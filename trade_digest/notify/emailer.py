# trade_digest/notify/emailer.py
"""SMTP 邮件发送 —— 配置解析、邮件构造、渠道适配。

报告内容的 HTML 渲染已迁移至 trade_digest.notify.render。
为向后兼容，本模块重新导出 render_report 和 render_email（别名）。
"""
import os
import smtplib
from collections.abc import Callable
from dataclasses import dataclass
from email.mime.text import MIMEText

# 向后兼容：旧代码 import render_email / render_report 仍然可用
from trade_digest.notify.render import render_report, render_email  # noqa: F401

# ---------------------------------------------------------------------------
# SMTP 预设表
# ---------------------------------------------------------------------------

SMTP_PRESETS = {
    "qq": {"host": "smtp.qq.com", "port": 465},
    "gmail": {"host": "smtp.gmail.com", "port": 587},
    "163": {"host": "smtp.163.com", "port": 465},
    "outlook": {"host": "smtp-mail.outlook.com", "port": 587},
    "126": {"host": "smtp.126.com", "port": 465},
}


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str


def resolve_smtp_config() -> SmtpConfig:
    """从环境变量解析 SMTP 配置。

    支持两种模式：
    1. 预设模式：设置 SMTP_PROVIDER=qq，只需 SMTP_USER + SMTP_PASSWORD
       host/port 从 SMTP_PRESETS 自动查表，sender 默认 = SMTP_USER
    2. 显式模式（向后兼容）：直接设置 SMTP_HOST/SMTP_PORT/SMTP_USER/
       SMTP_PASSWORD/SMTP_SENDER
    """
    provider = os.environ.get("SMTP_PROVIDER")
    if provider:
        preset = SMTP_PRESETS.get(provider.lower())
        if preset is None:
            raise ValueError(
                f"Unknown SMTP provider {provider!r}, available: {', '.join(SMTP_PRESETS)}"
            )
        host = preset["host"]
        port = preset["port"]
    else:
        host = os.environ["SMTP_HOST"]
        port = int(os.environ.get("SMTP_PORT", "465"))

    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_SENDER", user)

    return SmtpConfig(host=host, port=port, user=user, password=password, sender=sender)


# ---------------------------------------------------------------------------
# SMTP 发送
# ---------------------------------------------------------------------------


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: str,
    recipients: list[str],
    subject: str,
    html_body: str,
) -> None:
    message = MIMEText(html_body, "html", "utf-8")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(sender, recipients, message.as_string())


def try_create_email_sender(
    smtp_config: SmtpConfig,
    recipients: list[str],
) -> tuple[str, Callable[[dict[str, str]], None]]:
    """创建邮件发送 channel 闭包，供 dispatch.send_all 使用。"""

    def send(msg: dict[str, str]) -> None:
        send_email(
            smtp_host=smtp_config.host,
            smtp_port=smtp_config.port,
            smtp_user=smtp_config.user,
            smtp_password=smtp_config.password,
            sender=smtp_config.sender,
            recipients=recipients,
            subject=msg["subject"],
            html_body=msg["html"],
        )

    return ("email", send)
