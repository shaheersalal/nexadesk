"""
Text-to-speech with pluggable providers.

Two backends, chosen by TTS_PROVIDER:

  deepgram    Aura-2. Fast (sub-200ms first byte) and roughly 5-7x cheaper than
              ElevenLabs, but has no Arabic or Urdu voice at all.
  elevenlabs  More expressive, and the only option for ar/ur.

TTS_PROVIDER="auto" (the default) prefers ElevenLabs when TTS_API_KEY is set and
otherwise falls back to Deepgram, so adding an ElevenLabs key later switches
providers without a code change.

Deepgram can return 8 kHz linear16 directly, which the Twilio path converts to
mulaw with `audioop` — no ffmpeg subprocess at all. ElevenLabs only returns
compressed formats, so that path still shells out to ffmpeg to decode.
"""
import asyncio
import audioop
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("nexadesk.voice")

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEEPGRAM_SPEAK = "https://api.deepgram.com/v1/speak"

# Deepgram's TTS and STT share one API key; STT_API_KEY is where it lives.
DEEPGRAM_DEFAULT_VOICE = "aura-2-apollo-en"


def _provider() -> str:
    """Resolve the active TTS provider, or "" when none is usable."""
    choice = (settings.TTS_PROVIDER or "auto").strip().lower()

    if choice == "elevenlabs":
        return "elevenlabs" if settings.TTS_API_KEY else ""
    if choice == "deepgram":
        return "deepgram" if settings.STT_API_KEY else ""

    # auto
    if settings.TTS_API_KEY:
        return "elevenlabs"
    if settings.STT_API_KEY:
        return "deepgram"
    return ""


def _deepgram_voice(voice_id: str | None) -> str:
    """
    Pick the Aura model name.

    TTS_VOICE_ID is shared with ElevenLabs, where it holds an opaque voice id
    rather than a model name, so anything that doesn't look like an Aura model
    is ignored in favour of the default.
    """
    candidate = (voice_id or settings.TTS_VOICE_ID or "").strip()
    if candidate.startswith("aura"):
        return candidate
    return DEEPGRAM_DEFAULT_VOICE


# ── ElevenLabs ────────────────────────────────────────────────────────────────

async def _elevenlabs(text: str, voice_id: str | None) -> bytes:
    vid = voice_id or settings.TTS_VOICE_ID
    if not vid:
        logger.error("TTS_VOICE_ID is not set — ElevenLabs needs a voice id")
        return b""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{ELEVENLABS_BASE}/text-to-speech/{vid}",
                json={
                    "text": text,
                    "model_id": settings.TTS_MODEL,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
                headers={"xi-api-key": settings.TTS_API_KEY,
                         "Content-Type": "application/json"},
            )
    except Exception as exc:
        logger.error("ElevenLabs TTS request failed: %s", exc)
        return b""

    if response.status_code != 200:
        logger.error("ElevenLabs TTS %s: %s", response.status_code, response.text[:300])
        return b""
    return response.content


# ── Deepgram Aura ─────────────────────────────────────────────────────────────

async def _deepgram(text: str, voice_id: str | None, *, telephony: bool = False) -> bytes:
    """
    Synthesize with Aura.

    `telephony=True` asks for raw 8 kHz linear16 (headerless), which is one
    `audioop.lin2ulaw` away from what Twilio wants. Otherwise returns MP3 for
    browser playback.
    """
    params = {"model": _deepgram_voice(voice_id)}
    if telephony:
        params |= {"encoding": "linear16", "sample_rate": "8000", "container": "none"}
    else:
        params |= {"encoding": "mp3"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                DEEPGRAM_SPEAK,
                params=params,
                json={"text": text},
                headers={"Authorization": f"Token {settings.STT_API_KEY}",
                         "Content-Type": "application/json"},
            )
    except Exception as exc:
        logger.error("Deepgram TTS request failed: %s", exc)
        return b""

    if response.status_code != 200:
        logger.error("Deepgram TTS %s: %s", response.status_code, response.text[:300])
        return b""
    return response.content


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """
    Convert text to compressed audio (MP3) for browser playback.

    Returns b"" when no provider is configured; callers treat that as "show the
    text, play nothing" rather than an error.
    """
    if not text.strip():
        return b""

    provider = _provider()
    if provider == "elevenlabs":
        return await _elevenlabs(text, voice_id)
    if provider == "deepgram":
        return await _deepgram(text, voice_id)

    logger.warning("No TTS provider configured — set TTS_API_KEY or STT_API_KEY")
    return b""


async def synthesize_to_mulaw(text: str) -> bytes:
    """
    Synthesize 8 kHz mulaw for Twilio Media Streams.

    Deepgram returns 8 kHz PCM directly, so the conversion is a pure-Python
    `audioop` call. ElevenLabs only emits compressed audio, so that path must
    decode via ffmpeg — run through asyncio's subprocess API, since a blocking
    `subprocess.run` here stalled the event loop for every concurrent call
    (ruff ASYNC221).
    """
    if not text.strip():
        return b""

    provider = _provider()

    if provider == "deepgram":
        pcm = await _deepgram(text, None, telephony=True)
        if not pcm:
            return b""
        try:
            return audioop.lin2ulaw(pcm, 2)
        except Exception as exc:
            logger.error("mulaw conversion failed: %s", exc)
            return b""

    if provider != "elevenlabs":
        return b""

    mp3_bytes = await _elevenlabs(text, None)
    if not mp3_bytes:
        return b""

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0", "-ar", "8000", "-ac", "1",
            "-f", "mulaw", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=mp3_bytes), timeout=10
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("TTS mulaw conversion timed out after 10s")
            return b""

        if proc.returncode != 0:
            logger.error(
                "ffmpeg exited %s during mulaw conversion: %s",
                proc.returncode,
                stderr.decode(errors="replace")[:400],
            )
            return b""
        return stdout
    except FileNotFoundError:
        logger.error("ffmpeg not found on PATH — cannot convert ElevenLabs audio for Twilio")
        return b""
    except Exception as exc:
        logger.error("TTS mulaw conversion failed: %s", exc)
        return b""
