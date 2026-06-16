from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import get_settings
from app.dependencies import get_qdrant, ensure_collection

from app.voice.router import router as voice_router
from app.chat.router import router as chat_router
from app.rag.router import router as rag_router
from app.leads.router import router as leads_router
from app.properties.router import router as properties_router
from app.public.router import router as public_router
from app.assistant.router import router as assistant_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise Qdrant collection
    from app.dependencies import get_settings as gs
    s = gs()
    client = await get_qdrant(s)
    await ensure_collection(client, s)

    os.makedirs("uploads", exist_ok=True)
    yield
    # Shutdown: nothing needed for demo


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
app.include_router(voice_router, prefix="/voice", tags=["voice"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(leads_router, prefix="/leads", tags=["leads"])
app.include_router(properties_router, prefix="/properties", tags=["properties"])


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
        return FileResponse(index)
