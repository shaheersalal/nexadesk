"""
Voice conversation engine — same RAG + confidence gate as chat,
but optimised for short, spoken responses.
"""
import json
import logging

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.dependencies import get_redis
from app.shared import llm
from app.shared.verticals import build_knowledge_system_prompt
from app.shared.language import anormalize_for_llm, atranslate_from_english
from app.rag.store import query_with_confidence
from app.rag.live_fetch import get_live_context
from app.chat.lead_scoring import score_message, compute_total_delta
from app.voice.call_session import CallSession
from app.dependencies import get_supabase_admin
from app.shared.patterns import PHONE_REGEX, EMAIL_REGEX

settings = get_settings()
logger = logging.getLogger("nexadesk.voice")

COMPANY_CACHE_TTL = 300


async def _get_company(company_id: str) -> dict:
    """
    Fetch the company row, cached in Redis.

    This runs on every single voice turn. It was a blocking, synchronous
    `select("*")` inside an async handler — stalling the event loop mid-call,
    for a row that changes maybe once a month (AUDIT.md M4).
    """
    cache_key = f"company_row:{company_id}"
    redis = None
    try:
        redis = await get_redis(settings)
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.warning("Company cache read failed for %s: %s", company_id, exc)

    def _lookup():
        sb = get_supabase_admin()
        return sb.table("companies").select("*").eq("id", company_id).maybe_single().execute()

    result = await run_in_threadpool(_lookup)
    company = (result.data if result else None) or {}

    if redis is not None and company:
        try:
            await redis.setex(cache_key, COMPANY_CACHE_TTL, json.dumps(company, default=str))
        except Exception:
            pass

    return company


VOICE_SYSTEM_SUFFIX = (
    "\n\nIMPORTANT VOICE RULES:\n"
    "- Keep responses SHORT — 1 to 3 sentences max.\n"
    "- Never use markdown, bullet points, or lists.\n"
    "- Speak naturally as if on a phone call.\n"
    "- Always end with a question to keep the conversation going.\n"
)


async def _build_turn_context(user_text: str, session: CallSession) -> tuple[str, str, str]:
    """
    Shared prologue for the streaming voice turn path.
    Returns (system_prompt, english_query, detected_language).
    """
    english_query, detected_lang = await anormalize_for_llm(user_text)
    session.language = detected_lang
    session.language_confirmed = True

    rag_result = await query_with_confidence(
        query=english_query,
        company_id=session.company_id,
        top_k=4,
    )
    company = await _get_company(session.company_id)

    # ai_studio audition flow: a visitor pastes a URL on the web step before
    # dialling in, keyed by the number they said they'd call from. Real
    # estate companies never have anything stored under this key, so this is
    # a no-op for them. See app/rag/live_fetch.py.
    live_fetch_context = None
    if session.caller_number:
        live_fetch_context = await get_live_context(session.caller_number)

    system = build_knowledge_system_prompt(
        company, rag_result["context_text"], live_fetch_context,
    ) + VOICE_SYSTEM_SUFFIX

    if rag_result["confidence"] in ("PARTIAL", "NO_MATCH"):
        system += (
            "\n[Retrieval confidence LOW. Do not state any specific price, size, "
            "address or availability - nothing matched well enough. You may still "
            "answer general market questions and questions about this service from "
            "what you know. Do not stall: answer what you can, then offer to take a "
            "name and number for the specifics.]"
        )

    return system, english_query, detected_lang


async def stream_voice_turn(user_text: str, session: CallSession):
    """
    Run one voice turn, streaming.

    Yields reply fragments as the model produces them, so TTS can start
    speaking the first sentence while the rest is still being generated. The
    session is updated once the stream completes.

    Non-English calls are translated per fragment rather than in one pass at the
    end — translating the whole reply would reintroduce exactly the serial wait
    this path exists to remove.
    """
    system, english_query, detected_lang = await _build_turn_context(user_text, session)

    messages = session.conversation_history[-8:] + [
        {"role": "user", "content": english_query}
    ]

    collected: list[str] = []

    async def _english_tokens():
        async for token in llm.stream(system=system, messages=messages, max_tokens=150):
            collected.append(token)
            yield token

    if detected_lang == "en":
        async for token in _english_tokens():
            yield token
    else:
        # Translate at fragment granularity; sentence_chunks upstream gives us
        # whole clauses, which is the smallest unit that translates sanely.
        from app.voice.tts_stream import sentence_chunks
        async for chunk in sentence_chunks(_english_tokens()):
            yield await atranslate_from_english(chunk, detected_lang)

    reply_english = "".join(collected).strip()
    reply = (
        reply_english
        if detected_lang == "en"
        else await atranslate_from_english(reply_english, detected_lang)
    )

    events = score_message(user_text, reply_english)
    score_delta = compute_total_delta(events)

    session.add_turn("user", user_text)
    session.add_turn("assistant", reply)
    session.score += score_delta
    session.transcript_parts.append(f"Caller: {user_text}")
    session.transcript_parts.append(f"AI: {reply}")
    _update_lead_data(session, events, english_query)


def _update_lead_data(session: CallSession, events, english_text: str) -> None:
    """Extract contact signals and store on the session."""
    import re
    for event in events:
        if event.rule == "shared_phone":
            match = PHONE_REGEX.search(english_text)
            if match:
                session.lead_data["phone"] = match.group()
        if event.rule == "shared_email":
            match = EMAIL_REGEX.search(english_text)
            if match:
                session.lead_data["email"] = match.group()
        if event.rule == "shared_name":
            match = re.search(r"(?:my name(?:\s+is)?\s+|i(?:'m| am)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", english_text)
            if match:
                session.lead_data["name"] = match.group(1)
