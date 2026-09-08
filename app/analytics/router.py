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
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.admin.router import require_admin
from app.dependencies import get_supabase_admin
from app.shared import session_store
from app.shared.net import get_client_ip
from app.shared.notify import send_visitor_digest_email

logger = logging.getLogger("nexadesk.analytics")
router = APIRouter()

TRACK_RATE_WINDOW = 60   # seconds
TRACK_RATE_MAX = 60      # requests per IP per window — generous, these are cheap beacons
SESSION_END_RATE_WINDOW = 60
SESSION_END_RATE_MAX = 10

# How long to wait before compiling a finished visit. The page fires its
# queued /track batch and this session-end beacon at the same moment on
# pagehide, and nothing orders them - so reading the events immediately can
# miss the visitor's last clicks and scroll depth.
DIGEST_SETTLE_SECONDS = 5

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

    live_fetch_result = (
        sb.table("site_live_fetches").select("url, scraped_excerpt, phone, created_at")
        .eq("session_id", session_id).order("created_at", desc=True).execute()
    )
    live_fetches = live_fetch_result.data or []

    # A phone-audition call's own conversation is keyed by call_sid, not this
    # browser session_id (see _find_voice_conversation) - if the plain lookup
    # above found nothing, try via the phone number this session entered.
    if not conversation and live_fetches:
        phone = next((lf.get("phone") for lf in live_fetches if lf.get("phone")), None)
        if phone:
            since_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            conversation = _find_voice_conversation(sb, phone, since_iso)

    review_result = (
        sb.table("site_reviews").select("stars, review_text, email, created_at")
        .eq("session_id", session_id).order("created_at", desc=True).execute()
    )

    return {
        "session_id": session_id,
        "events": events_result.data,
        "conversation": conversation,
        "live_fetches": live_fetches,
        "reviews": review_result.data or [],
    }


@router.get("/visitors")
async def visitors(
    site: Optional[Literal["shaheer_dev", "nexadesk_site"]] = None,
    _admin=Depends(require_admin),
):
    """
    One row per (site, ip_address) - a returning IP shows its full
    visit_dates history on one row instead of appearing as a separate log
    entry per visit (see site_session.py::session_end for the upsert).
    """
    sb = get_supabase_admin()
    q = sb.table("site_visitors").select("*").order("last_seen", desc=True).limit(500)
    if site:
        q = q.eq("site", site)
    result = q.execute()
    return {"visitors": result.data or []}


class ReviewRequest(BaseModel):
    site: Literal["shaheer_dev", "nexadesk_site"]
    session_id: str = Field(..., min_length=1, max_length=200)
    stars: Optional[int] = Field(None, ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)
    email: Optional[str] = Field(None, max_length=320)


@router.post("/review")
async def submit_review(body: ReviewRequest, request: Request):
    """The optional review/email box on shaheer.dev's audition section."""
    try:
        sb = get_supabase_admin()
        sb.table("site_reviews").insert({
            "site": body.site,
            "session_id": body.session_id,
            "ip_address": get_client_ip(request),
            "stars": body.stars,
            "review_text": body.review_text,
            "email": body.email,
        }).execute()
    except Exception as exc:
        logger.warning("site_reviews insert failed: %s", exc)
        return {"saved": False}
    return {"saved": True}


class SessionEndRequest(BaseModel):
    site: Literal["shaheer_dev", "nexadesk_site"]
    session_id: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=32)


def _find_voice_conversation(sb, phone: str, since_iso: str) -> Optional[dict]:
    """
    A voice call's `conversations.session_id` is the Twilio call_sid, which
    the browser never sees — so a phone-audition call can't be joined by
    session_id the way a chat conversation can. The only thread connecting
    "the visitor who typed this phone number into the web form" to "the call
    that number made" is the phone number itself, via the lead it produced
    (app/voice/router.py::_finalize_call always sets leads.phone, falling
    back to caller ID when nothing else was said).
    """
    lead_res = (
        sb.table("leads").select("id").eq("phone", phone)
        .order("created_at", desc=True).limit(1).execute()
    )
    if not lead_res.data:
        return None
    lead_id = lead_res.data[0]["id"]
    convo_res = (
        sb.table("conversations").select("channel, transcript, started_at, ended_at")
        .eq("lead_id", lead_id).eq("channel", "voice")
        .gte("started_at", since_iso).order("started_at", desc=True).limit(1).execute()
    )
    return convo_res.data[0] if convo_res.data else None


@router.post("/session-end")
async def session_end(body: SessionEndRequest, request: Request):
    """
    Fired via navigator.sendBeacon when a visitor leaves (see
    lib/analytics.js::finalizeSession in shaheer-dev-next). Compiles
    everything known about this visit - clicks, scroll depth, any URL they
    auditioned, any resulting call/chat transcript, any review or email left
    - upserts the (site, ip) visitor identity so a returning IP accumulates
    visit dates instead of becoming a new log entry, and emails the owner.

    Best-effort throughout: sendBeacon has no response the page can react
    to, and a tracking failure must never be visible to the visitor.
    """
    ip = get_client_ip(request)
    try:
        count = await session_store.incr(f"session_end_rate:{ip}", SESSION_END_RATE_WINDOW)
        if count > SESSION_END_RATE_MAX:
            return {"logged": False}
    except Exception:
        pass

    # Compile and send in the background, after a short settle. On pagehide the
    # page fires two independent beacons - the queued /track batch and this one
    # - with no ordering guarantee between them, and the last one loses. A real
    # visit on 2026-09-08 emailed "Pageviews 1" and no clicks while two click
    # events landed 4s later, because the digest was compiled first. Waiting
    # lets the final batch arrive before we read the events back.
    asyncio.create_task(_compile_and_send_digest(body, ip))
    return {"logged": True}


