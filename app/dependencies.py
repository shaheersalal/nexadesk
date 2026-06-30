from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from supabase import create_client, Client
import openai

from app.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)

# ── Supabase ──────────────────────────────────────────────────────────────────

@lru_cache
def get_supabase_admin(settings: Settings = get_settings()) -> Client:
    """Service-role client for server-side operations (bypasses RLS)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def get_supabase(settings: Annotated[Settings, Depends(get_settings)]) -> Client:
    """Anon client — respects RLS. Use for user-scoped reads."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


# ── Qdrant ────────────────────────────────────────────────────────────────────

_qdrant_client: AsyncQdrantClient | None = None


async def get_qdrant(settings: Annotated[Settings, Depends(get_settings)]) -> AsyncQdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if settings.QDRANT_URL:
            _qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
            )
        else:
            _qdrant_client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )
    return _qdrant_client


async def ensure_collection(client: AsyncQdrantClient, settings: Settings) -> None:
    """Create Qdrant collection if it doesn't exist."""
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.QDRANT_COLLECTION not in names:
        try:
            await client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBED_DIMENSIONS,
                    distance=Distance.COSINE,
                ),
            )
        except UnexpectedResponse as e:
            # Multiple --workers each run this lifespan check concurrently on
            # startup; the losers of the create race hit a 409 here even
            # though the collection now exists, which is not a real failure.
            if e.status_code != 409:
                raise


# ── Redis ─────────────────────────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis(settings: Annotated[Settings, Depends(get_settings)]) -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


# ── LLM (Anthropic/Claude) ────────────────────────────────────────────────────

def get_llm_client(settings: Annotated[Settings, Depends(get_settings)]) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.LLM_API_KEY)


# ── Embeddings (OpenAI-compatible) ───────────────────────────────────────────

def get_embed_client(settings: Annotated[Settings, Depends(get_settings)]) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(api_key=settings.EMBED_API_KEY)


# ── Auth: Supabase JWT verification ──────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    try:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        response = client.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"id": response.user.id, "email": response.user.email}
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def get_company_id(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> str:
    """Resolve company_id from the authenticated user."""
    supabase = get_supabase_admin()
    result = supabase.table("users").select("company_id").eq("id", current_user["id"]).single().execute()
    if not result.data or not result.data.get("company_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not linked to a company")
    return result.data["company_id"]
