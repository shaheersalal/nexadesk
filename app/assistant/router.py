from fastapi import APIRouter
from pydantic import BaseModel
import httpx

from app.auth.middleware import CurrentUser
from app.config import get_settings
from app.shared.llm import complete

router = APIRouter()

SYSTEM_PROMPT = """You are the NexaDesk in-app assistant. NexaDesk is an AI receptionist platform for real estate agencies.

You help agency owners with:
- Using NexaDesk features: Dashboard (stats + recent activity), Properties (list their inventory), Knowledge (upload listings, FAQs, brochures), Settings (embed widget, configure AI)
- Understanding their leads, client scores, and conversation transcripts shown on the Dashboard
- Getting the most from their AI receptionist — phone number, chat widget, lead scoring
- Billing: plan is $136/month (AED 499), includes 300 AI minutes, personal onboarding
- Technical setup: the widget embed code is on the Settings page

Be concise, friendly, and practical. If they have an urgent issue you can't resolve, tell them to email shaheersalal@gmail.com directly."""


class ChatRequest(BaseModel):
    messages: list[dict]


class NotifyRequest(BaseModel):
    messages: list[dict]
    user_email: str = ""


@router.post("/chat")
async def assistant_chat(body: ChatRequest, current_user: CurrentUser):
    response = await complete(
        system=SYSTEM_PROMPT,
        messages=body.messages,
        max_tokens=512,
        temperature=0.4,
    )
    return {"response": response}


@router.post("/notify")
async def assistant_notify(body: NotifyRequest, current_user: CurrentUser):
    settings = get_settings()
    if not settings.RESEND_API_KEY or not body.messages:
        return {"status": "skipped"}

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in body.messages
    )

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": "NexaDesk <onboarding@resend.dev>",
                "to": ["shaheersalal@gmail.com"],
                "subject": f"Assistant Chat — {body.user_email or current_user.get('email', 'unknown')}",
                "html": f"""
<div style="font-family:sans-serif;max-width:600px;color:#1a1a1a">
  <h2 style="color:#1e3a5f">NexaDesk Assistant Chat Session</h2>
  <p style="color:#666;font-size:14px"><b>User:</b> {body.user_email or current_user.get('email','')}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:16px 0"/>
  <pre style="background:#f9f9f9;padding:16px;border-radius:8px;font-size:13px;white-space:pre-wrap;line-height:1.6">{transcript}</pre>
</div>
                """,
            },
        )

    return {"status": "ok"}
