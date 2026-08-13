import html
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

import httpx
import redis.asyncio as aioredis

from app.admin.invite_token import issue_invite_token
from app.config import get_settings
from app.dependencies import get_supabase_admin, get_redis
from app.shared.demo_prompt import DEMO_KNOWLEDGE_PROMPT
from app.shared.language import anormalize_for_llm, atranslate_from_english
from app.shared.llm import complete

logger = logging.getLogger("nexadesk.public")
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """
    Best-effort client IP for rate limiting.

    Forwarded headers are only honoured when TRUST_PROXY_HEADERS is set, because
    they are trivially forged otherwise: `curl -H "CF-Connecting-IP: <random>"`
    yields a fresh throttle bucket on every request, which nullified every rate
    limit in this module (AUDIT.md M5).

    Enable it only when the app genuinely sits behind a proxy that overwrites
    these headers. Railway's edge does not, so the default is off and we use the
    real socket peer.
    """
    if get_settings().TRUST_PROXY_HEADERS:
        cf = request.headers.get("CF-Connecting-IP")
        if cf:
            return cf.strip()
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return (request.client.host if request.client else None) or "unknown"


async def _verify_recaptcha(token: str | None, settings) -> bool:
    """
    Verify a reCAPTCHA v3 token.

    Fails *closed* once RECAPTCHA_SECRET is configured: previously any exception
    — or a missing token on a configured deployment — returned True, so a
    verification outage or a malformed response silently disabled bot protection
    on the public form (AUDIT.md M6).

    When RECAPTCHA_SECRET is unset the check is skipped entirely, which keeps
    local development working without Google credentials.
    """
    if not settings.RECAPTCHA_SECRET:
        return True  # not configured — check disabled by choice
    if not token:
        return False  # configured but the client sent nothing
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": settings.RECAPTCHA_SECRET, "response": token},
            )
            d = r.json()
            return bool(d.get("success")) and d.get("score", 0) >= 0.5
    except Exception as exc:
        logger.warning("reCAPTCHA verification failed, rejecting submission: %s", exc)
        return False


# Caps on the public demo endpoint. Without these, /demo/chat is an
# unauthenticated, unmetered path straight to a paid LLM (AUDIT.md H3).
DEMO_MAX_MESSAGES = 30
DEMO_MAX_CHARS = 2000          # per message
DEMO_RATE_WINDOW = 60          # seconds
DEMO_RATE_MAX = 15             # requests per IP per window


class _ChatMessage(BaseModel):
    role: str
    content: str = Field(max_length=DEMO_MAX_CHARS)


class DemoChatRequest(BaseModel):
    messages: list[_ChatMessage] = Field(max_length=DEMO_MAX_MESSAGES)
    voice_mode: bool = False   # true → short spoken-style replies, same as voice demo


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
    recaptcha_token: Optional[str] = None


