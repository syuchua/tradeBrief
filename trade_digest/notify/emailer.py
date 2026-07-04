# trade_digest/notify/emailer.py
import os
import smtplib
from collections.abc import Callable
from dataclasses import dataclass
from email.mime.text import MIMEText

SESSION_LABELS = {"morning": "早盘", "evening": "晚间"}


def _fmt_nullable(value) -> str:
    return "无数据" if value is None else str(value)


def _change_pct_color(pct: float) -> str:
    if pct > 0:
        return "#e74c3c"
    elif pct < 0:
        return "#27ae60"
    return "#95a5a6"


def _email_wrapper(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fa;padding:20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
<!-- HEADER -->
<tr><td style="background:#2c3e50;padding:24px 30px;">
<h1 style="color:#ffffff;font-size:20px;margin:0;">{title}</h1>
</td></tr>
<!-- BODY -->
<tr><td style="padding:24px 30px;">
{content}
</td></tr>
<!-- FOOTER -->
<tr><td style="padding:16px 30px;background:#fafafa;border-top:1px solid #eee;">
<p style="color:#95a5a6;font-size:12px;margin:0;text-align:center;">仅供参考，不构成投资建议</p>
</td></tr>
</table></td></tr></table></body></html>"""


def _section_heading(icon: str, title: str) -> str:
    return (
        f'<h2 style="font-size:18px;color:#2c3e50;margin:24px 0 12px 0;'
        f'padding-bottom:8px;border-bottom:2px solid #2c3e50;">{icon} {title}</h2>'
    )


def _subsection_heading(icon: str, title: str) -> str:
    return (
        f'<h3 style="font-size:16px;color:#2c3e50;margin:20px 0 12px 0;'
        f'padding-bottom:8px;border-bottom:1px solid #e0e0e0;">{icon} {title}</h3>'
    )


# ---------------------------------------------------------------------------
# _render_* helpers — each returns a styled HTML fragment (or "" when empty)
# ---------------------------------------------------------------------------


def _render_indices(indices: list[dict] | None) -> str:
    if not indices:
        return (
            '<p style="color:#95a5a6;font-size:14px;margin:8px 0;">'
            "（大盘指数数据缺失）</p>"
        )

    rows = ""
    for i in indices:
        pct = i["change_pct"]
        color = _change_pct_color(pct)
        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">{i["name"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;text-align:right;">{i["price"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;text-align:right;color:{color};">{pct:+.2f}%</td>'
            "</tr>"
        )

    return (
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        '<tr style="background:#f8f9fa;">'
        '<th style="text-align:left;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">指数</th>'
        '<th style="text-align:right;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">最新价</th>'
        '<th style="text-align:right;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">涨跌幅</th>'
        "</tr>"
        f"{rows}"
        "</table>"
    )


def _render_sector_flow(sector_flow: dict | None) -> str:
    if not sector_flow:
        return (
            '<p style="color:#95a5a6;font-size:14px;margin:8px 0;">'
            "（板块资金流数据缺失）</p>"
        )

    inflow = sector_flow.get("top_inflow") or []
    outflow = sector_flow.get("top_outflow") or []

    def _flow_table(items: list[dict], label: str, value_color: str) -> str:
        if not items:
            return (
                f'<p style="color:#95a5a6;font-size:14px;margin:8px 0;">'
                f"{label}：无数据</p>"
            )
        rows = ""
        for s in items:
            rows += (
                "<tr>"
                f'<td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">{s["name"]}</td>'
                f'<td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;text-align:right;color:{value_color};">'
                f'净流入 {s["net_inflow"]:.0f}</td>'
                "</tr>"
            )
        return (
            f'<p style="font-size:14px;color:#2c3e50;margin:12px 0 4px 0;font-weight:600;">{label}</p>'
            '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f"{rows}"
            "</table>"
        )

    parts = []
    if inflow:
        parts.append(_flow_table(inflow, "🔥 流入靠前", "#e74c3c"))
    if outflow:
        parts.append(_flow_table(outflow, "❄️ 流出靠前", "#27ae60"))

    if not parts:
        return (
            '<p style="color:#95a5a6;font-size:14px;margin:8px 0;">'
            "（板块资金流数据缺失）</p>"
        )

    return "".join(parts)


def _render_watchlist(watchlist_quotes: list[dict]) -> str:
    if not watchlist_quotes:
        return ""

    rows = ""
    for q in watchlist_quotes:
        pct = q["change_pct"]
        color = _change_pct_color(pct)
        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">{q["name"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;text-align:right;">{q["price"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;text-align:right;color:{color};">{pct:+.2f}%</td>'
            "</tr>"
        )

    return (
        f"{_subsection_heading('📈', '关注ETF行情')}"
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        '<tr style="background:#f8f9fa;">'
        '<th style="text-align:left;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">名称</th>'
        '<th style="text-align:right;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">最新价</th>'
        '<th style="text-align:right;padding:10px 12px;border-bottom:2px solid #dee2e6;font-size:14px;">涨跌幅</th>'
        "</tr>"
        f"{rows}"
        "</table>"
    )


def _render_alerts(triggered_alerts: list[dict]) -> str:
    if not triggered_alerts:
        return ""

    rows = ""
    for a in triggered_alerts:
        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">'
            f"🔔 {a['name']}: {a['action']}</td>"
            "</tr>"
        )

    return (
        f"{_subsection_heading('🔔', '持仓提醒')}"
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f"{rows}"
        "</table>"
    )


def _render_tactical_scores(llm_result: dict | None) -> str:
    scores = (llm_result or {}).get("tactical_scores") or []
    if not scores:
        return ""

    rows = ""
    for s in scores:
        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">'
            f"⚡ {s['name']}: {s['score']} - {s['reason']}</td>"
            "</tr>"
        )

    return (
        f"{_subsection_heading('⚡', '短线/黄金打分')}"
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f"{rows}"
        "</table>"
    )


def _render_tactical_positions(tactical_positions: list[dict]) -> str:
    if not tactical_positions:
        return ""

    rows = ""
    for p in tactical_positions:
        price_str = f'{p["price"]}' if p["price"] is not None else "无实时报价"
        cost_str = (
            f"（成本 {p['cost_price']}）"
            if p.get("cost_price") is not None
            else ""
        )
        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">'
            f"📌 {p['name']}: {price_str}{cost_str}</td>"
            "</tr>"
        )

    return (
        f"{_subsection_heading('📌', '短线/黄金持仓现价')}"
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f"{rows}"
        "</table>"
    )


def _render_news(news_items: list[dict]) -> str:
    if not news_items:
        return ""

    rows = ""
    for n in news_items[:5]:
        rows += (
            "<tr>"
            f'<td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:14px;">'
            f"📰 [{n['tag']}] {n['summary']}</td>"
            "</tr>"
        )

    return (
        f"{_subsection_heading('📰', '相关新闻')}"
        '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f"{rows}"
        "</table>"
    )


def _render_hk_market(hk_market: dict | None) -> str:
    if not hk_market:
        return "<p>（恒生指数数据缺失）</p>"
    return f"<p>恒生指数收盘: {hk_market['hsi_close']:.2f}</p>"


def _render_priority_alerts(
    priority_alerts: list[dict], tier3_max_items: int = 5
) -> str:
    if not priority_alerts:
        return ""

    tier12 = [a for a in priority_alerts if a["tier"] in (1, 2)]
    tier3 = [a for a in priority_alerts if a["tier"] == 3][:tier3_max_items]
    tier4_count = sum(1 for a in priority_alerts if a["tier"] == 4)

    parts = []

    if tier12:
        items = "".join(
            '<li style="font-size:14px;color:#2c3e50;margin-bottom:6px;">'
            f"<strong>[第{a['tier']}档 {a['category']}]</strong> "
            f"{a['summary']} - {a['reason']}</li>"
            for a in tier12
        )
        parts.append(
            '<table width="100%" cellpadding="0" cellspacing="0"'
            ' style="background:#fff5f5;border-left:4px solid #e74c3c;margin:0 0 20px 0;">'
            '<tr><td style="padding:14px 16px;">'
            '<h2 style="color:#e74c3c;font-size:16px;margin:0 0 10px 0;">'
            "⚠️ 重要提醒</h2>"
            f'<ul style="margin:0;padding-left:20px;">{items}</ul>'
            "</td></tr></table>"
        )

    if tier3:
        items = "".join(
            '<li style="font-size:14px;color:#2c3e50;margin-bottom:4px;">'
            f"[{a['category']}] {a['summary']}</li>"
            for a in tier3
        )
        parts.append(
            f"{_subsection_heading('📋', '其他关注')}"
            f'<ul style="margin:0;padding-left:20px;">{items}</ul>'
        )

    if tier4_count:
        parts.append(
            f'<p style="color:#95a5a6;font-size:14px;margin:12px 0;">'
            f"另有{tier4_count}条常规消息，影响较小，未展开。</p>"
        )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Main render entry point — signature unchanged
# ---------------------------------------------------------------------------


def render_email(
    session: str,
    report_date: str,
    market_overview: dict,
    sector_flow: dict | None,
    watchlist_quotes: list[dict],
    macro_updates: list[dict],
    macro_condensed_counts: dict[str, int],
    triggered_alerts: list[dict],
    tactical_positions: list[dict],
    news_items: list[dict],
    priority_alerts: list[dict],
    llm_result: dict | None,
    health_warnings: list[str] | None = None,
    hk_market: dict | None = None,
) -> str:
    session_label = SESSION_LABELS.get(session, session)
    title = f"{report_date} {session_label}交易简报"
    parts = []

    # 系统健康告警（如有连续失败）
    if health_warnings:
        warning_items = "".join(f"<li>{w}</li>" for w in health_warnings)
        parts.append(
            f"<div style='background-color:#fff3cd; border:1px solid #ffa500; "
            f"padding:10px; margin:10px 0; border-radius:4px'>"
            f"<h3 style='color:#856404; margin:0 0 5px 0'>系统告警</h3>"
            f"<ul style='margin:0; color:#856404'>{warning_items}</ul>"
            f"</div>"
        )

    # --- AI fallback banner ---
    if llm_result is None:
        parts.append(
            '<table width="100%" cellpadding="0" cellspacing="0"'
            ' style="background:#fff5f5;border-left:4px solid #e74c3c;margin:0 0 20px 0;">'
            '<tr><td style="padding:14px 16px;">'
            '<p style="color:#e74c3c;font-size:14px;font-weight:bold;margin:0;">'
            "⚠️ AI解读生成失败，仅展示原始数据</p>"
            "</td></tr></table>"
        )

    # --- Priority alerts (tier banner) ---
    alert_html = _render_priority_alerts(priority_alerts)
    if alert_html:
        parts.append(alert_html)

    # --- Market overview ---
    parts.append(_section_heading("📊", "大盘概览"))
    parts.append(_render_indices(market_overview.get("indices")))
    if hk_market:
        parts.append(_render_hk_market(hk_market))
    if llm_result and llm_result.get("market_summary"):
        parts.append(
            f'<p style="font-size:14px;color:#2c3e50;line-height:1.6;margin:12px 0;">'
            f'{llm_result["market_summary"]}</p>'
        )

    # --- Sector flow ---
    parts.append(_section_heading("💰", "板块资金流"))
    parts.append(_render_sector_flow(sector_flow))

    # --- Watchlist ---
    watchlist_html = _render_watchlist(watchlist_quotes)
    if watchlist_html:
        parts.append(watchlist_html)

    if llm_result and llm_result.get("sector_highlights"):
        parts.append(
            f'<p style="font-size:14px;color:#2c3e50;line-height:1.6;margin:12px 0;">'
            f'{llm_result["sector_highlights"]}</p>'
        )

    # --- Macro data ---
    if macro_updates or macro_condensed_counts:
        parts.append(_section_heading("🌍", "宏观数据"))
        if macro_updates:
            items = "".join(
                '<li style="font-size:14px;color:#2c3e50;margin-bottom:4px;">'
                f"[{m['region']}] {m['event']}: 公布{_fmt_nullable(m['actual'])} "
                f"预期{_fmt_nullable(m['forecast'])} 前值{_fmt_nullable(m['previous'])}"
                "</li>"
                for m in macro_updates
            )
            parts.append(f'<ul style="margin:0;padding-left:20px;">{items}</ul>')
        if macro_condensed_counts:
            summary = "；".join(
                f"{name}{count}项更新"
                for name, count in macro_condensed_counts.items()
            )
            parts.append(
                f'<p style="color:#95a5a6;font-size:14px;margin:12px 0;">'
                f"另有：{summary}（常规数据更新，未展开）</p>"
            )
        if llm_result and llm_result.get("macro_commentary"):
            parts.append(
                f'<p style="font-size:14px;color:#2c3e50;line-height:1.6;margin:12px 0;">'
                f'{llm_result["macro_commentary"]}</p>'
            )

    # --- Alerts ---
    alerts_html = _render_alerts(triggered_alerts)
    if alerts_html:
        parts.append(alerts_html)

    # --- Tactical positions ---
    positions_html = _render_tactical_positions(tactical_positions)
    if positions_html:
        parts.append(positions_html)

    # --- Tactical scores ---
    scores_html = _render_tactical_scores(llm_result)
    if scores_html:
        parts.append(scores_html)

    # --- DCA strategy ---
    dca_strategy = (llm_result or {}).get("dca_strategy")
    if dca_strategy:
        items = "".join(
            '<li style="font-size:14px;color:#2c3e50;margin-bottom:4px;">'
            f"{s['name']}: {s['suggestion']} - {s['reason']}</li>"
            for s in dca_strategy
        )
        parts.append(
            f"{_subsection_heading('💎', '定投策略参考')}"
            f'<ul style="margin:0;padding-left:20px;">{items}</ul>'
        )

    # --- News ---
    news_html = _render_news(news_items)
    if news_html:
        parts.append(news_html)

    body = "\n".join(p for p in parts if p)
    return _email_wrapper(title, body)


# ---------------------------------------------------------------------------
# SMTP config resolver
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
    """Resolve SMTP configuration from environment variables.

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
# SMTP sender
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
    """创建邮件发送 channel 闭包。"""

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
