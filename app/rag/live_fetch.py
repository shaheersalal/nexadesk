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
        raise LiveFetchError("That URL points somewhere internal — not supported.")


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


async def fetch_page_text(url: str) -> tuple[str, str]:
    """
    Fetch a public URL and return (final_url, readable_text). Raises
    LiveFetchError on anything unsafe, unreachable, or not actually a page —
    never returns partial or garbled content silently.
    """
    safe_url = _normalize_url(url)
    _resolve_and_check(urlparse(safe_url).hostname)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=_FETCH_TIMEOUT, max_redirects=3,
        ) as client:
            resp = await client.get(safe_url, headers={"User-Agent": "NexaDeskAuditionBot/1.0"})
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise LiveFetchError("Couldn't fetch that page.") from exc

    # A redirect can land somewhere other than the host that was already
    # checked — re-validate the host actually served before trusting it.
    _resolve_and_check(urlparse(str(resp.url)).hostname)

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise LiveFetchError("That doesn't look like a web page.")

    raw = resp.content[:_MAX_RESPONSE_BYTES]
    text = _strip_html(raw.decode(resp.encoding or "utf-8", errors="replace"))
    if len(text) < 50:
        raise LiveFetchError("Couldn't find any readable content on that page.")
    return str(resp.url), text[:_MAX_CONTEXT_CHARS]


async def store_live_context(key: str, url: str, text: str) -> None:
    settings = get_settings()
    redis = await get_redis(settings)
    await redis.setex(
        f"{_REDIS_PREFIX}{key}", _TTL_SECONDS, json.dumps({"url": url, "text": text}),
    )


async def get_live_context(key: str) -> Optional[str]:
    settings = get_settings()
    redis = await get_redis(settings)
    raw = await redis.get(f"{_REDIS_PREFIX}{key}")
    if not raw:
        return None
    try:
        return json.loads(raw).get("text")
    except Exception:
        logger.warning("Corrupt live_fetch payload for key %s — dropping it", key)
        return None


async def clear_live_context(key: str) -> None:
    settings = get_settings()
    redis = await get_redis(settings)
    await redis.delete(f"{_REDIS_PREFIX}{key}")
