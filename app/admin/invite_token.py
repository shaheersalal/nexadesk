"""
Single-use activation tokens for the one-click "Activate Account" email link.

Replaces the previous design, which pasted the server's static ADMINTOKEN into
every outbound demo-request email as a URL query parameter (AUDIT.md C2). That
token grants login-free account creation and never rotates, so a single leaked
email — or one entry in an access log, proxy log, or browser history —
permanently handed over the ability to mint NexaDesk accounts.

A token here is:
  * random (256 bits from `secrets`), so it cannot be guessed;
  * bound to one request_id + email, so it cannot be replayed against another;
  * single-use, consumed atomically with GETDEL;
  * expiring, so an unclicked link stops working.

The static ADMINTOKEN is no longer sent anywhere.
"""
import json
import secrets

import redis.asyncio as aioredis

# Long enough that an invite email sitting unread over a holiday still works,
# short enough that an old leaked inbox is not a standing liability.
INVITE_TTL_SECONDS = 7 * 24 * 3600


def _key(token: str) -> str:
    return f"invite_token:{token}"


async def issue_invite_token(
    redis: aioredis.Redis,
    request_id: str,
    email: str,
    name: str,
) -> str:
    """Mint a single-use activation token and return it."""
    token = secrets.token_urlsafe(32)
    await redis.setex(
        _key(token),
        INVITE_TTL_SECONDS,
        json.dumps({"request_id": request_id, "email": email, "name": name}),
    )
    return token


async def consume_invite_token(redis: aioredis.Redis, token: str) -> dict | None:
    """
    Atomically redeem a token. Returns its payload, or None if the token is
    unknown, already used, or expired.

    GETDEL makes redemption atomic: two concurrent clicks on the same link
    cannot both succeed.
    """
    if not token:
        return None
    raw = await redis.getdel(_key(token))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
