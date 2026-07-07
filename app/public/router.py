from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

import httpx

from app.config import get_settings
from app.dependencies import get_supabase_admin
from app.shared.demo_prompt import DEMO_KNOWLEDGE_PROMPT
from app.shared.language import normalize_for_llm, translate_from_english
from app.shared.llm import complete

router = APIRouter()


class _ChatMessage(BaseModel):
    role: str
    content: str


class DemoChatRequest(BaseModel):
    messages: list[_ChatMessage]


class DemoRequest(BaseModel):
    name: str
    email: str
    agency: str
    phone: str
    country: str = ""
    monthly_calls: str = ""
    discount_pct: Optional[int] = None
    original_price: Optional[float] = None
    final_price: Optional[float] = None
    plan_name: Optional[str] = None


@router.post("/book-demo")
async def book_demo(body: DemoRequest):
    settings = get_settings()

    sb_id = ""
    try:
        sb = get_supabase_admin()
        result = sb.table("demo_requests").insert({
            "name": body.name,
            "email": body.email,
            "agency_name": body.agency,
            "phone": body.phone,
            "country": body.country,
            "monthly_calls": body.monthly_calls,
            "status": "pending",
        }).execute()
        sb_id = (result.data or [{}])[0].get("id", "")
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

  {f'''<div style="background:#fef9ec;border:1px solid #f6c90e;border-radius:10px;padding:16px 20px;margin-bottom:24px">
    <p style="font-size:13px;font-weight:700;color:#92400e;margin:0 0 8px">🏷️ Discount Negotiated via Pricing Chat</p>
    <p style="font-size:14px;color:#1e293b;margin:0">
      Plan: <strong>{body.plan_name}</strong><br>
      Original price: <strong>${body.original_price:.2f}/mo</strong><br>
      Discount: <strong>{body.discount_pct}% off</strong><br>
      Final agreed price: <strong style="color:#16a34a">${body.final_price:.2f}/mo</strong>
    </p>
    <p style="font-size:12px;color:#92400e;margin:8px 0 0">Use this price in your Payoneer email — the client confirmed it.</p>
  </div>''' if body.discount_pct else ''}

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin-bottom:24px">
    <p style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">
      ✉️ Copy-paste email to send to client
    </p>
    <pre style="font-family:inherit;font-size:13px;line-height:1.7;color:#1e293b;white-space:pre-wrap;margin:0">{payoneer_template}</pre>
  </div>

  <a href="{settings.APP_BASE_URL}/admin/invite-quick?request_id={sb_id}&email={body.email}&name={body.name}&token={settings.ADMINTOKEN}"
     style="display:inline-block;background:#1e3a5f;color:#fff;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;font-size:14px">
    Activate Account →
  </a>
  <p style="font-size:12px;color:#94a3b8;margin-top:12px">
    Click once payment is confirmed — sends the invite email directly, no login needed.
  </p>
</div>""",
                },
            )

    return {"status": "ok"}


@router.post("/demo/chat")
async def demo_chat(body: DemoChatRequest):
    if len(body.messages) > 30:
        raise HTTPException(status_code=400, detail="Session too long")
    if not body.messages:
        raise HTTPException(status_code=400, detail="No messages")

    messages_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
    user_message = messages_dicts[-1]["content"]

    english_query, detected_lang = normalize_for_llm(user_message)

    # Send English to LLM; keep history as-is (client stores it)
    messages_for_llm = messages_dicts[:-1][-9:] + [{"role": "user", "content": english_query}]
    response_english = await complete(
        system=DEMO_KNOWLEDGE_PROMPT,
        messages=messages_for_llm,
        max_tokens=200,
        temperature=0.6,
    )
    return {"response": translate_from_english(response_english, detected_lang)}
