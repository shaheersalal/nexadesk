"""
Tests for app/rag/live_fetch.py — the ephemeral per-session URL context used
by the ai_studio audition flow.

The SSRF guard is the security-critical part: this module fetches whatever
URL a public, unauthenticated visitor types in, so it must never be usable
to reach internal infrastructure (localhost, RFC1918 ranges, link-local /
cloud metadata addresses).
"""
import pytest

from app.rag.live_fetch import (
    _is_blocked_ip,
    _normalize_url,
    _resolve_and_check,
    LiveFetchError,
    store_live_context,
    get_live_context,
    clear_live_context,
)


# ── SSRF guard: IP classification ─────────────────────────────────────────────

@pytest.mark.parametrize("ip", [
    "127.0.0.1",        # loopback
    "10.0.0.5",          # RFC1918
    "172.16.0.1",        # RFC1918
    "192.168.1.1",       # RFC1918
    "169.254.169.254",   # link-local / cloud metadata
    "0.0.0.0",            # unspecified
    "::1",                # IPv6 loopback
])
def test_blocks_internal_and_metadata_ips(ip):
    assert _is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "1.1.1.1"])
def test_allows_ordinary_public_ips(ip):
    assert _is_blocked_ip(ip) is False


def test_unparseable_ip_is_blocked_not_ignored():
    """Refuse rather than silently let something through on a parse failure."""
    assert _is_blocked_ip("not-an-ip") is True


# ── URL normalisation ──────────────────────────────────────────────────────────

def test_bare_domain_gets_https_scheme():
    assert _normalize_url("example.com").startswith("https://")


def test_rejects_non_http_schemes():
    with pytest.raises(LiveFetchError):
        _normalize_url("file:///etc/passwd")
    with pytest.raises(LiveFetchError):
        _normalize_url("javascript:alert(1)")
    with pytest.raises(LiveFetchError):
        _normalize_url("gopher://internal:70/")


def test_rejects_url_with_no_host():
    with pytest.raises(LiveFetchError):
        _normalize_url("https:///path-only")


# ── Hostname resolution guard ──────────────────────────────────────────────────

def test_blocks_localhost_by_name():
    with pytest.raises(LiveFetchError):
        _resolve_and_check("localhost")


def test_blocks_cloud_metadata_hostname():
    with pytest.raises(LiveFetchError):
        _resolve_and_check("metadata.google.internal")


def test_rejects_empty_hostname():
    with pytest.raises(LiveFetchError):
        _resolve_and_check("")


def test_blocks_hostname_that_resolves_internally(monkeypatch):
    """
    The real SSRF case: a public-looking hostname that resolves to a private
    address (DNS rebinding, or an internal-only domain). Resolution itself
    must be checked, not just the literal string typed in.
    """
    import app.rag.live_fetch as live_fetch

    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("10.0.0.1", 0))]

    monkeypatch.setattr(live_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(LiveFetchError):
        live_fetch._resolve_and_check("looks-public.example.com")


def test_allows_hostname_that_resolves_publicly(monkeypatch):
    import app.rag.live_fetch as live_fetch

    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("93.184.216.34", 0))]

    monkeypatch.setattr(live_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    live_fetch._resolve_and_check("example.com")  # must not raise


# ── Ephemeral storage round-trip ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_get_clear_round_trip(monkeypatch, fake_redis):
    import app.rag.live_fetch as live_fetch

    async def fake_get_redis(settings):
        return fake_redis

    monkeypatch.setattr(live_fetch, "get_redis", fake_get_redis)

    assert await get_live_context("session-1") is None

    await store_live_context("session-1", "https://example.com", "some page text")
    assert await get_live_context("session-1") == "some page text"

    # A different key must not see this session's content.
    assert await get_live_context("session-2") is None

    await clear_live_context("session-1")
    assert await get_live_context("session-1") is None


@pytest.mark.asyncio
async def test_corrupt_payload_is_dropped_not_raised(monkeypatch, fake_redis):
    import app.rag.live_fetch as live_fetch

    async def fake_get_redis(settings):
        return fake_redis

    monkeypatch.setattr(live_fetch, "get_redis", fake_get_redis)

    await fake_redis.set(f"{live_fetch._REDIS_PREFIX}session-x", "not valid json")
    assert await get_live_context("session-x") is None
