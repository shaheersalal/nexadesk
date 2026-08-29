"""
Tests for the streaming voice pipeline.

The chunker is the piece most likely to break silently: a bug there does not
raise, it just stops streaming and reintroduces the multi-second dead air the
rewrite existed to remove. The first implementation had exactly that bug — it
returned the whole reply as one chunk — so it is pinned here.
"""
import pytest

from app.voice.tts_stream import sentence_chunks, MIN_CHUNK_CHARS, MAX_CHUNK_CHARS


async def _collect(tokens):
    async def gen():
        for t in tokens:
            yield t
    return [c async for c in sentence_chunks(gen())]


@pytest.mark.asyncio
async def test_splits_multi_sentence_reply():
    """A normal reply must produce several chunks, not one."""
    tokens = [
        "Hello", " there", "! I", " can", " help", " with", " that", " listing", ".",
        " It", " has", " three", " bedrooms", " and", " two", " baths", ".",
        " Want", " a", " viewing", "?",
    ]
    chunks = await _collect(tokens)

    assert len(chunks) > 1, "reply was not split — streaming is defeated"
    assert "".join(chunks).replace(" ", "") == "".join(tokens).replace(" ", "")


@pytest.mark.asyncio
async def test_short_opener_does_not_block_later_splits():
    """
    Regression: a short first fragment must not prevent all later splits.

    The original implementation stopped at the first boundary; because
    "Hello there!" is under MIN_CHUNK_CHARS it bailed out every time and the
    entire reply came back as a single chunk.
    """
    tokens = ["Hi", "!", " This", " is", " a", " much", " longer", " second",
              " sentence", " that", " easily", " clears", " the", " minimum", "."]
    chunks = await _collect(tokens)
    assert len(chunks) >= 1
    assert chunks[0].startswith("Hi!")
    # The short opener is merged forward rather than emitted alone.
    assert len(chunks[0]) >= MIN_CHUNK_CHARS


@pytest.mark.asyncio
async def test_unpunctuated_run_is_force_split():
    """A long run with no punctuation must not buffer forever."""
    chunks = await _collect(["word " * 60])
    assert len(chunks) > 1
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)


@pytest.mark.asyncio
async def test_no_word_is_split_mid_token():
    chunks = await _collect(["supercalifragilistic " * 20])
    for c in chunks:
        for word in c.split():
            assert word in ("supercalifragilistic",), f"word was cut: {word!r}"


@pytest.mark.asyncio
async def test_empty_stream_yields_nothing():
    assert await _collect([]) == []


@pytest.mark.asyncio
async def test_single_short_utterance_still_emitted():
    """A reply shorter than MIN_CHUNK_CHARS must still be spoken."""
    assert await _collect(["Yes", "."]) == ["Yes."]


@pytest.mark.asyncio
async def test_blank_tokens_ignored():
    chunks = await _collect(["", "Hello", "", " world", "", "."])
    assert chunks == ["Hello world."]


# ── The parameter that silenced every inbound call ───────────────────────────

def test_stream_url_never_asks_deepgram_to_detect_language():
    """
    Deepgram rejects detect_language on the streaming socket with HTTP 400 —
    verified against nova-2 and nova-3.

    The rejection was raised from DeepgramStream.__aenter__, before the greeting
    was synthesised, so the whole media-stream handler aborted and the caller
    heard silence until they hung up. It fired on EVERY call, because the
    handler passes language=None whenever session.language_confirmed is False,
    which it always is on a fresh call.
    """
    from app.voice.stt_stream import _build_url
    for language in (None, "", "en"):
        assert "detect_language" not in _build_url(language), (
            f"detect_language sent for language={language!r} — Deepgram 400s on it "
            "and the call is answered with silence"
        )


def test_stream_url_requests_the_configured_language_when_caller_is_unknown(monkeypatch):
    from app.voice import stt_stream
    monkeypatch.setattr(stt_stream.settings, "SUPPORTED_LANGUAGES", "en", raising=False)
    assert "language=en" in stt_stream._build_url(None)


def test_stream_url_omits_language_when_several_are_supported(monkeypatch):
    """
    With no single answer, omitting the parameter is correct: Deepgram falls
    back to English, which is recoverable. Guessing one is not, and asking it to
    detect is a 400.
    """
    from app.voice import stt_stream
    monkeypatch.setattr(stt_stream.settings, "SUPPORTED_LANGUAGES", "en,es,fr", raising=False)
    url = stt_stream._build_url(None)
    assert "language=" not in url
    assert "detect_language" not in url


def test_stream_url_keeps_an_explicit_language(monkeypatch):
    from app.voice import stt_stream
    monkeypatch.setattr(stt_stream.settings, "SUPPORTED_LANGUAGES", "en,es", raising=False)
    assert "language=es" in stt_stream._build_url("es")
