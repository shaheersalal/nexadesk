from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.shared.llm import complete

router = APIRouter()

DEMO_SYSTEM_PROMPT = """You are Aria, the AI receptionist for Palm Elite Properties — a premium real estate agency in Dubai. You handle inbound buyer and tenant inquiries with warmth and professionalism.

Your goals:
1. Understand what the client needs (buy, rent, invest, view a property)
2. Qualify them: budget, preferred area, timeline, family size, number of bedrooms
3. Share accurate price ranges confidently
4. Capture their name and number so an agent can follow up, or book a viewing

Property knowledge — UAE market 2025:
DUBAI SALE: Downtown/Burj Khalifa studio AED 950K–1.4M · 1BR AED 1.5M–2.3M · 2BR AED 2.1M–3.8M | Marina studio AED 550K–950K · 1BR AED 900K–1.6M · 2BR AED 1.5M–2.8M | JBR 1BR AED 1.1M–1.8M · 2BR AED 1.7M–3M | Business Bay studio AED 600K–950K · 1BR AED 950K–1.5M | Palm Jumeirah 1BR apt AED 2M–3.5M · villa AED 12M–35M | Dubai Hills 1BR AED 900K–1.4M · 4BR villa AED 4M–7M | Arabian Ranches 4BR villa AED 3.2M–5.5M | JVC studio AED 380K–600K · 1BR AED 550K–900K (best yields 7–9%) | JLT 1BR AED 750K–1.2M
DUBAI RENTAL (annual): Downtown 1BR AED 95K–145K · 2BR AED 145K–210K | Marina 1BR AED 75K–120K · 2BR AED 115K–175K | Business Bay 1BR AED 65K–100K | JVC 1BR AED 40K–65K (most affordable)
ABU DHABI: Saadiyat Island 1BR AED 1.2M–2M · villa AED 7M–20M | Al Reem Island studio AED 500K–750K · 1BR AED 750K–1.3M | Yas Island 1BR AED 750K–1.2M
SHARJAH: 2BR sale AED 420K–800K · studio rental AED 15K–28K/year

Rules:
- Keep replies to 2–3 sentences maximum. Never bullet points.
- Ask ONE qualifying question per reply — never multiple at once.
- Sound like a smart, human agent — not a chatbot.
- If they want to speak to a human or book a viewing: ask for their name and phone number.
- Reply in whatever language the client uses (Arabic, Urdu, French, etc.)
- Never reveal you're a demo or simulated."""


class DemoChatRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"assistant", content: str}]


class DemoRequest(BaseModel):
    name: str
    email: str
    agency: str
    phone: str


@router.post("/book-demo")
async def book_demo(body: DemoRequest):
    settings = get_settings()

    # Persist to Supabase (best-effort — table may not exist yet)
    try:
        sb = get_supabase_admin()
        sb.table("demo_requests").insert({
            "name": body.name,
            "email": body.email,
            "agency_name": body.agency,
            "phone": body.phone,
        }).execute()
    except Exception:
        pass

    # Notify via Resend
    if settings.RESEND_API_KEY:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": "NexaDesk <onboarding@resend.dev>",
                    "to": ["shaheersalal@gmail.com"],
                    "subject": f"New Demo Request — {body.agency}",
                    "html": f"""
<div style="font-family:sans-serif;max-width:520px;color:#1a1a1a">
  <h2 style="color:#1e3a5f;margin-bottom:20px">New Demo Request 🎯</h2>
  <table style="width:100%;border-collapse:collapse;font-size:15px">
    <tr><td style="padding:10px 0;color:#666;width:130px">Name</td>
        <td style="padding:10px 0;font-weight:600">{body.name}</td></tr>
    <tr style="background:#f9f9f9"><td style="padding:10px 0;color:#666">Email</td>
        <td style="padding:10px 0"><a href="mailto:{body.email}" style="color:#2563eb">{body.email}</a></td></tr>
    <tr><td style="padding:10px 0;color:#666">Agency</td>
        <td style="padding:10px 0;font-weight:600">{body.agency}</td></tr>
    <tr style="background:#f9f9f9"><td style="padding:10px 0;color:#666">Phone</td>
        <td style="padding:10px 0"><a href="tel:{body.phone}" style="color:#2563eb">{body.phone}</a></td></tr>
  </table>
  <p style="margin-top:24px;color:#888;font-size:13px">Sent from nexadesk.site landing page</p>
</div>
                    """,
                },
            )

    return {"status": "ok"}


@router.post("/demo/chat")
async def demo_chat(body: DemoChatRequest):
    if len(body.messages) > 30:
        raise HTTPException(status_code=400, detail="Session too long")
    # Keep only last 10 turns to control cost
    recent = body.messages[-10:]
    response = await complete(
        system=DEMO_SYSTEM_PROMPT,
        messages=recent,
        max_tokens=160,
        temperature=0.6,
    )
    return {"response": response}
