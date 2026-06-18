"""
RAG-augmented chat conversation engine.
Handles a single chat turn: retrieves context, calls LLM, scores the lead.
"""
from typing import Optional
from datetime import datetime, timezone

from app.config import get_settings
from app.shared import llm, prompts
from app.shared.language import normalize_for_llm, translate_from_english
from app.rag.store import query_with_confidence
from app.chat.lead_scoring import score_message, compute_total_delta
from app.dependencies import get_supabase_admin

settings = get_settings()


async def get_company_context(company_id: str) -> dict:
    """Load company record for system prompt injection."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("*").eq("id", company_id).single().execute()
    return result.data or {}


def _build_system_prompt(company: dict, rag_context: str) -> str:
    working_hours = company.get("working_hours", {"Mon–Fri": "9:00–17:00"})
    hours_str = ", ".join(f"{k}: {v}" for k, v in working_hours.items()) if isinstance(working_hours, dict) else str(working_hours)
    company_info = f"Address: {company.get('address', 'N/A')} | Phone: {company.get('phone', 'N/A')} | Email: {company.get('email', 'N/A')}"

    return prompts.RECEPTIONIST_SYSTEM_PROMPT.format(
        ai_persona=company.get("ai_persona", "a friendly and professional real estate receptionist"),
        company_name=company.get("name", settings.APP_NAME),
        company_info=company_info,
        working_hours=hours_str,
        rag_context=rag_context or "No property information has been uploaded yet.",
    )


async def chat_turn(
    user_message: str,
    session_id: str,
    company_id: str,
    history: list[dict],  # [{role, content}]
    lead_id: Optional[str] = None,
) -> dict:
    """
    Process one chat turn.

    Returns:
      {
        "reply": str,
        "language": str,
        "confidence": "CONFIDENT"|"PARTIAL"|"NO_MATCH",
        "score_delta": int,
        "scoring_events": [...],
      }
    """
    # Normalize language
    english_query, detected_lang = normalize_for_llm(user_message)

    # RAG retrieval
    rag_result = await query_with_confidence(
        query=english_query,
        company_id=company_id,
        top_k=5,
    )
    confidence = rag_result["confidence"]
    context_text = rag_result["context_text"]

    # Build messages for LLM
    company = await get_company_context(company_id)
    system = _build_system_prompt(company, context_text)

    messages = history[-10:] + [{"role": "user", "content": english_query}]

    # If partial/no match, prefix with confidence gate instruction
    if confidence in ("PARTIAL", "NO_MATCH"):
        gate_note = (
            "\n\n[SYSTEM NOTE: Retrieval confidence is LOW. "
            "Do NOT invent property details. Capture the lead instead.]"
        )
        system = system + gate_note

    reply_english = await llm.complete(
        system=system,
        messages=messages,
        max_tokens=512,
        temperature=0.4,
    )

    # Translate reply back to user's language
    reply = translate_from_english(reply_english, detected_lang)

    # Lead scoring
    events = score_message(user_message, reply_english)
    score_delta = compute_total_delta(events)

    # Persist conversation turn + update lead score
    await _persist_turn(
        session_id=session_id,
        company_id=company_id,
        user_msg=user_message,
        assistant_msg=reply,
        language=detected_lang,
        lead_id=lead_id,
        score_delta=score_delta,
    )

    return {
        "reply": reply,
        "language": detected_lang,
        "confidence": confidence,
        "score_delta": score_delta,
        "scoring_events": [{"rule": e.rule, "delta": e.delta} for e in events],
    }


async def _persist_turn(
    session_id: str,
    company_id: str,
    user_msg: str,
    assistant_msg: str,
    language: str,
    lead_id: Optional[str],
    score_delta: int,
) -> None:
    """Append turn to conversation and update lead score."""
    sb = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()

    turn = [
        {"role": "user", "content": user_msg, "timestamp": now},
        {"role": "assistant", "content": assistant_msg, "timestamp": now},
    ]

    # Upsert conversation record
    existing = sb.table("conversations").select("id, transcript").eq("session_id", session_id).execute()
    if existing.data:
        conv_id = existing.data[0]["id"]
        transcript = existing.data[0].get("transcript") or []
        transcript.extend(turn)
        sb.table("conversations").update({"transcript": transcript, "language": language}).eq("id", conv_id).execute()
    else:
        sb.table("conversations").insert({
            "company_id": company_id,
            "lead_id": lead_id,
            "channel": "chat",
            "session_id": session_id,
            "transcript": turn,
            "language": language,
        }).execute()

    # Update lead score atomically via RPC to prevent race conditions
    if lead_id and score_delta != 0:
        sb.rpc("increment_lead_score", {"p_lead_id": lead_id, "p_delta": score_delta}).execute()
