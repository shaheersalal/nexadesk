"""
Shared test fixtures.

Everything external is faked. These tests are about *our* logic — tenant
isolation, auth boundaries, input handling — not about whether Supabase or
Deepgram work, so nothing here touches the network.
"""
import os

import pytest

# Must be set before app.config is imported, since Settings reads the
# environment at class definition time.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "placeholder-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "placeholder-anon-key")
os.environ.setdefault("LLM_API_KEY", "placeholder-llm-key")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production")


@pytest.fixture
def settings():
    from app.config import get_settings
    get_settings.cache_clear()
    return get_settings()


class FakeRedis:
    """
    In-memory stand-in for the bits of redis.asyncio we actually use.

    Only implements what the code under test calls; anything else should fail
    loudly rather than silently pretending to work.
    """

    def __init__(self):
        self.store: dict[str, str] = {}
        self.expiries: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        if ex:
            self.expiries[key] = ex
        return True

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.expiries[key] = ttl
        return True

    async def getdel(self, key):
        return self.store.pop(key, None)

    async def delete(self, key):
        self.store.pop(key, None)

    async def incr(self, key):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key, ttl):
        self.expiries[key] = ttl
        return True


@pytest.fixture
def fake_redis():
    return FakeRedis()
