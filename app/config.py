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

    # LLM
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

    # STT
    STT_API_KEY: str = ""
    STT_MODEL: str = "nova-2"

    # TTS
    TTS_API_KEY: str = ""
    TTS_MODEL: str = "eleven_turbo_v2"
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

    # Upload / Storage
    MAX_UPLOAD_SIZE_MB: int = 50
    SUPABASE_STORAGE_BUCKET: str = "knowledge-base"

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
