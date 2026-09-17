"""
Ephemeral, per-session "live" context — Part 2 of the two-part ai_studio
knowledge base (Part 1 is the permanent seed_knowledge_shaheer/ ingestion,
see scripts/seed_shaheer_knowledge.py and app/shared/verticals.py).

A visitor pastes their own site's URL. That page's text is fetched once and
stuffed directly into the conversation's system prompt for exactly this
session — not chunked, not embedded, not written to Qdrant or the
`documents` table. A single company page (tens of KB) doesn't need vector
search, and unlike the permanent knowledge base, this content must not
outlive the conversation: it's deleted the moment the call/chat ends
(app/voice/router.py::_finalize_call, app/chat/router.py session-end), with
a short Redis TTL as a backstop for anyone who abandons the tab or call.

Storage is keyed generically, not by company: a chat session uses its
session_id; a phone call has no call_sid until Twilio answers, so it's keyed
by the caller's own number instead (captured on the web step before they
dial in — see app/voice/router.py's use of session.caller_number).

The fetched text is attacker-influenced content by construction — a visitor
could point this at a page containing "ignore previous instructions". It is
never treated as instructions by this module; app/shared/verticals.py wraps
it in an explicitly labelled, untrusted context block before it ever reaches
a prompt, per HARD RULE 1 in every vertical's system prompt template.
"""
import ipaddress
import json
import logging
import re
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.dependencies import get_redis

logger = logging.getLogger("nexadesk.live_fetch")

_REDIS_PREFIX = "live_fetch:"
_TTL_SECONDS = 900  # 15 min safety net — real deletion is event-driven, not timer-driven
_MAX_RESPONSE_BYTES = 300_000
_MAX_CONTEXT_CHARS = 20_000  # keeps the prompt bounded regardless of source page size
_FETCH_TIMEOUT = 8.0

# Jina Reader renders the page in a real browser on Jina's side. Measured at
# 5-15s, so it is only the fallback for pages the plain fetch can't read.
_READER_URL = "https://r.jina.ai/"
_READER_TIMEOUT = 30.0

# Below this a "page" is a title tag or an empty JavaScript shell, not content:
# zameen.com's plain fetch returned only its 52-character <title>.
_MIN_TEXT_CHARS = 100

# Bot walls are short pages; only look for these in short text so a real page
# that mentions "captcha" in its contact form isn't rejected.
_BOT_WALL_MAX_CHARS = 1500
_BOT_WALL_MARKERS = (
    "security check", "just a moment", "access denied", "attention required",
    "verify you are human", "checking your browser", "enable javascript",
    "are you a robot", "captcha", "request blocked", "unusual traffic",
)

_UNREADABLE_MESSAGE = (
    "Couldn't read that site - it may block automated readers. "
    "Try a specific page, like your About or Services page."
)

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


class LiveFetchError(Exception):
    """
    Raised for any reason a URL can't be safely fetched. Callers turn this
    into a plain, honest reply ("couldn't read that page") — never into
    fabricated content, and never surfaced to the LLM as if it were real
    retrieved context.
    """


def _is_blocked_ip(ip: str) -> bool:
    """SSRF guard: refuse anything that isn't a normal public address."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable — refuse rather than guess
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _resolve_and_check(hostname: str) -> None:
    if not hostname or hostname.lower() in _BLOCKED_HOSTNAMES:
        raise LiveFetchError("That URL isn't reachable.")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise LiveFetchError("Couldn't resolve that domain.") from exc
    if any(_is_blocked_ip(info[4][0]) for info in infos):
        raise LiveFetchError("That URL points somewhere internal - not supported.")


_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _normalize_url(url: str) -> str:
    """
    Bare domains ("example.com") get https:// assumed. Anything that already
    looks like `scheme:...` is left alone and validated as-is — checking for
    a literal "://" instead of a real scheme prefix would let a schemeless-
    looking string like "javascript:alert(1)" (no "//") slip through the
    "no scheme, assume https" branch and never hit the scheme check at all.
    """
    url = url.strip()
    if not _SCHEME_RE.match(url):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LiveFetchError("Only http/https URLs are supported.")
    if not parsed.hostname:
        raise LiveFetchError("That doesn't look like a valid URL.")
    return parsed.geturl()


def _strip_html(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _looks_unreadable(text: str) -> bool:
    """An empty shell or a bot wall rather than the visitor's actual content."""
    if len(text) < _MIN_TEXT_CHARS:
        return True
    if len(text) >= _BOT_WALL_MAX_CHARS:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _BOT_WALL_MARKERS)


