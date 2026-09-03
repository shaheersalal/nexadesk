"""
Owner-only first-party analytics for shaheer.dev and nexadesk.site — IP,
pageviews, clicks, scroll depth. Not a tenant/company feature: gated purely
by ADMIN_UID (app/admin/router.py::require_admin), the same mechanism that
already protects /dashboard/support and /nxd-c0ns0le in the dashboard.

POST /track is public and unauthenticated by necessity (it's called by an
anonymous site visitor's browser) — rate-limited per IP, and every write is
capped in size so it can't be used to smuggle arbitrary data volume into
Supabase.
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.admin.router import require_admin
from app.dependencies import get_supabase_admin
from app.shared import session_store
from app.shared.net import get_client_ip

logger = logging.getLogger("nexadesk.analytics")
router = APIRouter()

TRACK_RATE_WINDOW = 60   # seconds
TRACK_RATE_MAX = 60      # requests per IP per window — generous, these are cheap beacons

_SITES = ("shaheer_dev", "nexadesk_site")


class TrackEvent(BaseModel):
    event_type: Literal["pageview", "click", "scroll_depth"]
    path: str = Field("", max_length=500)
    event_data: dict = Field(default_factory=dict)


class TrackRequest(BaseModel):
    site: Literal["shaheer_dev", "nexadesk_site"]
    session_id: str = Field(..., min_length=1, max_length=200)
    referrer: str = Field("", max_length=500)
    events: list[TrackEvent] = Field(..., min_length=1, max_length=20)


@router.post("/track")
async def track(body: TrackRequest, request: Request):
    ip = get_client_ip(request)
    count = await session_store.incr(f"site_track_rate:{ip}", TRACK_RATE_WINDOW)
    if count > TRACK_RATE_MAX:
        raise HTTPException(status_code=429, detail="Too many events.")

    ua = request.headers.get("user-agent", "")[:500]
    rows = [
        {
            "site": body.site,
            "session_id": body.session_id,
            "ip_address": ip,
            "user_agent": ua,
            "referrer": body.referrer[:500],
            "path": event.path[:500],
            "event_type": event.event_type,
            "event_data": event.event_data,
        }
        for event in body.events
    ]

    try:
        sb = get_supabase_admin()
        sb.table("site_visits").insert(rows).execute()
    except Exception as exc:
        # Never break the visitor's page over an analytics write failure.
        logger.warning("site_visits insert failed: %s", exc)
        return {"tracked": False}

    return {"tracked": True, "count": len(rows)}


@router.get("/site")
async def site_summary(
    site: Optional[Literal["shaheer_dev", "nexadesk_site"]] = None,
    days: int = 7,
    _admin=Depends(require_admin),
):
    """Aggregate stats + a recent-session list. Admin-only."""
    from datetime import datetime, timedelta, timezone

    days = max(1, min(days, 90))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    sb = get_supabase_admin()
    q = sb.table("site_visits").select(
        "site, session_id, ip_address, path, event_type, referrer, created_at"
    ).gte("created_at", since).order("created_at", desc=True).limit(5000)
    if site:
        q = q.eq("site", site)
    result = q.execute()
    rows = result.data or []

    sessions: dict[str, dict] = {}
    pageviews = clicks = scrolls = 0
    for row in rows:
        sid = row["session_id"]
        s = sessions.setdefault(sid, {
            "session_id": sid,
            "site": row["site"],
            "ip_address": row["ip_address"],
            "referrer": row["referrer"],
            "first_path": row["path"],
            "first_seen": row["created_at"],
            "last_seen": row["created_at"],
            "pageviews": 0,
            "clicks": 0,
            "scroll_max_pct": 0,
        })
        s["first_seen"] = min(s["first_seen"], row["created_at"])
        s["last_seen"] = max(s["last_seen"], row["created_at"])
        if row["event_type"] == "pageview":
            pageviews += 1
            s["pageviews"] += 1
        elif row["event_type"] == "click":
            clicks += 1
            s["clicks"] += 1
        elif row["event_type"] == "scroll_depth":
            scrolls += 1

    # Which sessions also have a real conversation (chat or voice) — cheap
    # existence check, not a full transcript fetch (see /site/{session_id}).
    session_ids = list(sessions.keys())
    convo_sessions: set[str] = set()
    if session_ids:
        convo_result = (
            sb.table("conversations").select("session_id")
            .in_("session_id", session_ids[:1000]).execute()
        )
        convo_sessions = {r["session_id"] for r in (convo_result.data or []) if r.get("session_id")}

    for sid, s in sessions.items():
        s["has_conversation"] = sid in convo_sessions

    session_list = sorted(sessions.values(), key=lambda s: s["last_seen"], reverse=True)

    return {
        "since": since,
        "totals": {
            "pageviews": pageviews,
            "clicks": clicks,
            "scroll_events": scrolls,
            "unique_sessions": len(sessions),
        },
        "sessions": session_list[:200],
    }


@router.get("/site/{session_id}")
async def site_session_detail(session_id: str, _admin=Depends(require_admin)):
    """
    Full event timeline for one session, plus its conversation transcript
    (chat or voice) if one exists — the point of this endpoint: see IP,
    clicks, scrolls, and what they actually said, together.
    """
    sb = get_supabase_admin()
    events_result = (
        sb.table("site_visits").select("*")
        .eq("session_id", session_id).order("created_at").execute()
    )
    if not events_result.data:
        raise HTTPException(status_code=404, detail="No events for this session")

    convo_result = (
        sb.table("conversations").select("channel, transcript, summary, language, started_at, ended_at")
        .eq("session_id", session_id).maybe_single().execute()
    )
    conversation = convo_result.data if convo_result else None

    return {
        "session_id": session_id,
        "events": events_result.data,
        "conversation": conversation,
    }
