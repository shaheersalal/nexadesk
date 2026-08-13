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
import re
from typing import AsyncGenerator, Optional

from app.config import get_settings
from app.shared import llm
from app.shared.language import normalize_for_llm, translate_from_english
from app.shared.prompts import RECEPTIONIST_SYSTEM_PROMPT
from app.rag.store import query_with_confidence
from app.agents.tools import capture_lead_fields, flag_escalation, extract_fields_from_message

settings = get_settings()

# ── Query rewriter ────────────────────────────────────────────────────────────

async def _rewrite_query(english_query: str, history_tail: str) -> str:
    """
    Rewrite a conversational query into a standalone, search-optimised form
    before it hits the vector store.

    Runs in parallel with the router — zero extra latency on the critical path.
    Resolves pronouns ("that one", "it", "there"), injects implied location /
    property type from recent context, and expands vague terms like "cheap" or
    "near the beach" into concrete real-estate keywords.

    Falls back to the original query on any error or if rewriting is unhelpful.
    """
    prompt = (
        f"Recent conversation context: {history_tail}\n"
        f'User query: "{english_query}"\n\n'
        "Rewrite the user query as a standalone, specific real-estate search query "
        "that will retrieve the most relevant property listings and market data from "
        "a vector database.\n"
        "Rules:\n"
        "- Resolve ALL pronouns and references using the conversation context\n"
        "- Add specific property types, city/area names, price ranges if implied\n"
        "- Expand vague terms: 'cheap' → budget price range; 'near beach' → beach area names\n"
        "- Remove filler words and pleasantries\n"
        "- Return ONLY the rewritten query, no explanation. Max 25 words."
    )
    try:
        rewritten = await llm.complete(
            system="You rewrite conversational queries into specific property search queries. Return only the rewritten query text, nothing else.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.0,
        )
        rewritten = rewritten.strip().strip('"').strip("'")
        return rewritten if rewritten else english_query
    except Exception:
        return english_query


# ── Router ────────────────────────────────────────────────────────────────────

async def _route(user_message: str, history_tail: str, company_name: str) -> str:
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


# ── System prompt builders ────────────────────────────────────────────────────

def _knowledge_system(company: dict, rag_context: str, voice: bool = False) -> str:
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
    if voice:
        system += "\n\nIMPORTANT: Voice call — reply in 1–2 short sentences only. No lists."
    return system


def _qualifier_system(company: dict, voice: bool = False) -> str:
    system = (
        f"You are {company.get('ai_persona', 'a real estate receptionist')} "
        f"for {company.get('name', settings.APP_NAME)}.\n"
        "Your goal: understand what the client is looking for and naturally collect their details.\n"
        "Ask ONE qualifying question per reply (budget, area, bedrooms, timeline, name, or phone).\n"
        "Keep replies to 2–3 sentences. Sound like a warm, human agent — not a form.\n"
        "If they mention a specific property, confirm interest and ask for their contact details."
    )
    if voice:
        system += "\n\nIMPORTANT: Voice call — reply in 1–2 short sentences only."
    return system


def _escalation_system(company: dict, voice: bool = False) -> str:
    system = (
        f"You are {company.get('ai_persona', 'a receptionist')} "
        f"for {company.get('name', settings.APP_NAME)}.\n"
        "The client needs a human agent. Apologise sincerely, confirm you have flagged this for an agent "
        "who will follow up shortly, and ask for their name and best contact number if not already given. "
        "2–3 sentences, warm and professional."
    )
    if voice:
        system += "\n\nIMPORTANT: Voice call — reply in 1–2 short sentences only."
    return system


# ── Sub-agents ────────────────────────────────────────────────────────────────

async def _knowledge_agent(
    user_message: str,
    history: list[dict],
    company: dict,
    rag_context: str,
    voice: bool = False,
) -> str:
    system = _knowledge_system(company, rag_context, voice)
    messages = history[-10:] + [{"role": "user", "content": user_message}]
    max_tokens = 150 if voice else 300
    return await llm.complete(system=system, messages=messages, max_tokens=max_tokens, temperature=0.3)


async def _qualifier_agent(
    user_message: str,
    history: list[dict],
    company: dict,
    voice: bool = False,
) -> str:
    system = _qualifier_system(company, voice)
    messages = history[-8:] + [{"role": "user", "content": user_message}]
    max_tokens = 100 if voice else 180
    return await llm.complete(system=system, messages=messages, max_tokens=max_tokens, temperature=0.5)


