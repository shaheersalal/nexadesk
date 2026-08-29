"""
Central event dispatcher for NexaDesk integrations.

Call fire_event() from any router after a state change.
It schedules async webhook delivery without blocking the response.
"""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import httpx

from app.dependencies import get_supabase_admin
from app.shared.crypto import decrypt, encrypt

logger = logging.getLogger("nexadesk.integrations")

# asyncio only holds a weak reference to a running task. Without a strong
# reference here, a fire-and-forget webhook could be garbage collected
# mid-flight and vanish with no delivery and no error (AUDIT.md H5).
_background_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

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


def _is_safe_webhook_url(url: str) -> tuple[bool, str]:
    """
    Reject webhook targets that point back inside our own infrastructure.

    Endpoint URLs are tenant-supplied. Without this check a customer could
    register http://169.254.169.254/... or a Railway private address, have the
    server fetch it from inside the trust boundary, and read the resulting
    status code back out of webhook_logs — a blind SSRF with an oracle
    (AUDIT.md H7). Railway's private networking makes this materially worse
    than it was on the old single-host setup.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "malformed URL"

    if parsed.scheme != "https":
        return False, "only https:// webhook URLs are allowed"
    if not parsed.hostname:
        return False, "missing host"

    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return False, f"DNS resolution failed: {exc}"

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False, f"resolves to non-public address {ip}"

    return True, ""


async def _deliver(endpoint: dict, event: str, payload: dict, log_id: str, attempt: int):
    """Fire one HTTP delivery attempt and update the log row."""
    sb = get_supabase_admin()
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ts = str(int(time.time()))
    sig = _sign(body, endpoint["secret"], ts)

    status_code = None
    error = None

    safe, reason = _is_safe_webhook_url(endpoint["url"])
    if not safe:
        error = f"blocked: {reason}"
        logger.warning("Refusing webhook delivery to %s — %s", endpoint["url"], reason)
    else:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
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


async def _sync_to_crms(company_id: str, event: str, payload: dict):
    """Push lead events to any connected CRMs (HubSpot, Zoho, etc.)."""
    from app.config import get_settings
    from app.integrations.crm import hubspot, zoho
    settings = get_settings()

    sb = get_supabase_admin()
    conns = sb.table("crm_connections").select("*").eq("company_id", company_id).execute()
    for conn in (conns.data or []):
        provider = conn["provider"]
        # Stored encrypted at rest (AUDIT.md H9); decrypt() passes through any
        # legacy plaintext rows unchanged.
        token = decrypt(conn["access_token"])
        stored_refresh = decrypt(conn.get("refresh_token"))
        # Refresh if expiring
        if conn.get("expires_at") and stored_refresh:
            expires = datetime.fromisoformat(conn["expires_at"])
            if expires < datetime.now(timezone.utc) + timedelta(minutes=5):
                try:
                    if provider == "hubspot":
                        t = await hubspot.refresh_access_token(stored_refresh, settings.HUBSPOT_CLIENT_ID, settings.HUBSPOT_CLIENT_SECRET)
                    elif provider == "zoho":
                        t = await zoho.refresh_access_token(stored_refresh, settings.ZOHO_CLIENT_ID, settings.ZOHO_CLIENT_SECRET)
                    else:
                        continue
                    token = t["access_token"]
                    sb.table("crm_connections").update({
                        "access_token": encrypt(token),
                        "refresh_token": encrypt(t.get("refresh_token", stored_refresh)),
                        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=t.get("expires_in", 3600))).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", conn["id"]).eq("company_id", company_id).execute()
                except Exception as exc:
                    logger.warning("CRM token refresh failed for %s/%s: %s", company_id, provider, exc)
                    continue
        if not token:
            logger.warning("No usable token for %s/%s — reconnect required", company_id, provider)
            continue
        try:
            if provider == "hubspot":
                await hubspot.sync_lead(payload, token)
            elif provider == "zoho":
                await zoho.sync_lead(payload, token)
        except Exception as exc:
            logger.warning("CRM sync error for %s/%s: %s", company_id, provider, exc)


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

    # CRM sync for lead events (best-effort, non-blocking)
    if event in ("lead.created", "lead.status_changed"):
        _spawn(_sync_to_crms(company_id, event, payload))


def fire_event(company_id: str, event: str, payload: dict):
    """Non-blocking event fire. Call from any async router after a state change."""
    if event not in EVENTS:
        logger.error("Unknown event: %s", event)
        return
    _spawn(_dispatch(company_id, event, payload))


RETRY_LOCK_KEY = "webhook_retry_lock"
RETRY_LOCK_TTL = 55  # slightly under the 60s loop interval


async def retry_failed_webhooks():
    """
    Retry due webhook deliveries. Called every 60s from the app lifespan.

    The lifespan runs once per uvicorn worker, and Railway may run several
    replicas, so without coordination every worker would independently deliver
    each due retry — the customer's endpoint receiving N duplicates per cycle,
    with no idempotency key to deduplicate on (AUDIT.md H6). A short-lived
    Redis lock means exactly one worker does the work each tick.
    """
    from app.config import get_settings
    from app.dependencies import get_redis

    try:
        redis = await get_redis(get_settings())
        got_lock = await redis.set(RETRY_LOCK_KEY, "1", nx=True, ex=RETRY_LOCK_TTL)
        if not got_lock:
            return
    except Exception as exc:
        # Redis unavailable: skip this tick rather than risk a duplicate storm.
        logger.warning("Webhook retry lock unavailable, skipping tick: %s", exc)
        return

    sb = get_supabase_admin()
    now = datetime.now(timezone.utc).isoformat()
    result = sb.table("webhook_logs").select("*, webhook_endpoints(*)") \
        .lte("next_retry_at", now).is_("delivered_at", None).lt("attempts", 5).execute()

    for log in (result.data or []):
        endpoint = log.get("webhook_endpoints")
        if not endpoint or not endpoint.get("active"):
            continue
        await _deliver(endpoint, log["event"], log["payload"], log["id"], attempt=log["attempts"])
