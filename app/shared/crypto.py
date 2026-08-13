"""
Symmetric encryption for secrets stored in the database.

CRM OAuth access/refresh tokens were previously written to `crm_connections`
as plain text (AUDIT.md H9). Every backend route already uses the Supabase
service-role key, so anything with read access to that table — a leaked key, a
database backup, an injection elsewhere — yielded live tokens granting write
access to customers' CRMs. Refresh tokens are long-lived, so rotating our own
credentials would not have revoked them.

Keys are derived from APP_SECRET_KEY, which the app already refuses to boot
with at its placeholder value in production.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger("nexadesk.crypto")

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    secret = get_settings().APP_SECRET_KEY.encode()
    # Fernet needs a 32-byte urlsafe-base64 key; APP_SECRET_KEY is free-form.
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str | None) -> str | None:
    """Encrypt a secret for storage. Returns None unchanged."""
    if not plaintext:
        return plaintext
    return _PREFIX + _fernet().encrypt(plaintext.encode()).decode()


def decrypt(value: str | None) -> str | None:
    """
    Decrypt a stored secret.

    Values without the prefix are returned as-is, so rows written before
    encryption was introduced keep working and are re-encrypted on their next
    token refresh. Remove this fallback once no plaintext rows remain.
    """
    if not value:
        return value
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        logger.error(
            "Failed to decrypt a stored secret — APP_SECRET_KEY has probably "
            "changed since it was written. The affected integration must be "
            "reconnected."
        )
        return None
