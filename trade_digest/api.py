# trade_digest/api.py
"""交易简报核心 API —— 可在脚本、Web 服务、Notebook 中直接调用。

示例:
    from trade_digest.api import generate_report, export_html

    report = generate_report("morning")
    print(report.llm_result["market_summary"])

    path = export_html("evening", output_dir="./reports")
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from trade_digest.main import _collect_data
from trade_digest.analysis.llm_client import get_llm_client
from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts
from trade_digest.notify.emailer import render_email
from trade_digest.logging_config import setup_logging

logger = logging.getLogger(__name__)


@dataclass
class ReportContext:
    """一次交易简报的完整上下文。"""
    session: str
    report_date: date
    market_overview: dict
    sector_flow: dict | None
    watchlist_quotes: list[dict]
    macro_updates: list[dict]
    macro_condensed_counts: dict[str, int]
    triggered_alerts: list[dict]
    tactical_positions: list[dict]
    news_items: list[dict]
    priority_alerts: list[dict]
    health_warnings: list[str]
    llm_result: dict | None
    dca_strategy_due: bool
    html: str
    settings: dict = field(repr=False)
    holdings: dict = field(repr=False)


def generate_report(
    session: str = "morning",
    today: date | None = None,
    *,
    enable_llm: bool = True,
) -> ReportContext:
    """生成一份完整的交易简报，返回结构化上下文。

    Args:
        session: "morning" 或 "evening"
        today: 日期，默认今天。非交易日会抛出 RuntimeError
        enable_llm: 是否调用 LLM（False 时跳过，只采集数据 + 渲染）

    Returns:
        包含所有数据和已渲染 HTML 的 ReportContext

    Raises:
        RuntimeError: 非交易日
    """
    if today is None:
        today = date.today()

    ctx = _collect_data(session, today)

    payload = build_payload(
        ctx["market_overview"], ctx["sector_flow"], ctx["watchlist_quotes"],
        ctx["macro_highlights"], ctx["news_items"], ctx["tactical_positions"], ctx["dca_due"],
    )

    llm_result = None
    if enable_llm:
        llm_result = synthesize_report(get_llm_client(), payload)

    macro_priority_alerts = build_macro_priority_alerts(
        ctx["macro_highlights"], ctx["settings"]["macro"]["surprise_threshold_pct"],
    )
    news_priority_alerts = (llm_result or {}).get("priority_alerts") or []
    priority_alerts = macro_priority_alerts + news_priority_alerts

    html = render_email(
        session=session,
        report_date=today.isoformat(),
        market_overview=ctx["market_overview"],
        sector_flow=ctx["sector_flow"],
        watchlist_quotes=ctx["watchlist_quotes"],
        macro_updates=ctx["macro_highlights"],
        macro_condensed_counts=ctx["macro_condensed_counts"],
        triggered_alerts=ctx["triggered_alerts"],
        tactical_positions=ctx["tactical_positions"],
        news_items=ctx["news_items"],
        priority_alerts=priority_alerts,
        llm_result=llm_result,
        health_warnings=ctx["health_warnings"],
        hk_market=ctx["market_overview"].get("hk_market"),
    )

    return ReportContext(
        session=session,
        report_date=today,
        market_overview=ctx["market_overview"],
        sector_flow=ctx["sector_flow"],
        watchlist_quotes=ctx["watchlist_quotes"],
        macro_updates=ctx["macro_highlights"],
        macro_condensed_counts=ctx["macro_condensed_counts"],
        triggered_alerts=ctx["triggered_alerts"],
        tactical_positions=ctx["tactical_positions"],
        news_items=ctx["news_items"],
        priority_alerts=priority_alerts,
        health_warnings=ctx["health_warnings"],
        llm_result=llm_result,
        dca_strategy_due=ctx["dca_due"],
        html=html,
        settings=ctx["settings"],
        holdings=ctx["holdings"],
    )


def export_html(
    session: str = "morning",
    today: date | None = None,
    output_dir: str | Path = ".",
    *,
    enable_llm: bool = True,
) -> Path:
    """生成简报并导出为独立 HTML 文件，不发送任何通知。"""
    setup_logging()
    report = generate_report(session, today, enable_llm=enable_llm)
    filename = f"trade_digest_{report.report_date.isoformat()}_{session}.html"
    path = Path(output_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.html, encoding="utf-8")
    logger.info("Exported HTML to %s", path)
    return path


def export_markdown(
    session: str = "morning",
    today: date | None = None,
    output_dir: str | Path = ".",
    *,
    enable_llm: bool = True,
) -> Path:
    """生成简报并导出为 Markdown 文本文件，不发送任何通知。"""
    setup_logging()
    report = generate_report(session, today, enable_llm=enable_llm)
    md = _html_to_markdown(report.html)
    filename = f"trade_digest_{report.report_date.isoformat()}_{session}.md"
    path = Path(output_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    logger.info("Exported Markdown to %s", path)
    return path


def _html_to_markdown(html: str) -> str:
    """将简报 HTML 转为 Markdown 文本。"""
    text = re.sub(r"<h1[^>]*>", "# ", html)
    text = re.sub(r"</h1>", "\n\n", text)
    text = re.sub(r"<h2[^>]*>", "## ", text)
    text = re.sub(r"</h2>", "\n\n", text)
    text = re.sub(r"<h3[^>]*>", "### ", text)
    text = re.sub(r"</h3>", "\n\n", text)
    text = re.sub(r"<li[^>]*>", "- ", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<hr[^>]*>", "\n---\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
