"""
Resolves the single company record used by public, unauthenticated demo
surfaces (landing-page chat widget, voice-demo widget) — these aren't
tied to a logged-in user, so there's no company_id to read from a session.

Mirrors the same single-tenant fallback voice/router.py's _resolve_company_id
already uses for the Twilio inbound path: try the named demo company first,
fall back to whichever company exists first.
"""
import asyncio
import logging
import time

from app.dependencies import get_supabase_admin

logger = logging.getLogger("nexadesk.demo_company")

DEMO_COMPANY_NAME = "Pinnacle Property Management"

_cache: dict | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 300  # 5 minutes


def _fetch_sync() -> dict | None:
    """Synchronous Supabase fetch — runs in executor so it never blocks the event loop."""
    sb = get_supabase_admin()
    result = sb.table("companies").select("*").eq("name", DEMO_COMPANY_NAME).limit(1).execute()
    if not result.data:
        result = sb.table("companies").select("*").limit(1).execute()
    return result.data[0] if result.data else None


async def resolve_demo_company() -> dict | None:
    global _cache, _cache_ts

    if _cache and (time.monotonic() - _cache_ts) < _CACHE_TTL:
        return _cache

    loop = asyncio.get_running_loop()
    for attempt in range(3):
        try:
            company = await loop.run_in_executor(None, _fetch_sync)
            if company:
                _cache = company
                _cache_ts = time.monotonic()
                print(f"[demo_company] resolved: {company.get('name')}", flush=True)
                return company
            print(f"[demo_company] attempt {attempt + 1}: companies table empty", flush=True)
        except Exception as e:
            print(f"[demo_company] attempt {attempt + 1} failed: {type(e).__name__}: {e}", flush=True)
        if attempt < 2:
            await asyncio.sleep(1)

    print("[demo_company] all 3 attempts failed, returning None", flush=True)
    return None
