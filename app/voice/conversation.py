"""
Voice conversation engine — same RAG + confidence gate as chat,
but optimised for short, spoken responses.
"""
from app.config import get_settings
from app.shared import llm, prompts
from app.shared.language import normalize_for_llm, translate_from_english
from app.rag.store import query_with_confidence
from app.chat.lead_scoring import score_message, compute_total_delta
from app.voice.call_session import CallSession
from app.dependencies import get_supabase_admin
from app.shared.patterns import PHONE_REGEX, EMAIL_REGEX

settings = get_settings()

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
    english_query, detected_lang = normalize_for_llm(user_text)
    session.language = detected_lang

    # RAG retrieval
    rag_result = await query_with_confidence(
        query=english_query,
        company_id=session.company_id,
        top_k=4,  # fewer chunks for voice (shorter context)
    )
    confidence = rag_result["confidence"]
    context_text = rag_result["context_text"]

    # Load company
    sb = get_supabase_admin()
    company_row = sb.table("companies").select("*").eq("id", session.company_id).single().execute()
    company = company_row.data or {}

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
        system += "\n[Retrieval confidence LOW — do NOT invent details. Capture name and phone instead.]"

    messages = session.conversation_history[-8:] + [
        {"role": "user", "content": english_query}
    ]

    reply_english = await llm.complete(
        system=system,
        messages=messages,
        max_tokens=150,  # short for voice
        temperature=0.4,
    )

    reply = translate_from_english(reply_english, detected_lang)

    # Score
    events = score_message(user_text, reply_english)
    score_delta = compute_total_delta(events)

    # Update session
    session.add_turn("user", user_text)
    session.add_turn("assistant", reply)
    session.score += score_delta
    session.transcript_parts.append(f"Caller: {user_text}")
    session.transcript_parts.append(f"AI: {reply}")

    # Update lead data from scoring events
    _update_lead_data(session, events, user_text)

    return reply, score_delta


def _update_lead_data(session: CallSession, events, user_text: str) -> None:
    """Extract contact signals and store on the session."""
    import re
    for event in events:
        if event.rule == "shared_phone":
            match = PHONE_REGEX.search(user_text)
            if match:
                session.lead_data["phone"] = match.group()
        if event.rule == "shared_email":
            match = EMAIL_REGEX.search(user_text)
            if match:
                session.lead_data["email"] = match.group()
        if event.rule == "shared_name":
            match = re.search(r"(?:my name(?:\s+is)?\s+|i(?:'m| am)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", user_text)
            if match:
                session.lead_data["name"] = match.group(1)
