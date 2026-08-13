import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
import os

_BOT_UA_FRAGMENTS = [
    "python-requests", "python-httpx", "python-urllib",
    "curl/", "wget/", "scrapy/", "go-http-client",
    "libwww-perl", "java/", "okhttp", "httpie",
]


class BotBlockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ua = request.headers.get("user-agent", "").lower()
        if any(frag in ua for frag in _BOT_UA_FRAGMENTS):
            return Response("Forbidden", status_code=403)
        return await call_next(request)

from app.config import get_settings
from app.dependencies import get_qdrant, ensure_collection

logger = logging.getLogger("nexadesk")

from app.voice.router import router as voice_router
from app.chat.router import router as chat_router
from app.rag.router import router as rag_router
from app.rag.inbound_email import router as inbound_email_router
from app.leads.router import router as leads_router
from app.properties.router import router as properties_router
from app.public.router import router as public_router
from app.assistant.router import router as assistant_router
from app.onboarding.router import router as onboarding_router
from app.admin.router import router as admin_router
from app.companies.router import router as companies_router
from app.pricing.router import router as pricing_router
from app.integrations.router import router as integrations_router
from app.integrations.crm_router import router as crm_router
from app.integrations.api_keys_router import router as api_keys_router
from app.v1.router import router as v1_router
from app.mcp.server import router as mcp_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate required env vars on startup so we fail fast with a clear message
    required = {
        "SUPABASE_URL": settings.SUPABASE_URL,
        "SUPABASE_SERVICE_KEY": settings.SUPABASE_SERVICE_KEY,
        "LLM_API_KEY": settings.LLM_API_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    # Twilio signature validation is skipped entirely when TELEPHONY_AUTH_TOKEN is
    # blank (see app/voice/router.py _validate_twilio). That is fine for local dev
    # but in production it means /voice/inbound and /voice/status accept unsigned
    # requests from anyone, who can then forge calls and drive LLM/TTS spend.
    # Logging an error and booting anyway was not enough — fail hard (AUDIT.md C3).
    if settings.APP_ENV == "production" and not settings.TELEPHONY_AUTH_TOKEN:
        raise RuntimeError(
            "TELEPHONY_AUTH_TOKEN is blank in production. Twilio webhook signature "
            "validation would be disabled, leaving /voice/inbound and /voice/status "
            "open to anyone. Set it in the Railway environment before deploying."
        )

    # Refuse to boot in production with the placeholder secret key — it's
    # public in this repo's source, so leaving it set means anyone can forge
    # signed tokens (sessions, etc.) that the app will trust.
    if settings.APP_ENV == "production" and settings.APP_SECRET_KEY == "change-me-in-production":
        raise RuntimeError(
            "APP_SECRET_KEY is still the default placeholder value in production. "
            "Generate a real secret (e.g. `openssl rand -hex 32`) and set it in your "
            "production environment before starting the app."
        )

    # Startup: initialise Qdrant collection
    client = await get_qdrant(settings)
    await ensure_collection(client, settings)

    # Webhook retry loop — runs every 60s in the background
    async def _retry_loop():
        from app.integrations.events import retry_failed_webhooks
        while True:
            await asyncio.sleep(60)
            try:
                await retry_failed_webhooks()
            except Exception as exc:
                logger.warning("Webhook retry loop error: %s", exc)

    import asyncio
    asyncio.create_task(_retry_loop())

    yield

    # Shutdown: close persistent connections
    from app.dependencies import _qdrant_client, _redis_pool
    if _qdrant_client:
        await _qdrant_client.close()
    if _redis_pool:
        await _redis_pool.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    description=f"{settings.APP_NAME} — AI Receptionist for Real Estate",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://nexadesk.site",
        "https://www.nexadesk.site",
        # Standalone demo app on Vercel — calls /demo/chat and /demo/voice
        # cross-origin now that it no longer proxies through its own API routes.
        "https://nexadesk-1j2y.vercel.app",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# BotBlockMiddleware runs first (last added = outermost in Starlette's stack)
app.add_middleware(BotBlockMiddleware)

# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(public_router, tags=["public"])
app.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(voice_router,      prefix="/voice",       tags=["voice"])
app.include_router(chat_router,       prefix="/chat",        tags=["chat"])
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(inbound_email_router, prefix="/rag", tags=["rag"])
app.include_router(leads_router, prefix="/leads", tags=["leads"])
app.include_router(properties_router, prefix="/properties", tags=["properties"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(companies_router, prefix="/companies", tags=["companies"])
app.include_router(pricing_router, prefix="/pricing", tags=["pricing"])
app.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
app.include_router(crm_router,          prefix="/integrations", tags=["integrations-crm"])
app.include_router(api_keys_router,     prefix="/integrations", tags=["integrations-api-keys"])
app.include_router(v1_router,           prefix="/v1",           tags=["v1"])
app.include_router(mcp_router,          prefix="/mcp",          tags=["mcp"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


# ── Serve React dashboard (production) ───────────────────────────────────────
_dashboard_dist = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")

if os.path.isdir(_dashboard_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dashboard_dist, "assets")), name="assets")

    # Path prefixes owned by the API. A GET that misses every route under one of
    # these is a genuine 404 — returning index.html with HTTP 200 instead made
    # typo'd or removed endpoints look like successful HTML responses, breaking
    # client error handling and hiding routing regressions (AUDIT.md M14).
    _API_PREFIXES = (
        "assistant", "onboarding", "voice", "chat", "rag", "leads",
        "properties", "admin", "companies", "pricing", "integrations", "v1",
        "mcp", "health", "docs", "openapi.json", "redoc",
        "demo", "book-demo",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        first_segment = full_path.split("/", 1)[0]
        if first_segment in _API_PREFIXES:
            raise HTTPException(status_code=404, detail="Not found")
        index = os.path.join(_dashboard_dist, "index.html")
        return FileResponse(index, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
