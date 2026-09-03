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
async def test_sends_to_contact_shaheer_dev_with_a_key(monkeypatch):
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {"RESEND_API_KEY": "re_test_key"})(),
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
    assert call["json"]["to"] == [notify.NOTIFY_TO]
    assert notify.NOTIFY_TO == "contact@shaheer.dev"
    assert "Ada Lovelace" in call["json"]["subject"]
    assert "ada@example.com" in call["json"]["html"]
    assert "Analytical Engines Ltd" in call["json"]["html"]
    assert call["headers"]["Authorization"] == "Bearer re_test_key"


@pytest.mark.asyncio
async def test_never_raises_on_network_failure(monkeypatch):
    monkeypatch.setattr(
        notify, "get_settings",
        lambda: type("S", (), {"RESEND_API_KEY": "re_test_key"})(),
    )
    monkeypatch.setattr(notify.httpx, "AsyncClient", _BoomAsyncClient)

    # Must not raise — a failed notification must never break the caller's
    # actual conversation turn.
    await notify.send_lead_email({"name": "Ada"}, "Shaheer Salal Studio", channel="voice")
