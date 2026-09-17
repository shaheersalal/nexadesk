from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.auth.middleware import CurrentUser
from app.dependencies import RlsDb
from app.chat.engine import chat_turn
from app.dependencies import get_supabase_admin
from app.shared.verticals import get_vertical
from app.shared import session_store
from app.shared.net import get_client_ip
from app.rag.live_fetch import (
    fetch_page_text, store_live_context, get_live_context_entry, clear_live_context,
    phone_key, LiveFetchError,
)
from app.config import get_settings

router = APIRouter()
settings = get_settings()


def _looks_like_phone(value: str) -> bool:
    """A live-context key that is mostly digits is a phone number, not a session id."""
    digits = "".join(ch for ch in value if ch.isdigit())
    return len(digits) >= 7 and len(digits) >= len(value.strip()) - 4

# Per-IP budget for the live-context fetch — it makes an outbound HTTP
# request per call, so it gets its own tighter limit rather than riding on
# chat's own per-session throttle.
LIVE_CONTEXT_RATE_WINDOW = 60   # seconds
LIVE_CONTEXT_RATE_MAX = 6       # fetches per IP per window

# Session history cache lives in Redis (shared across all uvicorn workers).
# On cache miss (TTL expiry, restart) we reload from Supabase conversations table.
SESSION_TTL_SECONDS = 1800  # 30 min of inactivity


def _session_key(company_id: str, session_id: str) -> str:
    # Company-scoped: the session id is client-supplied, so an unscoped key let
    # one tenant's chat read another's cached history.
    return f"chat:session:{company_id}:{session_id}"


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096)
    session_id: Optional[str] = None
    company_id: str = Field(..., min_length=36, max_length=36)  # UUID
    lead_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    lead_id: Optional[str] = None
    confidence: str
    language: str


@router.post("/message", response_model=ChatResponse)
async def send_message(body: ChatMessage):
    session_id = body.session_id or str(uuid4())

    # Reload history from Supabase if not in cache (e.g. TTL expiry, restart)
    history = await session_store.get_json(_session_key(body.company_id, session_id))
    if history is None:
        history = await _load_history_from_db(session_id, body.company_id)

    result = await chat_turn(
        user_message=body.message,
        session_id=session_id,
        company_id=body.company_id,
        history=history,
        lead_id=body.lead_id,
    )

    # Update cached history
    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": result["reply"]})
    history = history[-20:]  # keep last 20 turns
    await session_store.set_json(_session_key(body.company_id, session_id), history, SESSION_TTL_SECONDS)

    # Auto-create lead if not yet linked and engagement crossed threshold
    lead_id = body.lead_id
    if not lead_id and result.get("score_delta", 0) > 0:
        lead_id = await _get_or_create_session_lead(session_id, body.company_id)

    return ChatResponse(
        reply=result["reply"],
        session_id=session_id,
        lead_id=lead_id,
        confidence=result["confidence"],
        language=result["language"],
    )


