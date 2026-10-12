"""
Tests for the two-minute closing discipline (app/shared/closing.py).

The point of the module is that the prompt alone does not hold a caller to two
minutes, so these cover the computed stage notes and, just as importantly,
that only Shaheer's own line is time-boxed - a real-estate tenant's calls and
chats must behave exactly as they did before.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.shared.closing import (
    CONTACT_EMAIL,
    HARD_CLOSE_SECONDS,
    MAX_CLOSE_TURNS,
    SOFT_CLOSE_SECONDS,
    SOFT_CLOSE_TURNS,
    SPOKEN_EMAIL,
    call_stage_note,
    chat_stage_note,
)


# ── The stage notes ──────────────────────────────────────────────────────────

def test_early_in_a_call_adds_nothing():
    assert call_stage_note(0) == ""
    assert call_stage_note(SOFT_CLOSE_SECONDS - 1) == ""


def test_soft_close_chases_the_two_missing_details():
    note = call_stage_note(SOFT_CLOSE_SECONDS)
    assert SPOKEN_EMAIL in note
    assert "what they need" in note


def test_hard_close_only_hands_over_the_email():
    note = call_stage_note(HARD_CLOSE_SECONDS)
    assert SPOKEN_EMAIL in note
    assert "Ask no further questions" in note


def test_chat_counts_exchanges_instead_of_seconds():
    assert chat_stage_note(0) == ""
    assert chat_stage_note(SOFT_CLOSE_TURNS - 1) == ""
    assert CONTACT_EMAIL in chat_stage_note(SOFT_CLOSE_TURNS)
    assert "Ask no further questions" in chat_stage_note(MAX_CLOSE_TURNS)


def test_the_email_is_spoken_in_a_form_a_phone_line_survives():
    assert SPOKEN_EMAIL == "contact at shaheer dot dev"
    assert "@" not in SPOKEN_EMAIL


def test_a_written_email_is_rewritten_for_synthesis():
    """
    The model copies "contact@shaheer.dev" out of the knowledge base however
    the rules are worded, and "@" at 8 kHz is a gamble - so it is rewritten.
    """
    from app.shared.closing import speakable

    assert speakable("Email contact@shaheer.dev with the details.") == (
        "Email contact at shaheer dot dev with the details."
    )
    assert speakable("hello@sub.example.co.uk") == "hello at sub dot example dot co dot uk"
    # Ordinary text, and a bare domain, are left alone.
    assert speakable("Visit shaheer.dev for the demo.") == "Visit shaheer.dev for the demo."


@pytest.mark.asyncio
async def test_synthesis_is_fed_the_spoken_form_not_the_written_one(monkeypatch):
    from app.voice import tts_live

    fed: list = []

    class _FakeSpeak:
        def __init__(self, *a, **kw):
            # audio() must not end before the text has been fed, or
            # speak_tokens cancels the pump and nothing is ever sent.
            self._finished = asyncio.Event()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def feed(self, text):
            fed.append(text)

        async def finish(self):
            self._finished.set()

        async def audio(self):
            await self._finished.wait()
            return
            yield b""

    monkeypatch.setattr(tts_live, "SpeakStream", _FakeSpeak)

    async def tokens():
        for tok in ("Email", " contact@shaheer.dev", " now", "."):
            yield tok

    async for _ in tts_live.speak_tokens(tokens()):
        pass

    spoken = "".join(fed)
    assert "contact at shaheer dot dev" in spoken
    assert "@" not in spoken


# ── Where the notes are injected ─────────────────────────────────────────────

def _patch_turn_context(monkeypatch, vertical: str):
    import app.voice.conversation as convo

    async def fake_rag(**kwargs):
        return {"context_text": "kb text", "confidence": "CONFIDENT"}

    async def fake_normalize(text):
        return text, "en"

    async def fake_company(company_id):
        return {"name": "X", "vertical": vertical, "ai_persona": "the assistant"}

    monkeypatch.setattr(convo, "query_with_confidence", fake_rag)
    monkeypatch.setattr(convo, "anormalize_for_llm", fake_normalize)
    monkeypatch.setattr(convo, "_get_company", fake_company)
    return convo


def _session_started_seconds_ago(seconds: int):
    from app.voice.call_session import CallSession

    started = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
    return CallSession(call_sid="CAtest", company_id="c-1", started_at=started)


@pytest.mark.asyncio
async def test_studio_call_past_the_limit_is_told_to_close(monkeypatch):
    convo = _patch_turn_context(monkeypatch, "ai_studio")
    session = _session_started_seconds_ago(HARD_CLOSE_SECONDS + 5)
    system, _, _ = await convo._build_turn_context("hello", session)
    assert "two minutes are up" in system


@pytest.mark.asyncio
async def test_a_tenants_call_is_never_time_boxed(monkeypatch):
    convo = _patch_turn_context(monkeypatch, "real_estate")
    session = _session_started_seconds_ago(HARD_CLOSE_SECONDS + 5)
    system, _, _ = await convo._build_turn_context("hello", session)
    assert "two minutes are up" not in system
    assert SPOKEN_EMAIL not in system


@pytest.mark.asyncio
async def test_past_the_limit_the_close_is_spoken_without_the_model(monkeypatch):
    """
    Asked by prompt to close, the model asked another question instead. Past
    the hard mark the reply is fixed and no model call happens at all.
    """
    from app.shared.closing import CLOSING_LINE

    convo = _patch_turn_context(monkeypatch, "ai_studio")

    async def no_llm(*a, **kw):
        raise AssertionError("the model must not be called past the hard close")
        yield ""

    monkeypatch.setattr(convo.llm, "stream", no_llm)
    session = _session_started_seconds_ago(HARD_CLOSE_SECONDS + 1)
    parts = [p async for p in convo.stream_voice_turn("can we keep chatting?", session)]

    assert "".join(parts) == CLOSING_LINE
    assert SPOKEN_EMAIL in CLOSING_LINE
    # The turn still reaches the transcript the lead email is built from.
    assert any("can we keep chatting?" in p for p in session.transcript_parts)


@pytest.mark.asyncio
async def test_a_tenant_call_past_two_minutes_is_not_cut_short(monkeypatch):
    """A real-estate tenant's caller must still get a normal, model-written reply."""
    convo = _patch_turn_context(monkeypatch, "real_estate")

    async def fake_stream(system, messages, max_tokens=150, **kw):
        for token in ("Sure", ", we have ", "three listings."):
            yield token

    monkeypatch.setattr(convo.llm, "stream", fake_stream)
    session = _session_started_seconds_ago(HARD_CLOSE_SECONDS + 60)
    parts = [p async for p in convo.stream_voice_turn("what do you have?", session)]
    assert "three listings." in "".join(parts)


@pytest.mark.asyncio
async def test_a_fresh_studio_call_is_not_rushed(monkeypatch):
    convo = _patch_turn_context(monkeypatch, "ai_studio")
    session = _session_started_seconds_ago(5)
    system, _, _ = await convo._build_turn_context("hello", session)
    assert "two minutes are up" not in system
    assert "Wrap up now" not in system
