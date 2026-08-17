"""
JWKS fetching and caching for Supabase access-token verification.

Supabase projects now sign access tokens asymmetrically (ES256) and publish the
public keys at `/auth/v1/.well-known/jwks.json`. Verifying against those keys
means the server never holds a signing secret and never has to call Supabase
Auth to check a token.

Older projects use a shared HS256 secret. Both are supported — see
`app/dependencies.py` — because a project mid-migration can hand out tokens
signed either way.
"""
import logging
import time

import httpx

logger = logging.getLogger("nexadesk.jwks")

# kid -> JWK dict, plus the timestamp of the fetch that produced it.
_cache: dict[str, dict] = {}
_fetched_at: float = 0.0


async def get_signing_key(kid: str, jwks_url: str, ttl: int = 3600) -> dict | None:
    """
    Return the JWK matching `kid`, fetching the key set if needed.

    Refetches when the cache is stale, and also on an unknown `kid` — that is
    the signal a key was rotated, and waiting out the TTL would reject every
    valid token until it expired.
    """
    global _fetched_at

    if not jwks_url:
        return None

    fresh = (time.monotonic() - _fetched_at) < ttl
    if fresh and kid in _cache:
        return _cache[kid]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(jwks_url)
        response.raise_for_status()
        keys = response.json().get("keys", [])
    except Exception as exc:
        logger.warning("JWKS fetch failed from %s: %s", jwks_url, exc)
        # Serve a stale key rather than rejecting everyone during an outage.
        return _cache.get(kid)

    _cache.clear()
    for key in keys:
        if key.get("kid"):
            _cache[key["kid"]] = key
    _fetched_at = time.monotonic()

    if kid not in _cache:
        logger.warning("kid %s not present in JWKS (%d key(s) available)", kid, len(_cache))
    return _cache.get(kid)


def reset_cache() -> None:
    """Test hook."""
    global _fetched_at
    _cache.clear()
    _fetched_at = 0.0