async def _compile_and_send_digest(body: "SessionEndRequest", ip: str) -> None:
    """Gather everything known about a finished visit, then email it."""
    await asyncio.sleep(DIGEST_SETTLE_SECONDS)
    sb = get_supabase_admin()

    try:
        events = (
            sb.table("site_visits")
            .select("event_type, path, event_data, referrer, user_agent, created_at")
            .eq("session_id", body.session_id).order("created_at").execute()
        ).data or []
    except Exception:
        events = []

    clicks = [e for e in events if e["event_type"] == "click"]
    scrolls = [e for e in events if e["event_type"] == "scroll_depth"]
    pageviews = [e for e in events if e["event_type"] == "pageview"]
    max_scroll = max((e["event_data"].get("depth_pct", 0) for e in scrolls), default=0)
    referrer = next((e["referrer"] for e in events if e.get("referrer")), "")
    user_agent = next((e["user_agent"] for e in events if e.get("user_agent")), "")

    live_fetch = None
    try:
        result = (
            sb.table("site_live_fetches").select("url, scraped_excerpt, phone, created_at")
            .eq("site", body.site).eq("session_id", body.session_id)
            .order("created_at", desc=True).limit(1).execute()
        )
        if result.data:
            live_fetch = result.data[0]
        elif body.phone:
            result = (
                sb.table("site_live_fetches").select("url, scraped_excerpt, phone, created_at")
                .eq("site", body.site).eq("phone", body.phone)
                .order("created_at", desc=True).limit(1).execute()
            )
            if result.data:
                live_fetch = result.data[0]
    except Exception:
        pass

    conversation = None
    try:
        convo_res = (
            sb.table("conversations").select("channel, transcript, started_at, ended_at")
            .eq("session_id", body.session_id).maybe_single().execute()
        )
        conversation = convo_res.data if convo_res else None
    except Exception:
        pass
    if not conversation and body.phone:
        try:
            since_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            conversation = _find_voice_conversation(sb, body.phone, since_iso)
        except Exception:
            pass

    review = None
    try:
        result = (
            sb.table("site_reviews").select("stars, review_text, email, created_at")
            .eq("session_id", body.session_id).order("created_at", desc=True).limit(1).execute()
        )
        if result.data:
            review = result.data[0]
    except Exception:
        pass

    # Upsert the (site, ip) visitor identity - the whole point being that a
    # returning IP accumulates dates on ONE row instead of becoming a new
    # log entry every time.
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    existing_row = None
    try:
        existing = (
            # Whole row, not a subset: keep() below falls back to the stored
            # value for every field it might otherwise null out, so anything
            # left unselected here would silently fail to be preserved.
            sb.table("site_visitors").select("*")
            .eq("site", body.site).eq("ip_address", ip).maybe_single().execute()
        )
        existing_row = existing.data if existing else None
    except Exception:
        pass

    prior_dates = list((existing_row or {}).get("visit_dates") or [])
    visit_dates = prior_dates if today in prior_dates else prior_dates + [today]
    session_count = ((existing_row or {}).get("session_count") or 0) + 1

    prior = existing_row or {}

    def keep(new_value, field: str):
        """
        Never let a later, emptier visit erase what an earlier one learned.

        This row is a rolling summary per IP, so a returning visitor who just
        bounces off the page would otherwise null out the URL they auditioned,
        the review they left, and their email - i.e. exactly the lead detail
        the dashboard exists to show. The per-session tables keep the full
        history either way; this only governs the summary.
        """
        return new_value if new_value not in (None, "") else prior.get(field)

    visitor_row = {
        "site": body.site,
        "ip_address": ip,
        "last_seen": now.isoformat(),
        "visit_dates": visit_dates,
        "session_count": session_count,
        "last_session_id": body.session_id,
        "last_entered_url": keep((live_fetch or {}).get("url"), "last_entered_url"),
        "last_scraped_excerpt": keep((live_fetch or {}).get("scraped_excerpt"), "last_scraped_excerpt"),
        "email": keep((review or {}).get("email"), "email"),
        "last_review_stars": keep((review or {}).get("stars"), "last_review_stars"),
        "last_review_text": keep((review or {}).get("review_text"), "last_review_text"),
        "notified_at": now.isoformat(),
    }
    try:
        sb.table("site_visitors").upsert(visitor_row, on_conflict="site,ip_address").execute()
    except Exception as exc:
        logger.warning("site_visitors upsert failed: %s", exc)

    await send_visitor_digest_email({
        "site": body.site,
        "ip": ip,
        "session_id": body.session_id,
        "pageviews": len(pageviews),
        "clicks": len(clicks),
        "max_scroll_pct": max_scroll,
        "referrer": referrer,
        "user_agent": user_agent,
        "live_fetch": live_fetch,
        "conversation": conversation,
        "review": review,
        "prior_visit_dates": [d for d in prior_dates if d != today],
    })
