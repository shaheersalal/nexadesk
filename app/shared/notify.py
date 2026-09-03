"""
Lead-capture email notification via Resend — same provider and HTTPS-API
pattern already used by app/assistant/router.py's in-app assistant notify,
not raw SMTP, so it isn't affected by a cloud host blocking outbound SMTP
ports (Railway's history with this exact class of problem is why this
reuses Resend rather than reintroducing smtplib).

Deliberately scoped to the ai_studio vertical only. NexaDesk's real
real-estate tenants rely on their dashboard for leads — an email per lead
was never asked for or built for them, and adding it unconditionally here
would be a real, unwanted behaviour change to the actual paying product.
This exists because Shaheer specifically wants email on top of the
dashboard for his own site's leads (see app/agents/orchestrator.py::run).
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger("nexadesk.notify")

NOTIFY_TO = "contact@shaheer.dev"
NOTIFY_FROM = "shaheer.dev leads <onboarding@resend.dev>"


async def send_lead_email(fields: dict, company_name: str, channel: str) -> None:
    """Best-effort — never raises. Call via asyncio.create_task so a slow or
    failed send never adds latency to the caller's actual reply."""
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping lead email")
        return

    display_fields = [
        ("Name", fields.get("name")),
        ("Phone", fields.get("phone")),
        ("Email", fields.get("email")),
        ("Company", fields.get("client_company")),
        ("Project", fields.get("project_type")),
        ("Budget", fields.get("budget_text")),
        ("Timeline", fields.get("timeline")),
        ("Intent", fields.get("intent")),
        ("Channel", channel),
    ]
    rows = "".join(
        f'<tr><td style="padding:6px 10px;color:#666;font-size:13px">{label}</td>'
        f'<td style="padding:6px 10px;font-size:13px">{value}</td></tr>'
        for label, value in display_fields
        if value
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": NOTIFY_FROM,
                    "to": [NOTIFY_TO],
                    "subject": f"New lead — {fields.get('name') or 'unnamed visitor'} ({company_name})",
                    "html": (
                        '<div style="font-family:sans-serif;max-width:600px;color:#1a1a1a">'
                        f'<h2 style="color:#1e3a5f">New lead on {company_name}</h2>'
                        f'<table style="border-collapse:collapse">{rows}</table>'
                        '<p style="color:#999;font-size:12px;margin-top:16px">'
                        "Full conversation is in the dashboard.</p></div>"
                    ),
                },
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Lead notification email failed: %s", exc)