async def _fetch_direct(safe_url: str) -> tuple[str, str]:
    """Plain GET. Raises httpx.HTTPError on transport/status failures."""
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=_FETCH_TIMEOUT, max_redirects=3,
    ) as client:
        resp = await client.get(safe_url, headers={"User-Agent": "NexaDeskAuditionBot/1.0"})
        resp.raise_for_status()

    # A redirect can land somewhere other than the host that was already
    # checked — re-validate the host actually served before trusting it.
    _resolve_and_check(urlparse(str(resp.url)).hostname)

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise LiveFetchError("That doesn't look like a web page.")

    raw = resp.content[:_MAX_RESPONSE_BYTES]
    return str(resp.url), _strip_html(raw.decode(resp.encoding or "utf-8", errors="replace"))


async def _fetch_via_reader(safe_url: str) -> str:
    """
    Read the page through Jina Reader, which runs its JavaScript first. Sites
    built client-side (Wix, most site builders, SPAs like nexadesk.site) are
    an empty shell to a plain GET. Raises httpx.HTTPError on failure.
    """
    settings = get_settings()
    headers = {"X-Return-Format": "text"}
    if settings.JINA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"
    async with httpx.AsyncClient(timeout=_READER_TIMEOUT) as client:
        resp = await client.get(f"{_READER_URL}{safe_url}", headers=headers)
        resp.raise_for_status()
    return resp.text.strip()


async def fetch_page_text(url: str) -> tuple[str, str]:
    """
    Fetch a public URL and return (final_url, readable_text). Raises
    LiveFetchError on anything unsafe, unreachable, or not actually a page —
    never returns partial or garbled content silently.

    The SSRF checks raise LiveFetchError straight through and are never
    retried through the reader: a refused URL stays refused.
    """
    safe_url = _normalize_url(url)
    _resolve_and_check(urlparse(safe_url).hostname)

    final_url, text = safe_url, ""
    try:
        final_url, text = await _fetch_direct(safe_url)
    except httpx.HTTPError as exc:
        logger.info("Direct fetch failed for %s (%s) - trying reader", safe_url, exc)

    if _looks_unreadable(text):
        try:
            text = await _fetch_via_reader(safe_url)
        except httpx.HTTPError as exc:
            logger.warning("Reader fetch failed for %s: %s", safe_url, exc)
            text = ""

    if _looks_unreadable(text):
        raise LiveFetchError(_UNREADABLE_MESSAGE)
    return final_url, text[:_MAX_CONTEXT_CHARS]


def phone_key(raw: str) -> str:
    """
    Canonical Redis key for a phone-keyed live context.

    The web form and Twilio never agree on formatting: a visitor types
    "0331 2228870" (or "+92 331 2228870", or "(781) 365-5768") while Twilio's
    `From` is always E.164 ("+923312228870"). Keying on the raw string meant
    the call looked up a key the browser had never written, so the caller's
    own site silently never reached the assistant - it just behaved as if no
    URL had been entered.

    Matching on the last 10 digits makes both sides agree regardless of
    country code, leading zero, spaces, or punctuation. Ten digits is enough
    to keep distinct callers apart in practice; shorter numbers fall back to
    whatever digits they have.
    """
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return f"phone:{digits[-10:]}" if digits else "phone:unknown"


async def store_live_context(key: str, url: str, text: str, source: str | None = None) -> None:
    """`source` is the URL exactly as the visitor typed it, so a repeat request can reuse this."""
    settings = get_settings()
    redis = await get_redis(settings)
    await redis.setex(
        f"{_REDIS_PREFIX}{key}", _TTL_SECONDS,
        json.dumps({"url": url, "text": text, "source": source}),
    )


async def get_live_context_entry(key: str) -> Optional[dict]:
    settings = get_settings()
    redis = await get_redis(settings)
    raw = await redis.get(f"{_REDIS_PREFIX}{key}")
    if not raw:
        return None
    try:
        entry = json.loads(raw)
    except Exception:
        logger.warning("Corrupt live_fetch payload for key %s — dropping it", key)
        return None
    return entry if isinstance(entry, dict) else None


async def get_live_context(key: str) -> Optional[str]:
    entry = await get_live_context_entry(key)
    return entry.get("text") if entry else None


async def clear_live_context(key: str) -> None:
    settings = get_settings()
    redis = await get_redis(settings)
    await redis.delete(f"{_REDIS_PREFIX}{key}")
