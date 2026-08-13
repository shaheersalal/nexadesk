"""
Server-side STT via OpenAI whisper-1 (EMBED_API_KEY — same key as embeddings).
Accepts WebM/Opus or MP4/AAC bytes directly — no ffmpeg conversion needed.

language: ISO-639-1 code ('en', 'ur', 'ar', …) or 'auto' for whisper auto-detect.
  Pinning the language is the single biggest fix for short-clip hallucinations:
  whisper auto-detect mis-classifies accented English as the wrong language and
  then transcribes nonsense in that language's phonemes.

mime_type: container MIME string — used to set the correct file extension so
  OpenAI's API recognises the container format.
"""
import io
import logging

logger = logging.getLogger("nexadesk.voice_demo")

_DOMAIN_PROMPT = (
    "Real estate inquiry. Properties in Dubai, Abu Dhabi, London, Manchester, "
    "Houston, Miami, Austin, Nashville. Keywords: apartment, villa, bedroom, "
    "bathroom, buy, rent, invest, AED, GBP, USD, studio, penthouse, Golden Visa."
)


def _ext_from_mime(mime_type: str) -> str:
    """Map a recorder MIME type to an OpenAI-accepted file extension."""
    m = mime_type.lower()
    if "mp4" in m or "m4a" in m or "aac" in m:
        return "m4a"
    if "ogg" in m:
        return "ogg"
    return "webm"   # default — covers audio/webm and audio/webm;codecs=opus


async def transcribe(
    audio_bytes: bytes,
    language: str = "en",
    mime_type: str = "audio/webm",
) -> str:
    """
    Transcribe audio bytes using OpenAI whisper-1.

    Parameters
    ----------
    audio_bytes : bytes   Raw WebM/Opus (or other container) audio.
    language    : str     ISO-639-1 code to pin ('en', 'ur', 'ar', …) or 'auto'.
    mime_type   : str     MIME string from the browser MediaRecorder.
    """
    from openai import AsyncOpenAI
    from app.config import get_settings

    n_bytes = len(audio_bytes)
    ext = _ext_from_mime(mime_type)

    s = get_settings()
    client = AsyncOpenAI(api_key=s.EMBED_API_KEY)

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = f"audio.{ext}"

    kwargs: dict = {
        "model": "whisper-1",
        "file":  audio_file,
    }
    if language and language != "auto":
        kwargs["language"] = language
    # English prompt biases whisper to output Latin/Roman script even for
    # non-Latin languages (Urdu → Roman Urdu, Arabic → transliteration).
    # Only attach the domain prompt for English audio.
    if not language or language in ("en", "auto"):
        kwargs["prompt"] = _DOMAIN_PROMPT

    try:
        result = await client.audio.transcriptions.create(**kwargs)
        text = result.text.strip()
        logger.info(
            "whisper-1 OK  lang=%s  ext=%s  bytes=%d  → %r",
            language, ext, n_bytes, text,
        )
        return text
    except Exception as e:
        # Log the full exception including any API response body
        logger.error(
            "whisper-1 FAIL  lang=%s  ext=%s  bytes=%d  error=%s",
            language, ext, n_bytes, e,
        )
        return ""


async def warmup() -> None:
    """No warmup needed — cloud API, no local model to load."""
    pass
