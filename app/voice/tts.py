"""
ElevenLabs TTS client — streaming audio synthesis.
Returns audio bytes (MP3) that get sent back to Twilio.
"""
import httpx

from app.config import get_settings

settings = get_settings()

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """
    Convert text to speech. Returns MP3 bytes.
    Falls back to Twilio <Say> if ElevenLabs is not configured.
    """
    if not settings.TTS_API_KEY:
        return b""  # Caller will use Twilio <Say> fallback

    vid = voice_id or settings.TTS_VOICE_ID
    url = f"{ELEVENLABS_BASE}/text-to-speech/{vid}"

    payload = {
        "text": text,
        "model_id": settings.TTS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": settings.TTS_API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            return b""
        return response.content


async def synthesize_to_mulaw(text: str) -> bytes:
    """
    Synthesize and convert to 8kHz mulaw for Twilio playback.
    Requires ffmpeg in PATH. Falls back to empty bytes if unavailable.
    """
    mp3_bytes = await synthesize(text)
    if not mp3_bytes:
        return b""
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-ar", "8000", "-ac", "1",
             "-f", "mulaw", "pipe:1"],
            input=mp3_bytes,
            capture_output=True,
            timeout=10,
        )
        return result.stdout
    except Exception:
        return b""
