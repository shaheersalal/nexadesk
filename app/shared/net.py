"""Shared request-level helpers used by more than one public router."""
from fastapi import Request

from app.config import get_settings


def get_client_ip(request: Request) -> str:
    """
    Best-effort client IP for rate limiting.

    Forwarded headers are only honoured when TRUST_PROXY_HEADERS is set,
    because they are trivially forged otherwise: `curl -H "CF-Connecting-IP:
    <random>"` yields a fresh throttle bucket on every request, which
    nullified every rate limit that used to trust them (AUDIT.md M5).

    Enable it only when the app genuinely sits behind a proxy that overwrites
    these headers. Railway's edge does not, so the default is off and we use
    the real socket peer.
    """
    if get_settings().TRUST_PROXY_HEADERS:
        cf = request.headers.get("CF-Connecting-IP")
        if cf:
            return cf.strip()
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return (request.client.host if request.client else None) or "unknown"
