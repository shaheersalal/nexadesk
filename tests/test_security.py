"""
Regression tests for the security findings in AUDIT.md.

Each test names the finding it locks down. These are the ones where a silent
regression would be expensive — cross-tenant leaks, auth bypasses, SSRF — so
they assert the *absence* of the old behaviour, not just that the happy path
still works.
"""
import pytest


# ── C1: unrecognised inbound number must not fall back to an arbitrary tenant ──

@pytest.mark.asyncio
async def test_unknown_phone_number_resolves_to_none(monkeypatch):
    """
    A number no company owns must return None, not "the first company".

    The old code fell back to `SELECT id FROM companies LIMIT 1`, which
    answered strangers as an arbitrary tenant and wrote their lead and full
    transcript into that tenant's CRM.
    """
    from app.voice import router as voice_router

    class FakeTable:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def execute(self): return type("R", (), {"data": []})()

    monkeypatch.setattr(
        voice_router, "get_supabase_admin",
        lambda: type("SB", (), {"table": lambda self, n: FakeTable()})(),
    )

    assert await voice_router._resolve_company_id("+15550000000") is None


@pytest.mark.asyncio
async def test_empty_phone_number_resolves_to_none(monkeypatch):
    from app.voice import router as voice_router
    assert await voice_router._resolve_company_id("") is None


# ── C3: Twilio signature validation must not pass in production ───────────────

def test_twilio_validation_rejects_when_token_missing_in_production(monkeypatch):
    """Blank TELEPHONY_AUTH_TOKEN must fail closed when APP_ENV=production."""
    from app.voice import router as voice_router

    fake_settings = type("S", (), {"TELEPHONY_AUTH_TOKEN": "", "APP_ENV": "production"})()
    monkeypatch.setattr(voice_router, "settings", fake_settings)

    assert voice_router._validate_twilio(None, {}) is False


def test_twilio_validation_allows_in_development(monkeypatch):
    """Local dev without Twilio credentials must still work."""
    from app.voice import router as voice_router

    fake_settings = type("S", (), {"TELEPHONY_AUTH_TOKEN": "", "APP_ENV": "development"})()
    monkeypatch.setattr(voice_router, "settings", fake_settings)

    assert voice_router._validate_twilio(None, {}) is True


class _Cfg:
    """Config double exposing the same telephony properties as Settings."""

    def __init__(self, **kw):
        defaults = {
            "SUPABASE_URL": "https://x.supabase.co",
            "SUPABASE_SERVICE_KEY": "k",
            "LLM_API_KEY": "k",
            "APP_ENV": "production",
            "TELEPHONY_ACCOUNT_SID": "AC123",
            "TELEPHONY_AUTH_TOKEN": "twilio-token",
            "APP_SECRET_KEY": "a-real-secret",
        }
        defaults.update(kw)
        for k, v in defaults.items():
            setattr(self, k, v)

    @property
    def voice_enabled(self):
        return bool(self.TELEPHONY_ACCOUNT_SID and self.TELEPHONY_AUTH_TOKEN)

    @property
    def telephony_partially_configured(self):
        return bool(self.TELEPHONY_ACCOUNT_SID) != bool(self.TELEPHONY_AUTH_TOKEN)


def test_startup_refuses_half_configured_telephony():
    """
    Exactly one telephony credential is the dangerous state: the voice routes
    would mount while signature validation cannot work.
    """
    from app.main import validate_startup_config

    with pytest.raises(RuntimeError, match="half-configured"):
        validate_startup_config(_Cfg(TELEPHONY_AUTH_TOKEN=""))
    with pytest.raises(RuntimeError, match="half-configured"):
        validate_startup_config(_Cfg(TELEPHONY_ACCOUNT_SID=""))


def test_startup_allows_production_with_no_telephony_at_all():
    """
    Telephony is optional. With neither credential set the voice routes are
    never mounted, so there is no unsigned-webhook surface and the rest of the
    app must still boot — being unable to register with Twilio should not
    block deploying chat, RAG and the dashboard.
    """
    from app.main import validate_startup_config

    cfg = _Cfg(TELEPHONY_ACCOUNT_SID="", TELEPHONY_AUTH_TOKEN="")
    validate_startup_config(cfg)
    assert cfg.voice_enabled is False


