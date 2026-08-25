from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "NexaDesk"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_BASE_URL: str = "http://localhost:8000"
    # English-only for now. Deepgram Aura has no Arabic or Urdu voice at all, so
    # advertising ar/ur while TTS_PROVIDER=deepgram promises a spoken reply that
    # can never be produced. Widen this again together with an ElevenLabs key.
    SUPPORTED_LANGUAGES: str = "en"

    # Only honour CF-Connecting-IP / X-Forwarded-For when the app really is
    # behind a proxy that overwrites them. Otherwise they are client-controlled
    # and every per-IP rate limit becomes a no-op.
    TRUST_PROXY_HEADERS: bool = False

    # LLM
    LLM_API_KEY: str = ""
    # app/shared/llm.py uses the OpenAI SDK, so this must be an OpenAI model id.
    # The previous "claude-sonnet-4-6" default broke any deploy that did not
    # override it, failing at the first LLM call.
    LLM_MODEL: str = "gpt-4o-mini"

    # STT
    STT_API_KEY: str = ""
    STT_MODEL: str = "nova-2"

    # TTS
    # "auto" prefers ElevenLabs when TTS_API_KEY is set, else falls back to
    # Deepgram Aura (which reuses STT_API_KEY). Set explicitly to "deepgram" or
    # "elevenlabs" to pin one. Aura has no Arabic or Urdu voice, so ar/ur
    # require ElevenLabs.
    TTS_PROVIDER: str = "auto"
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "eleven_turbo_v2_5"  # multilingual (32 languages) + low latency; v2 is English-only
    # ElevenLabs: an opaque voice id. Deepgram: an Aura model name such as
    # aura-2-apollo-en. app/voice/tts.py ignores non-Aura values on the
    # Deepgram path so one field can serve both providers.
    TTS_VOICE_ID: str = ""

    # Embeddings
    EMBED_API_KEY: str = ""
    EMBED_MODEL: str = "text-embedding-3-small"
    EMBED_DIMENSIONS: int = 1536

    # Telephony
    TELEPHONY_ACCOUNT_SID: str = ""
    TELEPHONY_AUTH_TOKEN: str = ""
    TELEPHONY_PHONE_NUMBER: str = ""
    TELEPHONY_WEBHOOK_BASE_URL: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    # Local access-token verification, so an authenticated request costs no
    # network round trip. Two mechanisms, tried in this order:
    #   1. SUPABASE_JWKS_URL — asymmetric (ES256/RS256). What current Supabase
    #      projects issue. Public keys, fetched once and cached.
    #   2. SUPABASE_JWT_SECRET — the legacy shared HS256 secret.
    # If neither is set, or the token matches neither, we fall back to asking
    # Supabase Auth directly.
    SUPABASE_JWKS_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""
    JWKS_CACHE_TTL: int = 3600
    # How long a resolved user->company mapping stays cached in Redis.
    COMPANY_CACHE_TTL: int = 300

    # Qdrant (local: set HOST+PORT; cloud: set QDRANT_URL+QDRANT_API_KEY)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "nexadesk_kb"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Google Calendar
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_REDIRECT_URI: str = ""  # Set to {APP_BASE_URL}/leads/calendar/callback in production

    # Email (Resend)
    RESEND_API_KEY: str = ""
    RESEND_WEBHOOK_SECRET: str = ""  # Svix signing secret for inbound-email webhook verification; skipped if unset
    LISTINGS_INBOUND_DOMAIN: str = "listings.nexadesk.site"  # must be a verified Resend receiving domain

    # Upload / Storage
    MAX_UPLOAD_SIZE_MB: int = 50
    SUPABASE_STORAGE_BUCKET: str = "knowledge-base"

    # Jina AI (re-ranking)
    JINA_API_KEY: str = ""
    JINA_RERANKER_MODEL: str = "jina-reranker-v2-base-multilingual"

    # Admin one-click invite token (HF secret name: ADMINTOKEN)
    ADMINTOKEN: str = ""

    # Google reCAPTCHA v3 (set both RECAPTCHA_SECRET here and VITE_RECAPTCHA_SITE_KEY in dashboard/.env)
    RECAPTCHA_SECRET: str = ""

    # CRM OAuth consumer credentials
    HUBSPOT_CLIENT_ID: str = ""
    HUBSPOT_CLIENT_SECRET: str = ""
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""

    # Dashboard URL (for OAuth callback redirects)
    DASHBOARD_URL: str = "https://nexadesk.site"

    @property
    def calendar_redirect_uri(self) -> str:
        return self.GOOGLE_CALENDAR_REDIRECT_URI or f"{self.APP_BASE_URL}/leads/calendar/callback"

    @property
    def supported_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.SUPPORTED_LANGUAGES.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def voice_enabled(self) -> bool:
        """
        Whether the telephony (phone call) feature is switched on.

        Voice needs both a Twilio account SID and its auth token. With neither
        set the feature is simply off: the /voice routes are not mounted, so
        there is no unsigned-webhook surface to protect and the app boots
        normally. That matters when Twilio is unavailable — being unable to
        register for telephony should not block deploying chat, RAG and the
        dashboard.
        """
        return bool(self.TELEPHONY_ACCOUNT_SID and self.TELEPHONY_AUTH_TOKEN)

    @property
    def telephony_partially_configured(self) -> bool:
        """
        Exactly one of the two telephony credentials is present.

        This is the dangerous middle state — it looks configured but signature
        validation cannot work, so it is treated as an error rather than
        silently degrading (AUDIT.md C3).
        """
        return bool(self.TELEPHONY_ACCOUNT_SID) != bool(self.TELEPHONY_AUTH_TOKEN)


@lru_cache
def get_settings() -> Settings:
    return Settings()
