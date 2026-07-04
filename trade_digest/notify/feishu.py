# trade_digest/notify/feishu.py
"""飞书自定义机器人通知渠道。环境变量 FEISHU_WEBHOOK_URL。"""
import logging
import os
import re
from collections.abc import Callable

import requests

logger = logging.getLogger(__name__)


def try_create_feishu_sender() -> tuple[str, Callable] | None:
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        return None

    def send(msg: dict[str, str]) -> None:
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": msg["subject"]},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": _html_to_feishu_md(msg["html"])}
                ],
            },
        }
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        # 飞书 webhook 成功时返回 {"StatusCode": 0, ...}
        data = resp.json()
        if data.get("StatusCode") != 0:
            raise RuntimeError(f"Feishu webhook returned error: {data}")

    return ("feishu", send)


def _html_to_feishu_md(html: str) -> str:
    """将简报 HTML 转为飞书卡片支持的 markdown 文本。"""
    text = re.sub(r"<h1[^>]*>", "**", html)
    text = re.sub(r"</h1>", "**\n\n", text)
    text = re.sub(r"<h2[^>]*>", "**", text)
    text = re.sub(r"</h2>", "**\n\n", text)
    text = re.sub(r"<h3[^>]*>", "*", text)
    text = re.sub(r"</h3>", "*\n\n", text)
    text = re.sub(r"<li[^>]*>", "• ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<hr[^>]*>", "\n---\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:15000]
