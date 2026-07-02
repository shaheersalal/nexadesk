"""
Self-hosted TTS via Kokoro v1.0 ONNX (int8-quantized, CPU).
Model files are baked into the Docker image at KOKORO_CACHE_DIR by the
Dockerfile — no download happens at runtime.
"""
import asyncio
import io
import logging
import os
import subprocess

logger = logging.getLogger("nexadesk.voice_demo")

_kokoro = None
_lock = asyncio.Lock()

_MODEL_DIR = os.environ.get("KOKORO_CACHE_DIR", "/app/.models/kokoro")
_MODEL_FILE = "kokoro-v1.0.int8.onnx"
_VOICES_FILE = "voices-v1.0.bin"
_VOICE = "af_heart"


async def _load():
    global _kokoro
    if _kokoro is not None:
        return _kokoro
    async with _lock:
        if _kokoro is not None:
            return _kokoro
        model_path = os.path.join(_MODEL_DIR, _MODEL_FILE)
        voices_path = os.path.join(_MODEL_DIR, _VOICES_FILE)
        logger.info("Loading Kokoro TTS from %s…", _MODEL_DIR)
        from kokoro_onnx import Kokoro
        loop = asyncio.get_running_loop()
        _kokoro = await loop.run_in_executor(None, Kokoro, model_path, voices_path)
        logger.info("Kokoro loaded.")
    return _kokoro


def _run_sync(kokoro, text: str) -> bytes:
    import soundfile as sf
    samples, sr = kokoro.create(text, voice=_VOICE, speed=1.0, lang="en-us")
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    wav = buf.getvalue()
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "wav", "-i", "pipe:0",
         "-codec:a", "libmp3lame", "-q:a", "4", "-f", "mp3", "pipe:1"],
        input=wav, capture_output=True, timeout=20,
    )
    if result.returncode == 0 and result.stdout:
        return result.stdout
    logger.warning("ffmpeg MP3 encode failed (rc=%d), serving WAV", result.returncode)
    return wav


async def synthesize(text: str) -> bytes:
    kokoro = await _load()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_sync, kokoro, text)
