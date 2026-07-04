# trade_digest/notify/emailer.py
import smtplib
from email.mime.text import MIMEText

SESSION_LABELS = {"morning": "早盘", "evening": "晚间"}


def _fmt_nullable(value) -> str:
    return "无数据" if value is None else str(value)


def _render_indices(indices: list[dict] | None) -> str:
    if not indices:
        return "<p>（大盘指数数据缺失）</p>"
    rows = "".join(f"<li>{i['name']}: {i['price']} ({i['change_pct']:+.2f}%)</li>" for i in indices)
    return f"<ul>{rows}</ul>"


def _render_sector_flow(sector_flow: dict | None) -> str:
    if not sector_flow:
        return "<p>（板块资金流数据缺失）</p>"
    inflow = "".join(f"<li>{s['name']}: 净流入 {s['net_inflow']:.0f}</li>" for s in sector_flow.get("top_inflow", []))
    outflow = "".join(f"<li>{s['name']}: 净流出 {s['net_inflow']:.0f}</li>" for s in sector_flow.get("top_outflow", []))
    return f"<p>流入靠前：</p><ul>{inflow}</ul><p>流出靠前：</p><ul>{outflow}</ul>"


def _render_watchlist(watchlist_quotes: list[dict]) -> str:
    if not watchlist_quotes:
        return ""
    items = "".join(f"<li>{q['name']}: {q['price']} ({q['change_pct']:+.2f}%)</li>" for q in watchlist_quotes)
    return f"<h3>关注ETF行情</h3><ul>{items}</ul>"


def _render_alerts(triggered_alerts: list[dict]) -> str:
    if not triggered_alerts:
        return ""
    items = "".join(f"<li>{a['name']}: {a['action']}</li>" for a in triggered_alerts)
    return f"<h3>持仓提醒</h3><ul>{items}</ul>"


def _render_tactical_scores(llm_result: dict | None) -> str:
    scores = (llm_result or {}).get("tactical_scores") or []
    if not scores:
        return ""
    items = "".join(f"<li>{s['name']}: {s['score']} — {s['reason']}</li>" for s in scores)
    return f"<h3>短线/黄金打分</h3><ul>{items}</ul>"


def _render_tactical_positions(tactical_positions: list[dict]) -> str:
    if not tactical_positions:
        return ""
    items = "".join(
        f"<li>{p['name']}: {p['price'] if p['price'] is not None else '无实时报价'}"
        + (f"（成本 {p['cost_price']}）" if p.get("cost_price") is not None else "")
        + "</li>"
        for p in tactical_positions
    )
    return f"<h3>短线/黄金持仓现价</h3><ul>{items}</ul>"


def _render_news(news_items: list[dict]) -> str:
    if not news_items:
        return ""
    items = "".join(f"<li>[{n['tag']}] {n['summary']}</li>" for n in news_items[:5])
    return f"<h3>相关新闻</h3><ul>{items}</ul>"


def _render_priority_alerts(priority_alerts: list[dict], tier3_max_items: int = 5) -> str:
    if not priority_alerts:
        return ""
    tier12 = [a for a in priority_alerts if a["tier"] in (1, 2)]
    tier3 = [a for a in priority_alerts if a["tier"] == 3][:tier3_max_items]
    tier4_count = sum(1 for a in priority_alerts if a["tier"] == 4)

    parts = []
    if tier12:
        items = "".join(f"<li><strong>[第{a['tier']}档 {a['category']}]</strong> {a['summary']} — {a['reason']}</li>" for a in tier12)
        parts.append(f"<h2 style='color:#b00'>重要提醒</h2><ul>{items}</ul>")
    if tier3:
        items = "".join(f"<li>[{a['category']}] {a['summary']}</li>" for a in tier3)
        parts.append(f"<h3>其他关注</h3><ul>{items}</ul>")
    if tier4_count:
        parts.append(f"<p>另有{tier4_count}条常规消息，影响较小，未展开。</p>")
    return "".join(parts)


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
) -> str:
    session_label = SESSION_LABELS.get(session, session)
    parts = [f"<h1>{report_date} {session_label}简报</h1>"]

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

    if llm_result is None:
        parts.append("<p><strong>AI解读生成失败，仅展示原始数据</strong></p>")

    parts.append(_render_priority_alerts(priority_alerts))

    parts.append("<h2>大盘概览</h2>")
    parts.append(_render_indices(market_overview.get("indices")))
    if llm_result and llm_result.get("market_summary"):
        parts.append(f"<p>{llm_result['market_summary']}</p>")

    parts.append("<h2>板块资金流</h2>")
    parts.append(_render_sector_flow(sector_flow))
    parts.append(_render_watchlist(watchlist_quotes))
    if llm_result and llm_result.get("sector_highlights"):
        parts.append(f"<p>{llm_result['sector_highlights']}</p>")

    if macro_updates or macro_condensed_counts:
        parts.append("<h2>宏观数据</h2>")
        if macro_updates:
            items = "".join(
                f"<li>[{m['region']}] {m['event']}: 公布{_fmt_nullable(m['actual'])} "
                f"预期{_fmt_nullable(m['forecast'])} 前值{_fmt_nullable(m['previous'])}</li>"
                for m in macro_updates
            )
            parts.append(f"<ul>{items}</ul>")
        if macro_condensed_counts:
            summary = "；".join(f"{name}{count}项更新" for name, count in macro_condensed_counts.items())
            parts.append(f"<p>另有：{summary}（常规数据更新，未展开）</p>")
        if llm_result and llm_result.get("macro_commentary"):
            parts.append(f"<p>{llm_result['macro_commentary']}</p>")

    parts.append(_render_alerts(triggered_alerts))
    parts.append(_render_tactical_positions(tactical_positions))
    parts.append(_render_tactical_scores(llm_result))

    dca_strategy = (llm_result or {}).get("dca_strategy")
    if dca_strategy:
        items = "".join(f"<li>{s['name']}: {s['suggestion']} — {s['reason']}</li>" for s in dca_strategy)
        parts.append(f"<h3>定投策略参考</h3><ul>{items}</ul>")

    parts.append(_render_news(news_items))
    parts.append("<hr><p><em>仅供参考，不构成投资建议</em></p>")

    return "\n".join(p for p in parts if p)


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
