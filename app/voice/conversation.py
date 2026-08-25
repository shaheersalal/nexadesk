"""
Voice conversation engine — same RAG + confidence gate as chat,
but optimised for short, spoken responses.
"""
import json
import logging

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.dependencies import get_redis
from app.shared import llm, prompts
from app.shared.language import anormalize_for_llm, atranslate_from_english
from app.rag.store import query_with_confidence
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


async def process_voice_turn(
    user_text: str,
    session: CallSession,
) -> tuple[str, int]:
    """
    Process one voice turn.
    Returns (assistant_reply, score_delta).
    """
    english_query, detected_lang = await anormalize_for_llm(user_text)
    session.language = detected_lang
    session.language_confirmed = True

    # RAG retrieval
    rag_result = await query_with_confidence(
        query=english_query,
        company_id=session.company_id,
        top_k=4,  # fewer chunks for voice (shorter context)
    )
    confidence = rag_result["confidence"]
    context_text = rag_result["context_text"]

    # Load company (cached — see _get_company)
    company = await _get_company(session.company_id)

    working_hours = company.get("working_hours", {"Mon-Fri": "9:00-17:00"})
    hours_str = ", ".join(f"{k}: {v}" for k, v in working_hours.items()) if isinstance(working_hours, dict) else str(working_hours)
    company_info = f"Phone: {company.get('phone', 'N/A')} | Email: {company.get('email', 'N/A')}"

    system = prompts.RECEPTIONIST_SYSTEM_PROMPT.format(
        ai_persona=company.get("ai_persona", "a friendly and professional real estate receptionist"),
        company_name=company.get("name", settings.APP_NAME),
        company_info=company_info,
        working_hours=hours_str,
        rag_context=context_text or "No property information loaded yet.",
    ) + VOICE_SYSTEM_SUFFIX

    if confidence in ("PARTIAL", "NO_MATCH"):
        system += (
            "\n[Retrieval confidence LOW. Do not state any specific price, size, "
            "address or availability - nothing matched well enough. You may still "
            "answer general market questions and questions about this service from "
            "what you know. Do not stall: answer what you can, then offer to take a "
            "name and number for the specifics.]"
        )

    messages = session.conversation_history[-8:] + [
        {"role": "user", "content": english_query}
    ]

    reply_english = await llm.complete(
        system=system,
        messages=messages,
        max_tokens=150,  # short for voice
        temperature=0.5,
    )

    reply = await atranslate_from_english(reply_english, detected_lang)

    # Score
    events = score_message(user_text, reply_english)
    score_delta = compute_total_delta(events)

    # Update session
    session.add_turn("user", user_text)
    session.add_turn("assistant", reply)
    session.score += score_delta
    session.transcript_parts.append(f"Caller: {user_text}")
    session.transcript_parts.append(f"AI: {reply}")

    # Update lead data from scoring events. Matched against the English-normalized
    # text (not the caller's raw words) since the name-capture regex only knows
    # English phrasing ("my name is...") — translate_to_english preserves digits
    # and email addresses verbatim, so phone/email extraction still works either way.
    _update_lead_data(session, events, english_query)

    return reply, score_delta


async def _build_turn_context(user_text: str, session: CallSession) -> tuple[str, str, str]:
    """
    Shared prologue for both the batch and streaming turn paths.
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

    working_hours = company.get("working_hours", {"Mon-Fri": "9:00-17:00"})
    hours_str = ", ".join(f"{k}: {v}" for k, v in working_hours.items()) if isinstance(working_hours, dict) else str(working_hours)
    company_info = f"Phone: {company.get('phone', 'N/A')} | Email: {company.get('email', 'N/A')}"

    system = prompts.RECEPTIONIST_SYSTEM_PROMPT.format(
        ai_persona=company.get("ai_persona", "a friendly and professional real estate receptionist"),
        company_name=company.get("name", settings.APP_NAME),
        company_info=company_info,
        working_hours=hours_str,
        rag_context=rag_result["context_text"] or "No property information loaded yet.",
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
