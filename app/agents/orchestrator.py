"""
Multi-agent orchestrator for chat turns.

Architecture:
  Router (fast, low tokens) → classify intent
  parallel with RAG fetch

  Then dispatch to:
    knowledge_agent  — RAG-backed property Q&A
    qualifier_agent  — lead qualification + structured capture
    escalation_agent — warm handoff, flag needs_human
    appointment intent is handled by qualifier_agent (captures details first)

Latency budget:
  - Router + RAG in parallel: ~400–600 ms
  - Reply agent: ~400–600 ms
  - Field extraction in parallel with reply: 0 extra ms
  Target: <1.5 s total before TTS/response delivery
"""
import asyncio
import json
from typing import Optional

from app.config import get_settings
from app.shared import llm
from app.shared.language import normalize_for_llm, translate_from_english
from app.shared.prompts import RECEPTIONIST_SYSTEM_PROMPT
from app.rag.store import query_with_confidence
from app.agents.tools import capture_lead_fields, flag_escalation, extract_fields_from_message

settings = get_settings()

# ── Router ────────────────────────────────────────────────────────────────────

async def _route(user_message: str, history_tail: str, company_name: str) -> str:
    """
    Fast classification — returns one of: knowledge | qualify | appointment | escalate.
    Uses low max_tokens to stay cheap and fast.
    """
    prompt = (
        f"Classify this inbound message for a real estate AI receptionist at {company_name}.\n"
        f"Recent context: {history_tail}\n"
        f'Message: "{user_message}"\n\n'
        "Return JSON only: {\"intent\": \"<one of: knowledge|qualify|appointment|escalate>\"}\n"
        "knowledge   = specific property question (price, availability, features, location)\n"
        "qualify     = general interest, hasn't shared requirements yet, or contact capture\n"
        "appointment = explicitly wants to book/schedule a viewing or meeting\n"
        "escalate    = angry, wants to speak to a human, or complex complaint"
    )
    raw = await llm.complete(
        system="You are a routing classifier. Return only valid JSON.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=30,
        temperature=0.0,
    )
    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned).get("intent", "qualify")
    except Exception:
        return "qualify"


# ── Sub-agents ────────────────────────────────────────────────────────────────

async def _knowledge_agent(
    user_message: str,
    history: list[dict],
    company: dict,
    rag_context: str,
) -> str:
    working_hours = company.get("working_hours", {"Mon–Fri": "9:00–17:00"})
    hours_str = (
        ", ".join(f"{k}: {v}" for k, v in working_hours.items())
        if isinstance(working_hours, dict)
        else str(working_hours)
    )
    company_info = (
        f"Address: {company.get('address', 'N/A')} | "
        f"Phone: {company.get('phone', 'N/A')} | "
        f"Email: {company.get('email', 'N/A')}"
    )
    system = RECEPTIONIST_SYSTEM_PROMPT.format(
        ai_persona=company.get("ai_persona", "a professional real estate receptionist"),
        company_name=company.get("name", settings.APP_NAME),
        company_info=company_info,
        working_hours=hours_str,
        rag_context=rag_context or "No property information uploaded yet.",
    )
    if not rag_context:
        system += (
            "\n\n[SYSTEM NOTE: No knowledge base context was retrieved. "
            "Do NOT invent property details. Capture the lead instead.]"
        )
    messages = history[-10:] + [{"role": "user", "content": user_message}]
    return await llm.complete(system=system, messages=messages, max_tokens=300, temperature=0.3)


async def _qualifier_agent(
    user_message: str,
    history: list[dict],
    company: dict,
) -> str:
    system = (
        f"You are {company.get('ai_persona', 'a real estate receptionist')} "
        f"for {company.get('name', settings.APP_NAME)}.\n"
        "Your goal: understand what the client is looking for and naturally collect their details.\n"
        "Ask ONE qualifying question per reply (budget, area, bedrooms, timeline, name, or phone).\n"
        "Keep replies to 2–3 sentences. Sound like a warm, human agent — not a form.\n"
        "If they mention a specific property, confirm interest and ask for their contact details."
    )
    messages = history[-8:] + [{"role": "user", "content": user_message}]
    return await llm.complete(system=system, messages=messages, max_tokens=180, temperature=0.5)


async def _escalation_agent(user_message: str, company: dict) -> str:
    system = (
        f"You are {company.get('ai_persona', 'a receptionist')} "
        f"for {company.get('name', settings.APP_NAME)}.\n"
        "The client needs a human agent. Apologise sincerely, confirm you have flagged this for an agent "
        "who will follow up shortly, and ask for their name and best contact number if not already given. "
        "2–3 sentences, warm and professional."
    )
    return await llm.complete(
        system=system,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=120,
        temperature=0.4,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

async def run(
    user_message: str,
    company_id: str,
    history: list[dict],
    company: dict,
    lead_id: Optional[str] = None,
) -> dict:
    """
    Execute one multi-agent chat turn.

    Returns:
      {
        "reply": str,              # final reply (possibly translated)
        "reply_english": str,      # pre-translation reply (for lead scoring)
        "language": str,
        "confidence": str,
        "intent": str,
        "lead_id": str | None,     # may be updated if new lead was created
      }
    """
    english_query, detected_lang = normalize_for_llm(user_message)
    company_name = company.get("name", settings.APP_NAME)

    # Compact history tail for the router (just last 2 turns, cheap string)
    recent_tail = " | ".join(
        f"{m['role']}: {m['content'][:60]}" for m in history[-2:]
    ) or "start of conversation"

    # Step 1: Router + RAG in parallel — biggest latency win
    intent_task = asyncio.create_task(_route(english_query, recent_tail, company_name))
    rag_task = asyncio.create_task(query_with_confidence(english_query, company_id, top_k=8))
    intent, rag_result = await asyncio.gather(intent_task, rag_task)

    confidence = rag_result["confidence"]
    rag_context = rag_result["context_text"]

    # Step 2: Reply agent + field extraction in parallel
    if intent == "escalate":
        reply_task = asyncio.create_task(_escalation_agent(english_query, company))
    elif intent == "knowledge":
        reply_task = asyncio.create_task(
            _knowledge_agent(english_query, history, company, rag_context)
        )
    else:
        # qualify and appointment both go to qualifier (appointment needs details first)
        reply_task = asyncio.create_task(_qualifier_agent(english_query, history, company))

    extract_task = asyncio.create_task(
        extract_fields_from_message(english_query, llm.complete)
    )

    reply_english, extracted = await asyncio.gather(reply_task, extract_task)

    # Step 3: Persist any extracted fields to leads table (best-effort)
    new_lead_id = lead_id
    if any(v is not None for v in extracted.values()):
        new_lead_id = await capture_lead_fields(
            lead_id, company_id,
            name=extracted.get("name"),
            phone=extracted.get("phone"),
            email=extracted.get("email"),
            budget_min=extracted.get("budget_min"),
            budget_max=extracted.get("budget_max"),
            area_preference=extracted.get("area_preference"),
            bedrooms_needed=extracted.get("bedrooms_needed"),
            timeline=extracted.get("timeline"),
            intent=extracted.get("intent"),
        )

    if intent == "escalate":
        await flag_escalation(new_lead_id)

    reply = translate_from_english(reply_english, detected_lang)

    return {
        "reply": reply,
        "reply_english": reply_english,
        "language": detected_lang,
        "confidence": confidence,
        "intent": intent,
        "lead_id": new_lead_id,
    }
