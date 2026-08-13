from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.auth.middleware import CurrentUser
from app.chat.engine import chat_turn
from app.dependencies import get_supabase_admin
from app.shared.prompts import CHAT_GREETING
from app.shared import session_store
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# Session history cache lives in Redis (shared across all uvicorn workers).
# On cache miss (TTL expiry, restart) we reload from Supabase conversations table.
SESSION_TTL_SECONDS = 1800  # 30 min of inactivity


def _session_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


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
    history = await session_store.get_json(_session_key(session_id))
    if history is None:
        history = await _load_history_from_db(session_id)

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
    await session_store.set_json(_session_key(session_id), history, SESSION_TTL_SECONDS)

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
async def get_history(session_id: str, current_user: CurrentUser):
    """Fetch conversation transcript. Requires auth — dashboard use only."""
    sb = get_supabase_admin()
    result = (
        sb.table("conversations")
        .select("transcript, language, started_at, company_id")
        .eq("session_id", session_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify the conversation belongs to the authenticated user's company — fail closed on any error
    try:
        user_company = sb.table("users").select("company_id").eq("id", current_user["id"]).single().execute()
        user_cid = (user_company.data or {}).get("company_id")
    except Exception:
        raise HTTPException(status_code=403, detail="Access denied")
    if user_cid and result.data.get("company_id") != user_cid:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "transcript": result.data.get("transcript"),
        "language": result.data.get("language"),
        "started_at": result.data.get("started_at"),
    }


@router.get("/greeting")
async def get_greeting(company_id: str):
    """Return greeting for the embedded chat widget (public endpoint)."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("name, ai_persona").eq("id", company_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")
    company = result.data
    company_name = company.get("name", settings.APP_NAME)
    ai_name = settings.APP_NAME

    return {
        "greeting": CHAT_GREETING.format(ai_name=ai_name, company_name=company_name),
        "company_name": company_name,
    }


async def _load_history_from_db(session_id: str) -> list[dict]:
    """Rebuild LLM message history from Supabase on cache miss."""
    try:
        sb = get_supabase_admin()
        result = (
            sb.table("conversations")
            .select("transcript")
            .eq("session_id", session_id)
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
    sb = get_supabase_admin()
    conv = sb.table("conversations").select("lead_id").eq("session_id", session_id).execute()
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

    sb.table("conversations").update({"lead_id": lead_id}).eq("session_id", session_id).execute()
    return lead_id
