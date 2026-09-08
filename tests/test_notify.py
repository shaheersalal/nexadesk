"""
Tests for app/shared/notify.py — the ai_studio-only lead notification email.

Scoped narrowly: this must never raise (a notification failure must never
break the caller's actual conversation), must skip silently with no key
configured, and must actually call Resend with a sane payload when one is.
"""
import pytest

import app.shared.notify as notify


class _FakeResponse:
    def raise_for_status(self):
        pass


class _FakeAsyncClient:
    last_call = None

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        _FakeAsyncClient.last_call = {"url": url, "headers": headers, "json": json}
        return _FakeResponse()


class _BoomAsyncClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **k):
        raise RuntimeError("network is down")


@pytest.mark.asyncio
async def test_skips_silently_with_no_api_key(monkeypatch):
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {"RESEND_API_KEY": ""})(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_call = None

    await notify.send_lead_email({"name": "Ada"}, "Shaheer Salal Studio", channel="chat")

    assert _FakeAsyncClient.last_call is None


@pytest.mark.asyncio
async def test_sends_to_the_configured_recipient_with_a_key(monkeypatch):
    """
    The recipient comes from settings, not a hardcoded constant.

    It used to be pinned to contact@shaheer.dev, which Resend's shared
    onboarding@resend.dev sender is not allowed to deliver to - every lead
    email and visitor digest 403'd and was swallowed as a warning.
    """
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {
            "RESEND_API_KEY": "re_test_key",
            "NOTIFY_EMAIL_TO": "owner@example.com",
        })(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_call = None

    await notify.send_lead_email(
        {"name": "Ada Lovelace", "email": "ada@example.com", "client_company": "Analytical Engines Ltd"},
        "Shaheer Salal Studio",
        channel="chat",
    )

    call = _FakeAsyncClient.last_call
    assert call is not None
    assert call["json"]["to"] == ["owner@example.com"]
    assert "Ada Lovelace" in call["json"]["subject"]
    assert "ada@example.com" in call["json"]["html"]
    assert "Analytical Engines Ltd" in call["json"]["html"]
    assert call["headers"]["Authorization"] == "Bearer re_test_key"


@pytest.mark.asyncio
async def test_never_raises_on_network_failure(monkeypatch):
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {"RESEND_API_KEY": "re_test_key", "NOTIFY_EMAIL_TO": "owner@example.com"})(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _BoomAsyncClient)

    # Must not raise — a failed notification must never break the caller's
    # actual conversation turn.
    await notify.send_lead_email({"name": "Ada"}, "Shaheer Salal Studio", channel="voice")


# ── Call/chat transcript in the notification ────────────────────────────────
#
# Shaheer reported never receiving call or chat transcripts by email. Two bugs
# caused it on the voice path: the transcript is only written when the call
# ends, but the session-end digest fires when the visitor's tab closes (on
# mobile, the instant they tap the call button); and the lead email only fired
# for brand-new leads, so a returning caller produced no email at all. The fix
# moved the send to after the conversation row is written and passes the turns
# along, so this pins the payload actually carrying them.

@pytest.mark.asyncio
async def test_voice_email_includes_the_call_transcript(monkeypatch):
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {
            "RESEND_API_KEY": "re_test_key",
            "NOTIFY_EMAIL_TO": "owner@example.com",
        })(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_call = None

    turns = [
        {"role": "user", "content": "Do you build voice agents?"},
        {"role": "assistant", "content": "Yes, that is the core of what I build."},
    ]
    await notify.send_lead_email(
        {"name": "Dana", "phone": "+15551230000"},
        "Shaheer Salal",
        channel="voice",
        transcript=turns,
        duration=93,
    )

    html = _FakeAsyncClient.last_call["json"]["html"]
    assert "Do you build voice agents?" in html
    assert "Yes, that is the core of what I build." in html
    assert "Caller" in html and "Assistant" in html
    assert "93s" in html          # duration surfaced
    assert "transcript" in html.lower()


@pytest.mark.asyncio
async def test_email_without_a_transcript_renders_no_empty_section(monkeypatch):
    """A call that produced nothing must not email an empty transcript block."""
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {
            "RESEND_API_KEY": "re_test_key",
            "NOTIFY_EMAIL_TO": "owner@example.com",
        })(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.last_call = None

    await notify.send_lead_email({"name": "Dana"}, "Shaheer Salal", channel="voice")
    html = _FakeAsyncClient.last_call["json"]["html"]
    assert "transcript" not in html.lower()


def test_transcript_renderer_skips_empty_turns():
    """Blank turns must not produce stray labels in the email."""
    html = notify._transcript_html(
        [{"role": "user", "content": ""}, {"role": "assistant", "content": "Hello."}],
        "voice",
    )
    assert "Hello." in html
    assert html.count("<b>") == 1
