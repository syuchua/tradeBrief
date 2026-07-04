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
    """将简报 HTML 转为飞书卡片支持的 markdown 文本。

    飞书卡片 markdown 支持：**粗体** *斜体* [链接](url) 无序列表 换行
    """
    # <a> 链接 → markdown [text](url)
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', r"[\2](\1)", html)
    # 块级元素前后加换行
    for tag in ("h1", "h2", "h3", "p", "table", "/table", "tr", "/tr", "ul", "/ul", "ol", "/ol", "hr"):
        text = text.replace(f"<{tag}", f"\n<{tag}")
        text = text.replace(f"</{tag}>", f"</{tag}>\n")
    # <br> → 换行
    text = re.sub(r"<br\s*/?>", "\n", text)
    # <td> / <th> — 单元格之间加分隔
    text = re.sub(r"</t[dh]>\s*<t[dh]", " | ", text)
    text = re.sub(r"</t[dh]>", "  ", text)
    # 标题 → markdown
    text = re.sub(r"<h1[^>]*>", "**", text)
    text = re.sub(r"</h1>", "**\n", text)
    text = re.sub(r"<h2[^>]*>", "**", text)
    text = re.sub(r"</h2>", "**\n", text)
    text = re.sub(r"<h3[^>]*>", "*", text)
    text = re.sub(r"</h3>", "*\n", text)
    # <li> → bullet
    text = re.sub(r"<li[^>]*>", "• ", text)
    text = re.sub(r"</li>", "\n", text)
    # 去掉剩余 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 清理空白
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:15000]
