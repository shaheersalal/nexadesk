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


async def send_visitor_digest_email(summary: dict) -> None:
    """
    Fired from app/analytics/router.py::session_end for every visitor who
    leaves shaheer.dev or nexadesk.site - not just ones who became leads.
    Best-effort, never raises: called via asyncio.create_task from a
    sendBeacon handler with no response the page could react to anyway.
    """
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        logger.info("RESEND_API_KEY not set — skipping visitor digest email")
        return

    site_label = "shaheer.dev" if summary["site"] == "shaheer_dev" else "nexadesk.site"
    live_fetch = summary.get("live_fetch") or {}
    conversation = summary.get("conversation") or {}
    review = summary.get("review") or {}
    prior_dates = summary.get("prior_visit_dates") or []

    rows = [
        ("Site", site_label),
        ("IP", summary.get("ip")),
        ("Seen before on", ", ".join(prior_dates) if prior_dates else None),
        ("Pageviews", summary.get("pageviews")),
        ("Clicks", summary.get("clicks")),
        ("Max scroll", f"{summary.get('max_scroll_pct', 0)}%" if summary.get("max_scroll_pct") else None),
        ("Referrer", summary.get("referrer")),
        ("User agent", summary.get("user_agent")),
        ("Entered URL", live_fetch.get("url")),
        ("Review", f"{review.get('stars')}★ — {review.get('review_text')}" if review.get("stars") or review.get("review_text") else None),
        ("Email left", review.get("email")),
    ]
    rows_html = "".join(
        f'<tr><td style="padding:6px 10px;color:#666;font-size:13px;vertical-align:top">{label}</td>'
        f'<td style="padding:6px 10px;font-size:13px;vertical-align:top">{value}</td></tr>'
        for label, value in rows
        if value
    )

    excerpt = (live_fetch.get("scraped_excerpt") or "")[:1500]
    excerpt_html = (
        f'<h3 style="color:#1e3a5f;font-size:14px">Scraped page excerpt</h3>'
        f'<pre style="white-space:pre-wrap;font-size:12px;background:#f5f5f5;padding:10px;'
        f'border-radius:6px;max-height:300px;overflow:auto">{excerpt}</pre>'
        if excerpt else ""
    )

    transcript = conversation.get("transcript") or []
    transcript_html = ""
    if transcript:
        turns = "".join(
            f'<p style="margin:4px 0;font-size:12px"><b>{t.get("role")}:</b> {t.get("content")}</p>'
            for t in transcript if isinstance(t, dict)
        )
        transcript_html = (
            f'<h3 style="color:#1e3a5f;font-size:14px">Call/chat transcript ({conversation.get("channel")})</h3>'
            f'<div style="background:#f5f5f5;padding:10px;border-radius:6px;max-height:400px;overflow:auto">{turns}</div>'
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": NOTIFY_FROM,
                    "to": [NOTIFY_TO],
                    "subject": f"Visitor left {site_label} — {summary.get('ip')}",
                    "html": (
                        '<div style="font-family:sans-serif;max-width:600px;color:#1a1a1a">'
                        f'<h2 style="color:#1e3a5f">Visitor activity — {site_label}</h2>'
                        f'<table style="border-collapse:collapse">{rows_html}</table>'
                        f'{excerpt_html}{transcript_html}'
                        '</div>'
                    ),
                },
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Visitor digest email failed: %s", exc)
