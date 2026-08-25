"""
One shared HTTP client per worker.

Every outbound caller here used to open `async with httpx.AsyncClient(...)` per
request, which builds a connection pool, performs a TCP and TLS handshake, and
throws the connection away on exit. On the voice path that handshake is paid
again for every clause synthesised, and on the chat path for every retrieval —
latency spent before the remote service has read a byte.

A module-level client keeps connections alive between calls. It is created
lazily inside the running event loop rather than at import, because uvicorn
runs one loop per worker and an httpx client binds to the loop it is made on.
"""
import httpx

_CLIENT: httpx.AsyncClient | None = None

# Generous ceiling; individual calls pass their own timeout where they need a
# tighter one (the reranker sits on the critical path and uses 5s).
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=8.0)

_LIMITS = httpx.Limits(max_keepalive_connections=32, max_connections=128)


def client() -> httpx.AsyncClient:
    """The shared client. Never close it — it lives as long as the worker."""
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, limits=_LIMITS)
    return _CLIENT


async def aclose() -> None:
    """Close the shared client. Called from the app's lifespan shutdown."""
    global _CLIENT
    if _CLIENT is not None and not _CLIENT.is_closed:
        await _CLIENT.aclose()
    _CLIENT = None
