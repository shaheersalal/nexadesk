import logging
from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool
from jose import jwt, JWTError
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from supabase import create_client, Client
import openai

from app.config import Settings, get_settings

logger = logging.getLogger("nexadesk.deps")
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

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
)


def _verify_jwt_locally(token: str, settings: Settings) -> dict | None:
    """
    Verify a Supabase access token offline using the project JWT secret.

    Returns the claims, or None if SUPABASE_JWT_SECRET is not configured (the
    caller then falls back to remote verification). Raises on an actually
    invalid token.

    This exists because the previous implementation built a fresh synchronous
    Supabase client and made a blocking network call to Supabase Auth on *every
    authenticated request*, stalling the event loop for every other in-flight
    request on the worker (AUDIT.md H1).
    """
    if not settings.SUPABASE_JWT_SECRET:
        return None
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_aud": True},
        )
    except JWTError:
        raise _UNAUTHORIZED


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials

    claims = _verify_jwt_locally(token, settings)
    if claims is not None:
        user_id = claims.get("sub")
        if not user_id:
            raise _UNAUTHORIZED
        return {"id": user_id, "email": claims.get("email")}

    # Fallback: no JWT secret configured — verify against Supabase Auth. Runs in
    # a worker thread so the blocking client cannot stall the event loop.
    def _remote_verify() -> dict:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        response = client.auth.get_user(token)
        if not response.user:
            raise _UNAUTHORIZED
        return {"id": response.user.id, "email": response.user.email}

    try:
        return await run_in_threadpool(_remote_verify)
    except HTTPException:
        raise
    except Exception:
        raise _UNAUTHORIZED


async def get_company_id(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """
    Resolve company_id for the authenticated user.

    Cached in Redis for COMPANY_CACHE_TTL — this mapping changes about once in a
    user's lifetime but was previously re-queried synchronously on every single
    request (AUDIT.md H1).
    """
    user_id = current_user["id"]
    cache_key = f"user_company:{user_id}"

    try:
        redis = await get_redis(settings)
        cached = await redis.get(cache_key)
        if cached:
            return cached
    except Exception as exc:  # Redis down — fall through to the database
        logger.warning("Company cache read failed for %s: %s", user_id, exc)
        redis = None

    def _lookup():
        supabase = get_supabase_admin()
        return (
            supabase.table("users")
            .select("company_id")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )

    result = await run_in_threadpool(_lookup)
    company_id = (result.data or {}).get("company_id") if result else None
    if not company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not linked to a company")

    if redis is not None:
        try:
            await redis.setex(cache_key, settings.COMPANY_CACHE_TTL, company_id)
        except Exception:
            pass  # Caching is an optimisation, never a failure path

    return company_id
