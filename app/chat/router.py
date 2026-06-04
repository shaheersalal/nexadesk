from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.chat.engine import chat_turn
from app.dependencies import get_supabase_admin
from app.shared.prompts import CHAT_GREETING
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# In-memory session history (Redis-backed sessions would be used in production)
_sessions: dict[str, list[dict]] = {}


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    company_id: str               # passed from embedded widget
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
    history = _sessions.get(session_id, [])

    result = await chat_turn(
        user_message=body.message,
        session_id=session_id,
        company_id=body.company_id,
        history=history,
        lead_id=body.lead_id,
    )

    # Update in-memory history
    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": result["reply"]})
    _sessions[session_id] = history[-20:]  # keep last 20 turns

    # Auto-create lead if not yet linked and score crossed threshold
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
async def get_history(session_id: str):
    sb = get_supabase_admin()
    result = (
        sb.table("conversations")
        .select("transcript, language, started_at")
        .eq("session_id", session_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return result.data


@router.get("/greeting")
async def get_greeting(company_id: str):
    """Return a greeting for the chat widget on load."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("name, ai_persona").eq("id", company_id).single().execute()
    company = result.data or {}
    company_name = company.get("name", settings.APP_NAME)
    ai_name = settings.APP_NAME

    return {
        "greeting": CHAT_GREETING.format(ai_name=ai_name, company_name=company_name),
        "company_name": company_name,
    }


async def _get_or_create_session_lead(session_id: str, company_id: str) -> Optional[str]:
    """Create a placeholder lead linked to this chat session."""
    sb = get_supabase_admin()
    # Check if conversation already has a lead
    conv = sb.table("conversations").select("lead_id").eq("session_id", session_id).execute()
    if conv.data and conv.data[0].get("lead_id"):
        return conv.data[0]["lead_id"]

    # Create new lead
    lead_result = sb.table("leads").insert({
        "company_id": company_id,
        "source": "chat",
        "status": "new",
        "score": 0,
    }).execute()
    if not lead_result.data:
        return None
    lead_id = lead_result.data[0]["id"]

    # Link to conversation
    sb.table("conversations").update({"lead_id": lead_id}).eq("session_id", session_id).execute()
    return lead_id
