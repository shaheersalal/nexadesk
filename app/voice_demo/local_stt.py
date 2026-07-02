"""
Self-hosted STT via faster-whisper (CTranslate2, int8, CPU).
Model: base.en (~150 MB) — good English accuracy, ~1-3 s on CPU.
Lazy-loads on first request; subsequent calls reuse the in-process singleton.
"""
import asyncio
import logging
import os
import tempfile

logger = logging.getLogger("nexadesk.voice_demo")

_whisper = None
_lock = asyncio.Lock()

_MODEL_NAME = "base.en"
_CACHE_DIR = os.environ.get("WHISPER_CACHE_DIR", "/app/.models/whisper")


async def _load():
    global _whisper
    if _whisper is not None:
        return _whisper
    async with _lock:
        if _whisper is not None:
            return _whisper
        logger.info("Loading Whisper %s (CPU/int8)…", _MODEL_NAME)
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(
            _MODEL_NAME,
            device="cpu",
            compute_type="int8",
            download_root=_CACHE_DIR,
        )
        logger.info("Whisper ready.")
    return _whisper


def _run_sync(model, webm_path: str) -> str:
    import subprocess
    wav_path = webm_path.replace(".webm", ".wav")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning("ffmpeg webm→wav failed: %s", result.stderr.decode(errors="replace"))
            return ""
        segments, _ = model.transcribe(wav_path, beam_size=5, vad_filter=True)
        return " ".join(s.text for s in segments).strip()
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


async def transcribe(audio_bytes: bytes) -> str:
    model = await _load()
    tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.flush()
        tmp.close()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run_sync, model, tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
