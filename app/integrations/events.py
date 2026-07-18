"""
Central event dispatcher for NexaDesk integrations.

Call fire_event() from any router after a state change.
It schedules async webhook delivery without blocking the response.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone, timedelta

import httpx

from app.dependencies import get_supabase_admin

logger = logging.getLogger("nexadesk.integrations")

# All valid event names
EVENTS = {
    "lead.created",
    "lead.updated",
    "lead.status_changed",
    "appointment.booked",
    "call.ended",
}

# Retry delays in seconds: attempt 1→2→3→4→dead
_RETRY_DELAYS = [60, 300, 1800, 7200]


def _sign(payload_bytes: bytes, secret: str, timestamp: str) -> str:
    msg = f"{timestamp}.".encode() + payload_bytes
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


async def _deliver(endpoint: dict, event: str, payload: dict, log_id: str, attempt: int):
    """Fire one HTTP delivery attempt and update the log row."""
    sb = get_supabase_admin()
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ts = str(int(time.time()))
    sig = _sign(body, endpoint["secret"], ts)

    status_code = None
    error = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                endpoint["url"],
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-NexaDesk-Event": event,
                    "X-NexaDesk-Timestamp": ts,
                    "X-NexaDesk-Signature": f"sha256={sig}",
                    "User-Agent": "NexaDesk-Webhooks/1.0",
                },
            )
            status_code = r.status_code
    except Exception as exc:
        error = str(exc)

    success = status_code and 200 <= status_code < 300
    next_attempt = attempt + 1
    next_retry_at = None if success or next_attempt > len(_RETRY_DELAYS) else (
        datetime.now(timezone.utc) + timedelta(seconds=_RETRY_DELAYS[attempt])
    ).isoformat()

    sb.table("webhook_logs").update({
        "status_code": status_code,
        "attempts": next_attempt,
        "next_retry_at": next_retry_at,
        "delivered_at": datetime.now(timezone.utc).isoformat() if success else None,
        "error": error,
    }).eq("id", log_id).execute()

    if success:
        logger.info("Webhook delivered: %s → %s (%s)", event, endpoint["url"], status_code)
    else:
        logger.warning("Webhook failed (attempt %d): %s → %s | %s %s",
                       next_attempt, event, endpoint["url"], status_code, error)


async def _dispatch(company_id: str, event: str, payload: dict):
    """Fetch active endpoints subscribed to this event and fire them all."""
    sb = get_supabase_admin()
    result = sb.table("webhook_endpoints").select("*") \
        .eq("company_id", company_id).eq("active", True).execute()
    endpoints = [e for e in (result.data or []) if event in (e.get("events") or [])]

    for endpoint in endpoints:
        # Create log row first (attempt=0)
        log = sb.table("webhook_logs").insert({
            "endpoint_id": endpoint["id"],
            "event": event,
            "payload": payload,
            "attempts": 0,
        }).execute()
        log_id = log.data[0]["id"]
        await _deliver(endpoint, event, payload, log_id, attempt=0)


def fire_event(company_id: str, event: str, payload: dict):
    """Non-blocking event fire. Call from any async router after a state change."""
    if event not in EVENTS:
        logger.error("Unknown event: %s", event)
        return
    asyncio.create_task(_dispatch(company_id, event, payload))


async def retry_failed_webhooks():
    """Called periodically from lifespan to retry failed deliveries."""
    sb = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()
    result = sb.table("webhook_logs").select("*, webhook_endpoints(*)") \
        .lte("next_retry_at", now).is_("delivered_at", None).lt("attempts", 5).execute()

    for log in (result.data or []):
        endpoint = log.get("webhook_endpoints")
        if not endpoint or not endpoint.get("active"):
            continue
        await _deliver(endpoint, log["event"], log["payload"], log["id"], attempt=log["attempts"])
