"""
Redis-backed key/value helper for state that must survive across the
multiple uvicorn worker processes (docker-compose runs --workers 4, each
with its own memory space — a plain module-level dict is invisible to
the other 3 workers).
"""
import json
from typing import Any

from app.dependencies import get_redis
from app.config import get_settings

settings = get_settings()


async def get_json(key: str) -> Any | None:
    redis = await get_redis(settings)
    raw = await redis.get(key)
    return json.loads(raw) if raw is not None else None


async def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    redis = await get_redis(settings)
    await redis.set(key, json.dumps(value), ex=ttl_seconds)


async def delete(key: str) -> None:
    redis = await get_redis(settings)
    await redis.delete(key)


async def incr(key: str, ttl_seconds: int) -> int:
    """Increment an integer counter, setting its TTL on first creation."""
    redis = await get_redis(settings)
    value = await redis.incr(key)
    if value == 1:
        await redis.expire(key, ttl_seconds)
    return value
