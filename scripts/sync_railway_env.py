"""
Push selected .env values to the Railway service.

Deliberately an explicit allowlist, not "everything in .env". The local file
carries development values — APP_ENV=development, the placeholder
APP_SECRET_KEY, localhost Qdrant/Redis — and copying those into production
would silently disable every guard that is gated on APP_ENV == "production".

    RAILWAY_TOKEN=... python scripts/sync_railway_env.py [--dry-run]
"""
import os
import pathlib
import subprocess
import sys

# Safe to copy from .env to Railway.
ALLOW = [
    "LLM_API_KEY", "LLM_MODEL",
    "EMBED_API_KEY", "EMBED_MODEL", "EMBED_DIMENSIONS",
    "STT_API_KEY", "STT_MODEL",
    "TTS_PROVIDER", "TTS_API_KEY", "TTS_MODEL", "TTS_VOICE_ID",
    "TELEPHONY_ACCOUNT_SID", "TELEPHONY_AUTH_TOKEN",
    "TELEPHONY_PHONE_NUMBER", "TELEPHONY_WEBHOOK_BASE_URL",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY",
    "SUPABASE_JWT_SECRET", "SUPABASE_JWKS_URL",
    "QDRANT_URL", "QDRANT_API_KEY", "QDRANT_COLLECTION",
    "REDIS_URL",
    "RESEND_API_KEY", "RESEND_WEBHOOK_SECRET", "LISTINGS_INBOUND_DOMAIN",
    "RECAPTCHA_SECRET", "ADMINTOKEN",
    "JINA_API_KEY", "JINA_RERANKER_MODEL",
    "GOOGLE_CALENDAR_CLIENT_ID", "GOOGLE_CALENDAR_CLIENT_SECRET",
    "HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET",
    "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET",
    "SUPPORTED_LANGUAGES", "MAX_UPLOAD_SIZE_MB",
    "SUPABASE_STORAGE_BUCKET", "DASHBOARD_URL", "APP_NAME",
]

# Never copy: environment-specific, or would weaken production.
DENY_REASON = {
    "APP_ENV": "local value is 'development' — would disable production guards",
    "APP_SECRET_KEY": "local value is the placeholder; Railway already has a real one",
    "APP_BASE_URL": "set to the Railway domain, not localhost",
    "QDRANT_HOST": "local-only fallback, superseded by QDRANT_URL",
    "QDRANT_PORT": "local-only fallback, superseded by QDRANT_URL",
    "GOOGLE_CALENDAR_REDIRECT_URI": "derived from APP_BASE_URL in production",
    "UPSTASH_REDIS_REST_URL": "reference only; the app uses REDIS_URL over TCP",
    "UPSTASH_REDIS_REST_TOKEN": "reference only; the app uses REDIS_URL over TCP",
}


def load_env(path=".env") -> dict:
    values = {}
    p = pathlib.Path(path)
    if not p.is_file():
        return values
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not os.environ.get("RAILWAY_TOKEN"):
        print("RAILWAY_TOKEN is not set")
        return 1

    env = load_env()
    to_set, skipped_empty = [], []

    for key in ALLOW:
        value = env.get(key, "")
        if value:
            to_set.append((key, value))
        else:
            skipped_empty.append(key)

    print(f"will set {len(to_set)} variable(s):")
    for k, v in to_set:
        shown = f"…{v[-5:]} ({len(v)} chars)" if any(
            t in k for t in ("KEY", "TOKEN", "SECRET", "PASSWORD", "URL")
        ) else v
        print(f"  {k:28} {shown}")

    print(f"\nempty in .env, not set ({len(skipped_empty)}):")
    print("  " + ", ".join(skipped_empty))

    print("\ndeliberately never synced:")
    for k, why in DENY_REASON.items():
        print(f"  {k:28} {why}")

    if dry:
        print("\n--dry-run: nothing sent")
        return 0
    if not to_set:
        print("\nnothing to send")
        return 0

    cmd = ["railway", "variables", "--skip-deploys"]
    for k, v in to_set:
        cmd += ["--set", f"{k}={v}"]

    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print("\n" + (result.stdout or "").strip()[:600])
    if result.returncode != 0:
        print("FAILED:", (result.stderr or "").strip()[:600])
        return result.returncode
    print("\nsynced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