@router.post("/book-demo")
async def book_demo(
    body: DemoRequest,
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
):
    settings = get_settings()

    # Redis throttle — 3-second minimum between submissions from the same IP
    ip = _get_client_ip(request)
    throttle_key = f"demo_throttle:{ip}"
    if not await redis.set(throttle_key, "1", nx=True, ex=3):
        raise HTTPException(status_code=429, detail="Too many requests — please wait a moment.")

    # reCAPTCHA v3 verification
    if not await _verify_recaptcha(body.recaptcha_token, settings):
        raise HTTPException(status_code=403, detail="Bot check failed.")

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
        # Escape everything that came from the public form before it goes into
        # HTML. Unescaped, a crafted `name` could close the surrounding tag and
        # inject a link — turning this notification into a phishing email sent
        # from your own domain to yourself (AUDIT.md M8).
        e_name = html.escape(body.name)
        e_email = html.escape(body.email)
        e_agency = html.escape(body.agency)
        e_phone = html.escape(body.phone)
        e_country = html.escape(body.country)
        e_calls = html.escape(body.monthly_calls)

        # Single-use activation token — replaces embedding the static
        # ADMINTOKEN in the link (AUDIT.md C2).
        invite_token = await issue_invite_token(redis, sb_id, body.email, body.name)
        activate_url = f"{settings.APP_BASE_URL}/admin/invite-quick?token={invite_token}"

        # Only render the discount block when the prices needed to render it are
        # actually present. discount_pct alone used to be enough to enter this
        # branch, and `${None:.2f}` raised TypeError -> HTTP 500 (AUDIT.md M7).
        has_discount = (
            body.discount_pct is not None
            and body.original_price is not None
            and body.final_price is not None
        )

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
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">{e_name}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Email</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0"><a href="mailto:{e_email}" style="color:#2563eb">{e_email}</a></td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Agency</td>
        <td style="padding:9px 0;font-weight:600;border-bottom:1px solid #f0f0f0">{e_agency}</td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Phone</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0"><a href="tel:{e_phone}" style="color:#2563eb">{e_phone}</a></td></tr>
    <tr><td style="padding:9px 0;color:#666;border-bottom:1px solid #f0f0f0">Country</td>
        <td style="padding:9px 0;border-bottom:1px solid #f0f0f0">{e_country}</td></tr>
    <tr><td style="padding:9px 0;color:#666">Monthly Calls</td>
        <td style="padding:9px 0">{e_calls}</td></tr>
  </table>

  {f'''<div style="background:#fef9ec;border:1px solid #f6c90e;border-radius:10px;padding:16px 20px;margin-bottom:24px">
    <p style="font-size:13px;font-weight:700;color:#92400e;margin:0 0 8px">🏷️ Discount Negotiated via Pricing Chat</p>
    <p style="font-size:14px;color:#1e293b;margin:0">
      Plan: <strong>{html.escape(body.plan_name or "")}</strong><br>
      Original price: <strong>${body.original_price:.2f}/mo</strong><br>
      Discount: <strong>{body.discount_pct}% off</strong><br>
      Final agreed price: <strong style="color:#16a34a">${body.final_price:.2f}/mo</strong>
    </p>
    <p style="font-size:12px;color:#92400e;margin:8px 0 0">Use this price in your Payoneer email — the client confirmed it.</p>
  </div>''' if has_discount else ''}

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;margin-bottom:24px">
    <p style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin:0 0 12px">
      ✉️ Copy-paste email to send to client
    </p>
    <pre style="font-family:inherit;font-size:13px;line-height:1.7;color:#1e293b;white-space:pre-wrap;margin:0">{payoneer_template}</pre>
  </div>

  <a href="{activate_url}"
     style="display:inline-block;background:#1e3a5f;color:#fff;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;font-size:14px">
    Activate Account →
  </a>
  <p style="font-size:12px;color:#94a3b8;margin-top:12px">
    Click once payment is confirmed — sends the invite email directly, no login needed.
    Single-use link, expires in 7 days.
  </p>
</div>""",
                },
            )

    return {"status": "ok"}


@router.post("/demo/chat")
async def demo_chat(
    body: DemoChatRequest,
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
):
    if not body.messages:
        raise HTTPException(status_code=400, detail="No messages")

    # Sliding-ish per-IP budget. book_demo on this same router has always been
    # throttled; this endpoint was not, despite being the one that actually
    # spends money on every call (AUDIT.md H3).
    ip = _get_client_ip(request)
    rate_key = f"demo_chat_rate:{ip}"
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, DEMO_RATE_WINDOW)
    if count > DEMO_RATE_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many messages — please wait a minute before continuing.",
        )

    messages_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
    user_message = messages_dicts[-1]["content"]

    english_query, detected_lang = await anormalize_for_llm(user_message)

    # Send English to LLM; keep history as-is (client stores it)
    messages_for_llm = messages_dicts[:-1][-9:] + [{"role": "user", "content": english_query}]

    if body.voice_mode:
        system = (
            DEMO_KNOWLEDGE_PROMPT
            + "\n\nIMPORTANT: Simulate a voice call. Reply in 1–2 short sentences only. "
            "No bullet points or lists. Always end with a question."
        )
        max_tokens, temperature = 150, 0.4
    else:
        system, max_tokens, temperature = DEMO_KNOWLEDGE_PROMPT, 200, 0.6

    response_english = await complete(
        system=system,
        messages=messages_for_llm,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return {"response": await atranslate_from_english(response_english, detected_lang)}
