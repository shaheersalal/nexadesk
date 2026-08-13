from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "NexaDesk"
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change-me-in-production"
    APP_BASE_URL: str = "http://localhost:8000"
    SUPPORTED_LANGUAGES: str = "en,es,ar,fr,ur"

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
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "eleven_turbo_v2_5"  # multilingual (32 languages) + low latency; v2 is English-only
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
    # Project JWT secret (Supabase dashboard → Settings → API → JWT Secret).
    # Lets us verify access tokens locally instead of paying a network round
    # trip to Supabase Auth on every authenticated request. When blank the app
    # falls back to the old remote verification path.
    SUPABASE_JWT_SECRET: str = ""
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