async def _escalation_agent(user_message: str, company: dict, voice: bool = False) -> str:
    system = _escalation_system(company, voice)
    max_tokens = 80 if voice else 120
    return await llm.complete(
        system=system,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=max_tokens,
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

    recent_tail = " | ".join(
        f"{m['role']}: {m['content'][:60]}" for m in history[-2:]
    ) or "start of conversation"

    # Router + query rewrite in parallel — both are cheap fast LLM calls.
    # The rewritten query is used only for vector search; all agent calls
    # still receive the original english_query so the conversation stays natural.
    intent_task  = asyncio.create_task(_route(english_query, recent_tail, company_name))
    rewrite_task = asyncio.create_task(_rewrite_query(english_query, recent_tail))
    intent, rag_query = await asyncio.gather(intent_task, rewrite_task)

    rag_result = await query_with_confidence(rag_query, company_id, top_k=8)

    confidence = rag_result["confidence"]
    rag_context = rag_result["context_text"]

    if intent == "escalate":
        reply_task = asyncio.create_task(_escalation_agent(english_query, company))
    elif intent == "knowledge":
        reply_task = asyncio.create_task(
            _knowledge_agent(english_query, history, company, rag_context)
        )
    else:
        reply_task = asyncio.create_task(_qualifier_agent(english_query, history, company))

    extract_task = asyncio.create_task(
        extract_fields_from_message(english_query, llm.complete)
    )

    reply_english, extracted = await asyncio.gather(reply_task, extract_task)

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
        await flag_escalation(new_lead_id, company_id)

    reply = translate_from_english(reply_english, detected_lang)

    return {
        "reply": reply,
        "reply_english": reply_english,
        "language": detected_lang,
        "confidence": confidence,
        "intent": intent,
        "lead_id": new_lead_id,
    }


# ── Voice streaming entry point ───────────────────────────────────────────────

# Sentence boundary: after . ! ? followed by whitespace
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')


async def run_voice_streaming(
    user_message: str,
    company_id: str,
    history: list[dict],
    company: dict,
    lead_id: Optional[str] = None,
) -> AsyncGenerator[tuple, None]:
    """
    Voice-optimised orchestrator that streams the reply token by token.

    Yields:
      ("chunk", text)   — one LLM token / small text piece
      ("done", dict)    — final metadata: reply, reply_english, lead_id, intent, confidence
    """
    english_query, detected_lang = normalize_for_llm(user_message)
    company_name = company.get("name", settings.APP_NAME)

    recent_tail = " | ".join(
        f"{m['role']}: {m['content'][:60]}" for m in history[-2:]
    ) or "start of conversation"

    # Router + query rewrite in parallel — RAG waits for rewritten query.
    intent_task  = asyncio.create_task(_route(english_query, recent_tail, company_name))
    rewrite_task = asyncio.create_task(_rewrite_query(english_query, recent_tail))
    intent, rag_query = await asyncio.gather(intent_task, rewrite_task)

    rag_result = await query_with_confidence(rag_query, company_id, top_k=8)

    rag_context = rag_result["context_text"]
    confidence = rag_result["confidence"]

    # Field extraction fires now, we await it after streaming finishes
    extract_task = asyncio.create_task(
        extract_fields_from_message(english_query, llm.complete)
    )

    # Build system + messages for this intent (voice-brief)
    if intent == "escalate":
        system = _escalation_system(company, voice=True)
        messages = [{"role": "user", "content": english_query}]
        max_tokens = 80
    elif intent == "knowledge":
        system = _knowledge_system(company, rag_context, voice=True)
        messages = history[-10:] + [{"role": "user", "content": english_query}]
        max_tokens = 150
    else:
        system = _qualifier_system(company, voice=True)
        messages = history[-8:] + [{"role": "user", "content": english_query}]
        max_tokens = 100

    # Stream reply tokens
    reply_chunks: list[str] = []
    async for chunk in llm.stream(system=system, messages=messages, max_tokens=max_tokens):
        reply_chunks.append(chunk)
        yield ("chunk", chunk)

    reply_english = "".join(reply_chunks)
    reply = translate_from_english(reply_english, detected_lang)

    # Persist extracted fields (we can now await it)
    extracted = await extract_task
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
        await flag_escalation(new_lead_id, company_id)

    yield ("done", {
        "reply": reply,
        "reply_english": reply_english,
        "lead_id": new_lead_id,
        "intent": intent,
        "confidence": confidence,
    })
