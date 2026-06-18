"""
Chat engine — thin coordinator between HTTP layer, multi-agent orchestrator, and persistence.
"""
from typing import Optional
from datetime import datetime, timezone

from app.config import get_settings
from app.chat.lead_scoring import score_message, compute_total_delta
from app.dependencies import get_supabase_admin
from app.agents import orchestrator

settings = get_settings()


async def get_company_context(company_id: str) -> dict:
    """Load company record for system prompt injection."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("*").eq("id", company_id).single().execute()
    return result.data or {}


async def chat_turn(
    user_message: str,
    session_id: str,
    company_id: str,
    history: list[dict],  # [{role, content}]
    lead_id: Optional[str] = None,
) -> dict:
    """
    Process one chat turn via the multi-agent orchestrator.

    Returns:
      {
        "reply": str,
        "language": str,
        "confidence": "CONFIDENT"|"PARTIAL"|"NO_MATCH",
        "score_delta": int,
        "scoring_events": [...],
      }
    """
    company = await get_company_context(company_id)

    result = await orchestrator.run(
        user_message=user_message,
        company_id=company_id,
        history=history,
        company=company,
        lead_id=lead_id,
    )

    # Lead scoring (rule-based, no extra LLM call)
    events = score_message(user_message, result["reply_english"])
    score_delta = compute_total_delta(events)

    effective_lead_id = result.get("lead_id") or lead_id

    await _persist_turn(
        session_id=session_id,
        company_id=company_id,
        user_msg=user_message,
        assistant_msg=result["reply"],
        language=result["language"],
        lead_id=effective_lead_id,
        score_delta=score_delta,
    )

    return {
        "reply": result["reply"],
        "language": result["language"],
        "confidence": result["confidence"],
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

    if lead_id and score_delta != 0:
        sb.rpc("increment_lead_score", {"p_lead_id": lead_id, "p_delta": score_delta}).execute()
