"""
Resolves the single company record used by public, unauthenticated demo
surfaces (landing-page chat widget, voice-demo widget) — these aren't
tied to a logged-in user, so there's no company_id to read from a session.

Mirrors the same single-tenant fallback voice/router.py's _resolve_company_id
already uses for the Twilio inbound path: try the named demo company first,
fall back to whichever company exists first.
"""
from app.dependencies import get_supabase_admin

DEMO_COMPANY_NAME = "Palm Elite Properties"


async def resolve_demo_company() -> dict | None:
    sb = get_supabase_admin()
    result = sb.table("companies").select("*").eq("name", DEMO_COMPANY_NAME).limit(1).execute()
    if not result.data:
        result = sb.table("companies").select("*").limit(1).execute()
    return result.data[0] if result.data else None
