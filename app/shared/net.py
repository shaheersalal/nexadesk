"""Shared request-level helpers used by more than one public router."""
from fastapi import Request

from app.config import get_settings


def get_client_ip(request: Request) -> str:
    """
    Best-effort client IP for rate limiting and visitor logging.

    Only honoured when TRUST_PROXY_HEADERS is set, and even then only
    X-Forwarded-For is read - never CF-Connecting-IP.

    That split is empirical, measured against this deployment on
    2026-09-06 rather than assumed:

    - With TRUST_PROXY_HEADERS off, `request.client.host` is Railway's own
      internal proxy (100.64.0.x, RFC 6598) and it *rotates per request*.
      Every visitor therefore looked like a brand-new IP on every single
      request, which silently made all per-IP throttles no-ops and made the
      site_visitors IP-dedup log meaningless.
    - Railway's edge OVERWRITES X-Forwarded-For with the true client
      address: a request sent with a forged `X-Forwarded-For: 9.9.9.9`
      was still recorded as the real client IP. So XFF here cannot be
      spoofed and is safe to trust.
    - Railway does NOT touch CF-Connecting-IP, and nothing legitimately
      sets it, because the API is called directly on its railway.app origin
      rather than through Cloudflare. Trusting it let `curl -H
      "CF-Connecting-IP: 203.0.113.77"` write an arbitrary attacker-chosen
      address straight into the visitor log and mint a fresh throttle
      bucket per request (AUDIT.md M5, verified live and then closed here).

    Render is different, measured 2026-09-17: it sits behind Cloudflare and
    does NOT overwrite X-Forwarded-For - seven requests each forging a
    different XFF all passed the 6/min live-context limit. Every request to
    an onrender.com service goes through Cloudflare, which sets
    CF-Connecting-IP itself, so on Render CLIENT_IP_HEADER=CF-Connecting-IP.
    """
    settings = get_settings()
    if settings.TRUST_PROXY_HEADERS:
        value = request.headers.get(settings.CLIENT_IP_HEADER.strip() or "X-Forwarded-For")
        if value:
            return value.split(",")[0].strip()
    return (request.client.host if request.client else None) or "unknown"
