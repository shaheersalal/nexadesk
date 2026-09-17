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


# ── Phone-key normalisation ──────────────────────────────────────────────────
#
# Regression cover for a live incident: a caller loaded their site on the web
# form, saw "Loaded", then rang the number and the assistant knew nothing about
# it. The browser had stored the page under what the visitor typed
# ("0331 2228870") while the voice path looked it up under Twilio's E.164
# `From` ("+923312228870"), so the exact-match lookup never hit and the call
# silently behaved as though no URL had been given.


def test_phone_key_agrees_across_every_format_a_visitor_might_type():
    from app.rag.live_fetch import phone_key

    typed_locally = phone_key("0331 2228870")
    typed_international = phone_key("+92 331 2228870")
    what_twilio_sends = phone_key("+923312228870")

    assert typed_locally == typed_international == what_twilio_sends

    # US, formatted the way a person writes it vs the way Twilio sends it.
    assert phone_key("(781) 365-5768") == phone_key("+17813655768")


def test_phone_key_separates_genuinely_different_numbers():
    from app.rag.live_fetch import phone_key

    assert phone_key("+923312228870") != phone_key("+17813655768")


def test_phone_key_handles_empty_input():
    from app.rag.live_fetch import phone_key

    assert phone_key("") == "phone:unknown"
    assert phone_key(None) == "phone:unknown"


def test_session_ids_are_not_mistaken_for_phone_numbers():
    """
    The live-context endpoint derives a phone key from `key` when it looks like
    a phone number, so a chat session id must never be misread as one - that
    would write junk phone keys an inbound call could collide with.
    """
    from app.chat.router import _looks_like_phone

    assert _looks_like_phone("03312228870")
    assert _looks_like_phone("+92 331 2228870")
    assert _looks_like_phone("(781) 365-5768")

    assert not _looks_like_phone("f0c6455e-3420-49e9-8c60-b932465231f8")
    assert not _looks_like_phone("form-cto-test-1")
    assert not _looks_like_phone("audition-test-1788458945")


# ── Unreadable pages and the reader fallback ─────────────────────────────────
#
# A plain GET reads nothing from sites built in JavaScript and gets a bot wall
# from protected ones. zameen.com's fetch returned only its <title> and was
# reported to the visitor as "Loaded", handing the assistant nothing.

LONG_PAGE = "We build custom dental clinic websites and booking systems. " * 10


def test_title_only_and_bot_walls_are_unreadable():
    from app.rag.live_fetch import _looks_unreadable

    assert _looks_unreadable("Buy, Sell and Rent Property in Pakistan | Zameen.com")
    assert _looks_unreadable(
        "Title: Security check | Bayut\n\nURL Source: https://www.bayut.com/\n\n"
        "Markdown Content: please wait while we check your connection."
    )
    assert not _looks_unreadable(LONG_PAGE)


def test_a_long_real_page_mentioning_captcha_is_not_a_bot_wall():
    from app.rag.live_fetch import _looks_unreadable

    assert not _looks_unreadable(LONG_PAGE * 5 + " Contact form protected by reCAPTCHA.")


def _patch_fetchers(monkeypatch, direct, reader):
    import app.rag.live_fetch as live_fetch

    monkeypatch.setattr(live_fetch, "_resolve_and_check", lambda host: None)
    monkeypatch.setattr(live_fetch, "_fetch_direct", direct)
    monkeypatch.setattr(live_fetch, "_fetch_via_reader", reader)
    return live_fetch


@pytest.mark.asyncio
async def test_readable_direct_page_never_calls_the_reader(monkeypatch):
    async def direct(url):
        return "https://clinic.example/", LONG_PAGE

    async def reader(url):
        raise AssertionError("reader must not be called for a readable page")

    live_fetch = _patch_fetchers(monkeypatch, direct, reader)
    final_url, text = await live_fetch.fetch_page_text("clinic.example")
    assert final_url == "https://clinic.example/"
    assert text == LONG_PAGE


@pytest.mark.asyncio
async def test_empty_javascript_shell_falls_back_to_the_reader(monkeypatch):
    async def direct(url):
        return "https://clinic.example/", "Clinic"

    async def reader(url):
        return LONG_PAGE

    live_fetch = _patch_fetchers(monkeypatch, direct, reader)
    _, text = await live_fetch.fetch_page_text("clinic.example")
    assert text == LONG_PAGE


@pytest.mark.asyncio
async def test_blocked_everywhere_raises_an_honest_error(monkeypatch):
    import httpx

    async def direct(url):
        raise httpx.ConnectError("503 bot protection")

    async def reader(url):
        return "Title: Security check | Example"

    live_fetch = _patch_fetchers(monkeypatch, direct, reader)
    with pytest.raises(LiveFetchError, match="block automated readers"):
        await live_fetch.fetch_page_text("protected.example")


@pytest.mark.asyncio
async def test_internal_redirect_is_refused_not_retried_through_the_reader(monkeypatch):
    async def direct(url):
        raise LiveFetchError("That URL points somewhere internal - not supported.")

    async def reader(url):
        raise AssertionError("an SSRF refusal must never be retried")

    live_fetch = _patch_fetchers(monkeypatch, direct, reader)
    with pytest.raises(LiveFetchError, match="internal"):
        await live_fetch.fetch_page_text("rebinding.example")


@pytest.mark.asyncio
async def test_adding_a_phone_reuses_the_page_already_loaded(monkeypatch):
    """The phone step must not fetch the site again: slow, and a second chance to fail."""
    import app.chat.router as chat_router
    from starlette.requests import Request
    from app.rag.live_fetch import phone_key

    stored = {}

    async def fake_entry(key):
        if key == "sess-1":
            return {"url": "https://clinic.example/", "text": LONG_PAGE, "source": "clinic.example"}
        return None

    async def no_fetch(url):
        raise AssertionError("the page was already loaded for this session")

    async def fake_store(key, url, text, source=None):
        stored[key] = (url, text, source)

    def no_db():
        raise RuntimeError("no database in tests")

    monkeypatch.setattr(chat_router, "get_live_context_entry", fake_entry)
    monkeypatch.setattr(chat_router, "fetch_page_text", no_fetch)
    monkeypatch.setattr(chat_router, "store_live_context", fake_store)
    monkeypatch.setattr(chat_router, "get_supabase_admin", no_db)

    body = chat_router.LiveContextRequest(
        key="+971501234567", url="clinic.example", session_id="sess-1", phone="+971501234567",
    )
    request = Request({"type": "http", "headers": [], "client": ("1.2.3.4", 0)})
    result = await chat_router.set_live_context(body, request)

    assert result["url"] == "https://clinic.example/"
    assert stored[phone_key("+971501234567")][1] == LONG_PAGE