def test_startup_refuses_placeholder_secret_key():
    from app.main import validate_startup_config

    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
        validate_startup_config(_Cfg(APP_SECRET_KEY="change-me-in-production"))


def test_startup_refuses_missing_required_vars():
    from app.main import validate_startup_config

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        validate_startup_config(_Cfg(SUPABASE_URL=""))


def test_startup_allows_development_without_twilio_token():
    """Local dev must not need Twilio credentials or a real secret."""
    from app.main import validate_startup_config

    validate_startup_config(
        _Cfg(APP_ENV="development", TELEPHONY_AUTH_TOKEN="",
             APP_SECRET_KEY="change-me-in-production")
    )


def test_startup_passes_on_valid_production_config():
    from app.main import validate_startup_config
    validate_startup_config(_Cfg())


# ── C2: activation tokens must be single-use ─────────────────────────────────

@pytest.mark.asyncio
async def test_invite_token_is_single_use(fake_redis):
    """A redeemed token must not work a second time."""
    from app.admin.invite_token import issue_invite_token, consume_invite_token

    token = await issue_invite_token(fake_redis, "req-1", "a@example.com", "Ada")

    first = await consume_invite_token(fake_redis, token)
    assert first == {"request_id": "req-1", "email": "a@example.com", "name": "Ada"}

    assert await consume_invite_token(fake_redis, token) is None


@pytest.mark.asyncio
async def test_invite_token_rejects_unknown_and_empty(fake_redis):
    from app.admin.invite_token import consume_invite_token
    assert await consume_invite_token(fake_redis, "never-issued") is None
    assert await consume_invite_token(fake_redis, "") is None


@pytest.mark.asyncio
async def test_invite_tokens_are_unique(fake_redis):
    from app.admin.invite_token import issue_invite_token
    tokens = {
        await issue_invite_token(fake_redis, "r", "e@x.com", "N")
        for _ in range(50)
    }
    assert len(tokens) == 50


# ── H7: webhook URLs must not reach internal infrastructure ──────────────────

@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",              # not https
        "https://localhost/hook",               # loopback
        "https://127.0.0.1/hook",               # loopback
        "https://169.254.169.254/latest/meta",  # cloud metadata
        "https://10.0.0.5/hook",                # private
        "https://192.168.1.10/hook",            # private
        "not-a-url",
    ],
)
def test_webhook_url_rejected(url):
    """Tenant-supplied URLs pointing inside the trust boundary must be blocked."""
    from app.integrations.events import _is_safe_webhook_url
    safe, reason = _is_safe_webhook_url(url)
    assert safe is False
    assert reason


def test_public_https_webhook_allowed():
    from app.integrations.events import _is_safe_webhook_url
    safe, _ = _is_safe_webhook_url("https://example.com/hook")
    assert safe is True


# ── H9: CRM tokens must be encrypted at rest ─────────────────────────────────

def test_crm_token_roundtrip():
    from app.shared.crypto import encrypt, decrypt
    secret = "oauth-access-token-value"
    stored = encrypt(secret)
    assert stored != secret
    assert secret not in stored
    assert decrypt(stored) == secret


def test_legacy_plaintext_token_still_readable():
    """Rows written before encryption must keep working."""
    from app.shared.crypto import decrypt
    assert decrypt("legacy-plaintext") == "legacy-plaintext"


def test_encrypt_passes_through_empty():
    from app.shared.crypto import encrypt, decrypt
    assert encrypt(None) is None
    assert encrypt("") == ""
    assert decrypt(None) is None


# ── M5: forwarded IP headers must not be trusted by default ──────────────────

def test_forwarded_ip_headers_ignored_by_default(monkeypatch):
    """
    Spoofing CF-Connecting-IP must not create a fresh rate-limit bucket.

    Trusting it unconditionally made every per-IP throttle a no-op.
    """
    from app.public import router as public_router

    monkeypatch.setattr(
        public_router, "get_settings",
        lambda: type("S", (), {"TRUST_PROXY_HEADERS": False})(),
    )

    request = type("Req", (), {
        "headers": {"CF-Connecting-IP": "1.2.3.4", "X-Forwarded-For": "5.6.7.8"},
        "client": type("C", (), {"host": "10.0.0.1"})(),
    })()

    assert public_router._get_client_ip(request) == "10.0.0.1"


