import html
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import redis.asyncio as aioredis

from app.config import get_settings
from app.dependencies import get_supabase_admin, get_current_user, get_redis
from app.admin.invite_token import consume_invite_token

ADMIN_UID = "7227a933-56ef-45c4-8cbc-1c8331c74b21"

router = APIRouter()


def require_admin(user=Depends(get_current_user)):
    if user["id"] != ADMIN_UID:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/requests")
async def list_requests(_=Depends(require_admin)):
    sb = get_supabase_admin()
    result = sb.table("demo_requests").select("*").order("created_at", desc=True).execute()
    return result.data or []


class InviteBody(BaseModel):
    request_id: str
    email: str
    name: str


def _html(title, body_html, color="#34d399"):
    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0f1f3d}}
.box{{background:#fff;border-radius:16px;padding:40px 48px;max-width:420px;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.3)}}
h2{{color:#1e3a5f;margin-bottom:8px}} p{{color:#64748b;font-size:15px}}
.dot{{width:48px;height:48px;border-radius:50%;background:{color};display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:24px}}</style>
</head><body><div class="box"><div class="dot">{'✓' if color=='#34d399' else '✗'}</div>
<h2>{title}</h2>{body_html}</div></body></html>""")


@router.get("/invite-quick", include_in_schema=False)
async def invite_quick(token: str, redis: aioredis.Redis = Depends(get_redis)):
    """
    One-click activation from the demo-request notification email.

    Identity comes entirely from the single-use token (AUDIT.md C2) — request_id
    and email are read from the Redis payload, never from query parameters, so
    a link cannot be edited to invite a different address.
    """
    payload = await consume_invite_token(redis, token.strip())
    if not payload:
        return _html(
            "Link expired",
            "<p>This activation link is invalid, has expired, or has already been used.</p>",
            "#f87171",
        )

    request_id = payload["request_id"]
    email = payload["email"]
    name = payload["name"]

    sb = get_supabase_admin()
    try:
        req_row = sb.table("demo_requests").select("*").eq("id", request_id).maybe_single().execute()
        meta = {"full_name": name}
        if req_row.data:
            r = req_row.data
            meta.update({
                "agency_name":   r.get("agency_name", ""),
                "phone":         r.get("phone", ""),
                "country":       r.get("country", ""),
                "monthly_calls": r.get("monthly_calls", ""),
            })
        sb.auth.admin.invite_user_by_email(
            email,
            options={"data": meta, "redirect_to": "https://nexadesk.site/setup"},
        )
    except Exception as e:
        err = str(e)
        # Escape before interpolating: name/email originate from a public form
        # and would otherwise inject markup into this admin-facing page.
        safe_name, safe_email = html.escape(name), html.escape(email)
        if "already been invited" in err.lower() or "already registered" in err.lower():
            return _html("Already invited", f"<p>{safe_name} ({safe_email}) was already sent an invite.</p>", "#fbbf24")
        return _html("Error", f"<p>{html.escape(err)}</p>", "#f87171")

    sb.table("demo_requests").update({"status": "invited"}).eq("id", request_id).execute()
    return _html("Invite sent!", f"<p>An account activation email has been sent to <strong>{html.escape(email)}</strong>.<br><br>They'll set their password and land on the onboarding page.</p>")


@router.post("/invite")
async def invite_user(body: InviteBody, _=Depends(require_admin)):
    sb = get_supabase_admin()
    try:
        sb.auth.admin.invite_user_by_email(
            body.email,
            options={"data": {"full_name": body.name}, "redirect_to": "https://nexadesk.site/setup"},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    sb.table("demo_requests").update({"status": "invited"}).eq("id", body.request_id).execute()
    return {"status": "invited"}
