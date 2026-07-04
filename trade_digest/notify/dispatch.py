# trade_digest/notify/dispatch.py
"""多渠道通知调度器 —— 注册 channel，统一发送，失败隔离。"""
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_Message = dict[str, str]  # {"html": ..., "subject": ..., "plain": ...}

_CHANNEL_REGISTRY: list[Callable[[], tuple[str, Callable[[_Message], None]] | None]] = []


def register(factory: Callable[[], tuple[str, Callable[[_Message], None]] | None]):
    """将 channel 工厂注册到调度器。工厂返回 (name, sender) 或 None（未配置）。"""
    _CHANNEL_REGISTRY.append(factory)
    return factory


def _discover() -> list[tuple[str, Callable[[_Message], None]]]:
    channels = []
    for factory in _CHANNEL_REGISTRY:
        try:
            result = factory()
        except Exception:
            logger.exception("Channel factory failed, skipping")
            continue
        if result is not None:
            name, sender = result
            channels.append((name, sender))
            logger.info("Channel %s: enabled", name)
        else:
            logger.info("Channel not configured, skipped")
    return channels


def send_all(html: str, subject: str, plain: str) -> int:
    """发送消息到所有已配置的 channel。返回成功发送的 channel 数量。"""
    message: _Message = {"html": html, "subject": subject, "plain": plain}
    channels = _discover()
    if not channels:
        raise RuntimeError("没有配置任何通知渠道，请设置 SMTP_PROVIDER / FEISHU_WEBHOOK_URL / TELEGRAM_BOT_TOKEN")
    sent = 0
    for name, sender in channels:
        try:
            sender(message)
            sent += 1
            logger.info("Channel %s: sent OK", name)
        except Exception:
            logger.exception("Channel %s: send failed", name)
    return sent
