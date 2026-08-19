"""
Provider selection for TTS.

The failure this pins down is silent: with no provider resolvable, synthesize()
returns b"" and the demo shows text but never speaks — which looks like a
half-working feature rather than a misconfiguration. These assert which backend
each combination of keys actually selects.
"""
import pytest

from app.voice import tts


class _S:
    """Settings double covering only the fields _provider() reads."""

    def __init__(self, provider="auto", eleven_key="", deepgram_key="", voice=""):
        self.TTS_PROVIDER = provider
        self.TTS_API_KEY = eleven_key
        self.STT_API_KEY = deepgram_key
        self.TTS_VOICE_ID = voice
        self.TTS_MODEL = "eleven_turbo_v2_5"


@pytest.mark.parametrize(
    "provider,eleven,deepgram,expected",
    [
        # auto: ElevenLabs wins when present, Deepgram is the fallback
        ("auto", "el-key", "dg-key", "elevenlabs"),
        ("auto", "", "dg-key", "deepgram"),
        ("auto", "el-key", "", "elevenlabs"),
        ("auto", "", "", ""),
        # explicit pins, including asking for a provider with no key
        ("deepgram", "el-key", "dg-key", "deepgram"),
        ("deepgram", "el-key", "", ""),
        ("elevenlabs", "", "dg-key", ""),
        ("elevenlabs", "el-key", "dg-key", "elevenlabs"),
        # tolerate casing and stray whitespace from env files
        ("  DeepGram ", "", "dg-key", "deepgram"),
    ],
)
def test_provider_selection(monkeypatch, provider, eleven, deepgram, expected):
    monkeypatch.setattr(tts, "settings", _S(provider, eleven, deepgram))
    assert tts._provider() == expected


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("aura-2-apollo-en", "aura-2-apollo-en"),
        ("aura-2-thalia-en", "aura-2-thalia-en"),
        # An ElevenLabs voice id must not be sent to Deepgram as a model name.
        ("21m00Tcm4TlvDq8ikWAM", tts.DEEPGRAM_DEFAULT_VOICE),
        ("", tts.DEEPGRAM_DEFAULT_VOICE),
    ],
)
def test_deepgram_voice_resolution(monkeypatch, configured, expected):
    monkeypatch.setattr(tts, "settings", _S(voice=configured))
    assert tts._deepgram_voice(None) == expected


@pytest.mark.asyncio
async def test_empty_text_never_calls_a_provider(monkeypatch):
    """Blank input must not spend an API call."""
    monkeypatch.setattr(tts, "settings", _S(eleven_key="el-key"))

    async def explode(*a, **k):
        raise AssertionError("provider was called for empty text")

    monkeypatch.setattr(tts, "_elevenlabs", explode)
    monkeypatch.setattr(tts, "_deepgram", explode)

    assert await tts.synthesize("   ") == b""
    assert await tts.synthesize_to_mulaw("") == b""


@pytest.mark.asyncio
async def test_no_provider_returns_empty_not_error(monkeypatch):
    monkeypatch.setattr(tts, "settings", _S())
    assert await tts.synthesize("hello") == b""
    assert await tts.synthesize_to_mulaw("hello") == b""


@pytest.mark.asyncio
async def test_deepgram_telephony_path_is_pure_python(monkeypatch):
    """
    The Deepgram phone path must convert with audioop, never ffmpeg.

    Deepgram returns 8 kHz PCM directly, so spawning a subprocess per spoken
    reply would be pure overhead on the latency-critical path.
    """
    monkeypatch.setattr(tts, "settings", _S(provider="deepgram", deepgram_key="dg-key"))

    captured = {}

    async def fake_deepgram(text, voice_id, *, telephony=False):
        captured["telephony"] = telephony
        return b"\x00\x01" * 400  # 16-bit PCM

    monkeypatch.setattr(tts, "_deepgram", fake_deepgram)

    def no_subprocess(*a, **k):
        raise AssertionError("ffmpeg was spawned on the Deepgram path")

    monkeypatch.setattr(tts.asyncio, "create_subprocess_exec", no_subprocess)

    out = await tts.synthesize_to_mulaw("hello there")
    assert captured["telephony"] is True
    # mulaw is 1 byte per sample, PCM16 is 2 — so exactly half the length.
    assert len(out) == 400
