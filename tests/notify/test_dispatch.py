from unittest.mock import MagicMock
import pytest
from trade_digest.notify.dispatch import register, send_all, _CHANNEL_REGISTRY


def _clear_registry():
    _CHANNEL_REGISTRY.clear()


def test_send_all_raises_when_no_channels(monkeypatch):
    _clear_registry()
    with pytest.raises(RuntimeError, match="没有配置任何通知渠道"):
        send_all("<p>hi</p>", "Test", "hi")


def test_send_all_calls_enabled_channel():
    _clear_registry()
    mock_sender = MagicMock()
    register(lambda: ("test", mock_sender))
    send_all("<p>hi</p>", "Test", "hi")
    mock_sender.assert_called_once()
    msg = mock_sender.call_args.args[0]
    assert msg["subject"] == "Test"


def test_send_all_skips_disabled_channel():
    _clear_registry()
    mock_sender = MagicMock()
    register(lambda: None)  # disabled
    register(lambda: ("enabled", mock_sender))
    send_all("<p>hi</p>", "Test", "hi")
    mock_sender.assert_called_once()


def test_send_all_continues_on_channel_failure():
    _clear_registry()
    bad = MagicMock(side_effect=RuntimeError("boom"))
    good = MagicMock()
    register(lambda: ("bad", bad))
    register(lambda: ("good", good))
    # 不应抛异常
    sent = send_all("<p>hi</p>", "Test", "hi")
    assert sent == 1
    good.assert_called_once()
