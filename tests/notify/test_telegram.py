import os
from unittest.mock import patch, MagicMock
from trade_digest.notify.telegram import try_create_telegram_sender


def test_try_create_returns_none_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    assert try_create_telegram_sender() is None


def test_try_create_returns_none_without_chat_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert try_create_telegram_sender() is None


def test_try_create_returns_sender_when_configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    result = try_create_telegram_sender()
    assert result is not None
    name, _ = result
    assert name == "telegram"


def test_telegram_sender_posts_correct_payload():
    fake_response = MagicMock()
    fake_response.json.return_value = {"ok": True}
    fake_response.raise_for_status.return_value = None

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "123"}, clear=True):
        result = try_create_telegram_sender()
    _, sender = result

    with patch("trade_digest.notify.telegram.requests.post", return_value=fake_response) as mock_post:
        sender({"html": "", "subject": "Test", "plain": "Hello"})

    mock_post.assert_called_once()
    kwargs = mock_post.call_args.kwargs
    assert kwargs["json"]["chat_id"] == "123"
    assert "<b>Test</b>" in kwargs["json"]["text"]
    assert kwargs["json"]["parse_mode"] == "HTML"
