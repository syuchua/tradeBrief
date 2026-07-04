# trade_digest/notify/telegram.py
"""Telegram Bot 通知渠道。环境变量 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID。"""
import logging
import os
import re
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
        text = _plain_to_telegram_html(msg["plain"], msg["subject"])
        # 分片发送
        for i in range(0, len(text), _MAX_LENGTH):
            chunk = text[i : i + _MAX_LENGTH]
            resp = requests.post(
                api_url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error: {data}")

    return ("telegram", send)


def _plain_to_telegram_html(plain: str, subject: str) -> str:
    """将纯文本转为 Telegram HTML 格式，加粗标题 + 可点击链接。

    Telegram HTML 支持：<b> <i> <a href=""> <code> <pre> <u> <s>
    """
    # 标题加粗
    text = f"<b>{_escape_html(subject)}</b>\n\n"

    # 纯文本中可能有 "text (url)" 格式的链接，转为可点击 <a>
    result = []
    for line in plain.splitlines():
        if not line.strip():
            result.append("")
            continue
        # "text (http://...)" → "<a href="http://...">text</a>"
        line = re.sub(
            r"(.+?)\s*\((https?://[^)]+)\)",
            r'<a href="\2">\1</a>',
            _escape_html(line),
        )
        # bullet 行保留缩进
        if line.startswith("•"):
            result.append(f"  {line}")
        else:
            result.append(line)

    text += "\n".join(result)
    return text


def _escape_html(text: str) -> str:
    """转义 Telegram HTML 解析所需的特殊字符。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
