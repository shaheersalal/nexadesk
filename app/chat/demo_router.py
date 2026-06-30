"""
Demo chat endpoint for shaheer.dev — no Supabase writes, hardcoded Prestige Properties context.
"""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.shared import llm
from app.shared import session_store

router = APIRouter()

MAX_MESSAGES = 15
SESSION_TTL_SECONDS = 1800  # 30 min — Redis expires demo sessions natively, no manual eviction needed


def _history_key(session_id: str) -> str:
    return f"demo:history:{session_id}"


def _count_key(session_id: str) -> str:
    return f"demo:count:{session_id}"

DEMO_SYSTEM_PROMPT = """\
You are Nadia, the AI receptionist for Prestige Properties — a premium Gulf real estate agency.

PROPERTY LISTINGS (these are your knowledge base):
- Downtown Dubai: 2BR luxury apartment, AED 2.8M, direct Burj Khalifa view, ready to move in
- Dubai Marina: 1BR with full sea view, AED 1.5M, high floor, Q3 2025 handover
- Palm Jumeirah: 4BR beachfront villa, AED 12M, private pool and beach, fully furnished
- Abu Dhabi (Al Reem Island): 3BR waterfront apartment, AED 1.9M, off-plan, 10% down payment
- Sharjah (Al Zahia): 2BR townhouse, AED 750K, gated family community, near international schools

YOUR GOALS (in order):
1. Understand what the visitor is looking for — ask 1–2 good questions, don't rush
2. Match them to one of the listings above, or offer to have an agent follow up
3. Collect: name, phone number, and optionally email
4. Once you have name + contact: "Perfect — I'll make sure our team reaches you within 2 hours."

RULES:
- 2–3 sentences per reply maximum. Never write paragraphs.
- Warm and professional — Gulf hospitality standard
- Respond in whatever language the visitor uses: English, Arabic, or Urdu
- If asked about a property NOT in your listings, say you'll check and ask for their contact details
- Never invent prices, availability, or features beyond what's listed above
- Never mention you're an AI unless directly asked — you're a receptionist
""".strip()


class DemoChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class DemoChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/chat", response_model=DemoChatResponse)
async def demo_chat(body: DemoChatRequest):
    session_id = body.session_id or str(uuid4())

    count = await session_store.get_json(_count_key(session_id)) or 0
    if count >= MAX_MESSAGES:
        return DemoChatResponse(
            reply="You've reached the demo limit. Reach Shaheer directly at shaheer@shaheer.dev to discuss deploying NexaDesk for your agency.",
            session_id=session_id,
        )

    history = await session_store.get_json(_history_key(session_id)) or []
    history.append({"role": "user", "content": body.message})

    reply = await llm.complete(
        system=DEMO_SYSTEM_PROMPT,
        messages=history[-10:],
        max_tokens=200,
        temperature=0.45,
    )

    history.append({"role": "assistant", "content": reply})
    await session_store.set_json(_history_key(session_id), history[-20:], SESSION_TTL_SECONDS)
    await session_store.set_json(_count_key(session_id), count + 1, SESSION_TTL_SECONDS)

    return DemoChatResponse(reply=reply, session_id=session_id)
