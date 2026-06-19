from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.shared.llm import complete

router = APIRouter()

DEMO_SYSTEM_PROMPT = """You are Nexa, the AI receptionist for Palm Elite Properties — a premium real estate agency in Dubai. You handle inbound buyer and tenant inquiries with warmth and professionalism.

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
- Reply in whatever language the client uses (English, Spanish, French, Arabic, or others)
- Never reveal you're a demo or simulated."""


class DemoChatRequest(BaseModel):
    messages: list[dict]  # [{role: "user"|"assistant", content: str}]


class DemoRequest(BaseModel):
    name: str
    email: str
    agency: str
    phone: str
    country: str = ""
    monthly_calls: str = ""


@router.post("/book-demo")
async def book_demo(body: DemoRequest):
    settings = get_settings()

    try:
        sb = get_supabase_admin()
        sb.table("demo_requests").insert({
            "name": body.name,
            "email": body.email,
            "agency_name": body.agency,
            "phone": body.phone,
            "country": body.country,
            "monthly_calls": body.monthly_calls,
            "status": "pending",
        }).execute()
    except Exception:
        pass

    if settings.RESEND_API_KEY:
        payoneer_template = f"""Hi {body.name},

Thank you for your interest in NexaDesk — I'm excited to get your AI receptionist set up!

Your account is $136/month (AED 499), which includes:
• Dedicated AI phone number
• Unlimited chat conversations
• Full CRM dashboard & lead scoring
• Property knowledge base
• Full call transcripts
• Complete setup — handled by us

Please send payment via Payoneer using this link:
👉 [PASTE YOUR PAYONEER LINK HERE]

Once payment is confirmed, I'll activate your account and send you a setup link within a few hours. The whole onboarding takes about 10 minutes.

Any questions? Just reply to this email.

Best,
Shaheer
Founder, NexaDesk
nexadesk.site"""

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": "NexaDesk <onboarding@resend.dev>",
                    "to": ["shaheersalal@gmail.com"],
                    "subject": f"New Access Request — {body.agency} ({body.country})",
                    "html": f"""
<div style="font-family:sans-serif;max-width:580px;color:#1a1a1a">
  <h2 style="color:#1e3a5f;margin-bottom:4px">New Access Request 🎯</h2>
  <p style="color:#888;font-size:13px;margin-top:0">Submitted from nexadesk.site</p>

  <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:24px">
    <tr><td style="padding:9px 0;color:#666;width:140px;border-bottom:1px solid #f0f0f0">Name</td>
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">{body.name}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Email</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0"><a href="mailto:{body.email}" style="color:#2563eb">{body.email}</a></td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Agency</td>
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">{body.agency}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Phone</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0"><a href="tel:{body.phone}" style="color:#2563eb">{body.phone}</a></td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Country</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0">{body.country}</td></tr>
    <tr><td style="padding:9px 0;color:#666">Monthly Calls</td>
        <td style="padding:9px 0">{body.monthly_calls}</td></tr>
  </table>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin-bottom:24px">
    <p style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">
      ✉️ Copy-paste email to send to client
    </p>
    <pre style="font-family:inherit;font-size:13px;line-height:1.7;color:#1e293b;white-space:pre-wrap;margin:0">{payoneer_template}</pre>
  </div>

  <a href="https://nexadesk.site/admin"
     style="display:inline-block;background:#1e3a5f;color:#fff;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;font-size:14px">
    Activate Account →
  </a>
  <p style="font-size:12px;color:#94a3b8;margin-top:12px">
    Click above to open the admin panel and send the invite once payment is confirmed.
  </p>
</div>""",
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
