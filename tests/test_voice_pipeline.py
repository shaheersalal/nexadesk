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