@router.get("/history/{session_id}")
async def get_history(session_id: str, db: RlsDb, current_user: CurrentUser):
    """
    Fetch a conversation transcript. Dashboard use only.

    Runs as the caller, so row-level security decides whether the row is
    visible: another company's session simply is not found. The previous version
    read the row with service-role and then compared company ids by hand, which
    both fetched a row it was about to reject and let a user whose company_id
    was null through the check entirely — `if user_cid and ...` is not a denial
    when user_cid is None.
    """
    result = (
        db.table("conversations")
        .select("transcript, language, started_at")
        .eq("session_id", session_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data[0]


@router.get("/greeting")
async def get_greeting(company_id: str):
    """Return greeting for the embedded chat widget (public endpoint)."""
    # Both an unknown and a malformed id used to return 500: single() raises
    # when no row matches, and Postgres rejects a malformed uuid outright, so
    # the 404 below was unreachable.
    try:
        UUID(company_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Company not found")
    sb = get_supabase_admin()
    result = await run_in_threadpool(
        lambda: sb.table("companies")
        .select("name, ai_persona, receptionist_name, vertical")
        .eq("id", company_id).maybe_single().execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    company = result.data
    company_name = company.get("name", settings.APP_NAME)
    ai_name = company.get("receptionist_name") or settings.APP_NAME
    vertical = get_vertical(company.get("vertical"))

    return {
        "greeting": vertical["chat_greeting"].format(ai_name=ai_name, company_name=company_name),
        "company_name": company_name,
    }


class LiveContextRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=3, max_length=2048)
    site: str = Field("shaheer_dev", pattern="^(shaheer_dev|nexadesk_site)$")
    session_id: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=32)


class LiveContextClearRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=200)


@router.post("/live-context")
async def set_live_context(body: LiveContextRequest, request: Request):
    """
    Fetch a visitor-supplied URL and stash its text for this session/caller
    only (app/rag/live_fetch.py) — Part 2 of the ai_studio knowledge base.
    Public and rate-limited: it makes an outbound fetch on the caller's say-so.
    """
    ip = get_client_ip(request)

    # Adding a phone number re-sends the URL this session already loaded. Reuse
    # that copy: the reader fallback can take 15s, and a second fetch is a
    # second chance to fail after the visitor was already told it loaded.
    reused = None
    if body.session_id and body.session_id != body.key:
        entry = await get_live_context_entry(body.session_id)
        if entry and entry.get("text") and entry.get("source") == body.url.strip():
            reused = entry

    if reused:
        final_url, text = reused["url"], reused["text"]
    else:
        count = await session_store.incr(f"live_ctx_rate:{ip}", LIVE_CONTEXT_RATE_WINDOW)
        if count > LIVE_CONTEXT_RATE_MAX:
            raise HTTPException(status_code=429, detail="Too many page fetches - please wait a minute.")
        try:
            final_url, text = await fetch_page_text(body.url)
        except LiveFetchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    source = body.url.strip()
    await store_live_context(body.key, final_url, text, source=source)

    # Also store under the canonical phone key so an inbound call can find it.
    # Twilio's `From` is E.164 while the visitor types whatever they like, so
    # the raw `key` above will not match on the voice side - see phone_key().
    # Applied whenever the key itself looks like a phone number too, so an
    # older frontend that only sends `key` still works.
    phone_source = body.phone or (body.key if _looks_like_phone(body.key) else None)
    if phone_source:
        await store_live_context(phone_key(phone_source), final_url, text)

    # Durable log for the owner's own records (dashboard + session-end email
    # digest) - separate from the Redis entry above, which stays ephemeral
    # and is still deleted from the model's own working context as before.
    try:
        sb = get_supabase_admin()
        fetch_row = {
            "site": body.site,
            "session_id": body.session_id or body.key,
            "phone": body.phone,
            "ip_address": ip,
            "url": final_url,
            "scraped_excerpt": text[:4000],
        }
        await run_in_threadpool(lambda: sb.table("site_live_fetches").insert(fetch_row).execute())
    except Exception:
        pass  # never break the visitor's page over a logging failure

    return {"url": final_url, "chars": len(text)}


@router.post("/live-context/clear")
async def clear_live_context_route(body: LiveContextClearRequest):
    """
    Explicit deletion point for the ai_studio live-fetch context, called by
    the frontend on tab close / call end (navigator.sendBeacon). The Redis
    entry also carries a short TTL as a backstop, but this is the primary
    path — the content should not outlive the conversation that used it.
    """
    await clear_live_context(body.key)
    return {"cleared": True}


async def _load_history_from_db(session_id: str, company_id: str) -> list[dict]:
    """Rebuild LLM message history from Supabase on cache miss."""
    try:
        sb = get_supabase_admin()
        # session_id comes from the public request body. Unscoped, a caller who
        # supplied another tenant's session id got that conversation loaded
        # into the model's context, where it could be repeated back to them.
        result = await run_in_threadpool(
            lambda: sb.table("conversations")
            .select("transcript")
            .eq("session_id", session_id).eq("company_id", company_id)
            .single()
            .execute()
        )
        transcript = (result.data or {}).get("transcript") or []
        # transcript items: {role, content, timestamp} — strip timestamp for LLM
        history = [{"role": t["role"], "content": t["content"]} for t in transcript if "role" in t and "content" in t]
        return history[-20:]
    except Exception:
        return []


async def _get_or_create_session_lead(session_id: str, company_id: str) -> Optional[str]:
    """Create a placeholder lead linked to this chat session."""
    def _link() -> Optional[str]:
        sb = get_supabase_admin()
        # Scoped by company: session_id is client-supplied, and unscoped this
        # returned another tenant's lead id and re-linked their conversation.
        conv = (
            sb.table("conversations").select("lead_id")
            .eq("session_id", session_id).eq("company_id", company_id).execute()
        )
        if conv.data and conv.data[0].get("lead_id"):
            return conv.data[0]["lead_id"]

        lead_result = sb.table("leads").insert({
            "company_id": company_id,
            "source": "chat",
            "status": "new",
            "score": 0,
        }).execute()
        if not lead_result.data:
            return None
        lead_id = lead_result.data[0]["id"]

        (
            sb.table("conversations").update({"lead_id": lead_id})
            .eq("session_id", session_id).eq("company_id", company_id).execute()
        )
        return lead_id

    return await run_in_threadpool(_link)
