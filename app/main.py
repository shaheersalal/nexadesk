import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

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

    # Twilio signature validation is skipped entirely when TELEPHONY_AUTH_TOKEN is blank
    # (see app/voice/router.py _validate_twilio) — fine for local dev, a silent webhook
    # spoofing risk if ever blank in production.
    if settings.APP_ENV == "production" and not settings.TELEPHONY_AUTH_TOKEN:
        logger.error(
            "TELEPHONY_AUTH_TOKEN is blank in production — Twilio webhook signature "
            "validation is DISABLED, voice webhooks accept unsigned requests from anyone."
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

    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(public_router, tags=["public"])
app.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(voice_router, prefix="/voice", tags=["voice"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(inbound_email_router, prefix="/rag", tags=["rag"])
app.include_router(leads_router, prefix="/leads", tags=["leads"])
app.include_router(properties_router, prefix="/properties", tags=["properties"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(companies_router, prefix="/companies", tags=["companies"])
app.include_router(pricing_router, prefix="/pricing", tags=["pricing"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


# ── Serve React dashboard (production) ───────────────────────────────────────
_dashboard_dist = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")

if os.path.isdir(_dashboard_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dashboard_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = os.path.join(_dashboard_dist, "index.html")
        return FileResponse(index, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
