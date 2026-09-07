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


# ── Retrieval filler ─────────────────────────────────────────────────────────
#
# Retrieval has to finish before the model can produce a word, and on a phone
# line that gap is silence. A short acknowledgement is spoken into it when the
# gap is long. Two things must stay true or this does more harm than good: the
# filler must never reach the stored transcript (it would pollute the lead
# summary and the conversation history the model reads back), and it must not
# fire on a turn that was already fast.

import asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

import app.voice.conversation as convo  # noqa: E402
from app.voice.call_session import CallSession  # noqa: E402


def _session():
    return CallSession(call_sid="CA_test", company_id="c-1", caller_number="+15551230000")


async def _drain(user_text, ctx_delay, session):
    """Run one streamed turn with retrieval artificially slow/fast."""
    async def fake_ctx(_text, sess):
        await asyncio.sleep(ctx_delay)
        return "SYSTEM", _text, "en"

    async def fake_stream(system, messages, max_tokens=150, **kw):
        for tok in ("The ", "answer ", "is ", "here."):
            yield tok

    with patch.object(convo, "_build_turn_context", fake_ctx), \
         patch.object(convo.llm, "stream", fake_stream), \
         patch.object(convo, "_persist_turn", _noop, create=True):
        return [frag async for frag in convo.stream_voice_turn(user_text, session)]


async def _noop(*a, **kw):
    return None


@pytest.mark.asyncio
async def test_filler_is_spoken_when_retrieval_is_slow():
    frags = await _drain("what do you build", convo.FILLER_AFTER_SECONDS + 0.3, _session())
    assert frags[0] in convo._RETRIEVAL_FILLERS, (
        f"expected a filler first, got {frags[:1]}"
    )


@pytest.mark.asyncio
async def test_no_filler_when_retrieval_is_fast():
    """A fast turn must not gain a pointless preamble."""
    frags = await _drain("hi", 0.0, _session())
    assert frags[0] not in convo._RETRIEVAL_FILLERS
    assert "".join(frags).startswith("The answer")


@pytest.mark.asyncio
async def test_filler_never_enters_the_stored_transcript():
    """
    The spoken filler is echo-suppressed and thrown away; only the model's own
    words are persisted. If this breaks, every lead summary starts with
    "Let me check that." and the model reads its own filler back as context.
    """
    session = _session()
    frags = await _drain("what do you build", convo.FILLER_AFTER_SECONDS + 0.3, session)
    assert frags[0] in convo._RETRIEVAL_FILLERS  # a filler really was spoken

    history = " ".join(m.get("content", "") for m in session.conversation_history)
    transcript = " ".join(session.transcript_parts)

    # Positive assertion first, so this cannot pass by the history simply
    # being empty - the model's own words must be recorded.
    assert "The answer is here." in history
    assert "The answer is here." in transcript

    for filler in convo._RETRIEVAL_FILLERS:
        assert filler not in history
        assert filler not in transcript