def test_forwarded_ip_used_when_explicitly_trusted(monkeypatch):
    from app.public import router as public_router

    monkeypatch.setattr(
        public_router, "get_settings",
        lambda: type("S", (), {"TRUST_PROXY_HEADERS": True})(),
    )

    request = type("Req", (), {
        "headers": {"CF-Connecting-IP": "1.2.3.4"},
        "client": type("C", (), {"host": "10.0.0.1"})(),
    })()

    assert public_router._get_client_ip(request) == "1.2.3.4"


# ── M6: reCAPTCHA must fail closed once configured ───────────────────────────

@pytest.mark.asyncio
async def test_recaptcha_fails_closed_on_error(monkeypatch):
    """A verification outage must reject, not silently allow everything."""
    from app.public import router as public_router

    class Boom:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): raise RuntimeError("network down")

    monkeypatch.setattr(public_router.httpx, "AsyncClient", Boom)
    cfg = type("S", (), {"RECAPTCHA_SECRET": "configured"})()

    assert await public_router._verify_recaptcha("some-token", cfg) is False


@pytest.mark.asyncio
async def test_recaptcha_rejects_missing_token_when_configured():
    from app.public import router as public_router
    cfg = type("S", (), {"RECAPTCHA_SECRET": "configured"})()
    assert await public_router._verify_recaptcha(None, cfg) is False


@pytest.mark.asyncio
async def test_recaptcha_skipped_when_not_configured():
    from app.public import router as public_router
    cfg = type("S", (), {"RECAPTCHA_SECRET": ""})()
    assert await public_router._verify_recaptcha(None, cfg) is True


# ── M11: untyped JSON-RPC args must produce a client error, not a 500 ────────

def test_mcp_limit_coercion():
    from app.mcp.server import _coerce_limit

    assert _coerce_limit(None, 20, 100) == 20      # default
    assert _coerce_limit("15", 20, 100) == 15      # string is legal JSON-RPC
    assert _coerce_limit(500, 20, 100) == 100      # capped

    with pytest.raises(ValueError):
        _coerce_limit("abc", 20, 100)
    with pytest.raises(ValueError):
        _coerce_limit(0, 20, 100)
    with pytest.raises(ValueError):
        _coerce_limit(-5, 20, 100)


# ── Twilio signature is checked against the URL Twilio actually signed ────────

def test_callback_url_uses_configured_base_not_request_scheme(monkeypatch):
    """
    Behind Railway the app reconstructs http:// while Twilio signs https://, so
    every real inbound call was rejected 403 and the line never answered. The
    callback URL must come from configuration, which is what Twilio was given.
    """
    from app.voice import router as voice_router

    class _URL:
        path = "/voice/inbound"
        query = ""
        def __str__(self):
            return "http://nexadesk-api-production.up.railway.app/voice/inbound"

    class _Req:
        url = _URL()

    monkeypatch.setattr(
        voice_router.settings,
        "TELEPHONY_WEBHOOK_BASE_URL",
        "https://nexadesk-api-production.up.railway.app",
        raising=False,
    )
    built = voice_router._callback_url(_Req())
    assert built == "https://nexadesk-api-production.up.railway.app/voice/inbound"
    assert built.startswith("https://"), "signature would be computed over the wrong scheme"


def test_callback_url_preserves_query_string(monkeypatch):
    from app.voice import router as voice_router

    class _URL:
        path = "/voice/status"
        query = "a=1&b=2"
        def __str__(self):
            return "http://x/voice/status?a=1&b=2"

    class _Req:
        url = _URL()

    monkeypatch.setattr(
        voice_router.settings, "TELEPHONY_WEBHOOK_BASE_URL", "https://api.example.com/", raising=False
    )
    assert voice_router._callback_url(_Req()) == "https://api.example.com/voice/status?a=1&b=2"


def test_callback_url_falls_back_when_base_unset(monkeypatch):
    """Local dev has no webhook base; reconstructing from the request is correct there."""
    from app.voice import router as voice_router

    class _URL:
        path = "/voice/inbound"
        query = ""
        def __str__(self):
            return "http://localhost:8000/voice/inbound"

    class _Req:
        url = _URL()

    monkeypatch.setattr(voice_router.settings, "TELEPHONY_WEBHOOK_BASE_URL", "", raising=False)
    assert voice_router._callback_url(_Req()) == "http://localhost:8000/voice/inbound"
