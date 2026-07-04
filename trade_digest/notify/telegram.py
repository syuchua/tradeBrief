# trade_digest/notify/telegram.py
"""Telegram Bot 通知渠道。环境变量 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID。"""
import logging
import os
from collections.abc import Callable

import requests

logger = logging.getLogger(__name__)

_MAX_LENGTH = 4000  # Telegram 限制 4096，留余量


def try_create_telegram_sender() -> tuple[str, Callable] | None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return None

    def send(msg: dict[str, str]) -> None:
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        text = f"*{msg['subject']}*\n\n{msg['plain']}"
        # 分片发送
        for i in range(0, len(text), _MAX_LENGTH):
            chunk = text[i : i + _MAX_LENGTH]
            resp = requests.post(
                api_url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data}")

    return ("telegram", send)
