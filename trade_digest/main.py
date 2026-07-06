# trade_digest/main.py
import argparse
import logging
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from trade_digest.config.loader import load_settings, load_holdings

CONFIG_DIR = Path(__file__).parent / "config"
STATE_FILE = Path(__file__).parent.parent / "state" / "dca_strategy_last_run.json"

# 自动加载 .env 文件（本地开发）；GitHub Actions 等 CI 环境直接注入系统环境变量
_load_dotenv_path = CONFIG_DIR / ".env"
if _load_dotenv_path.exists():
    load_dotenv(_load_dotenv_path)

from trade_digest.data.calendar import is_trading_day
from trade_digest.data.market_overview import fetch_market_overview
from trade_digest.data.sector_flow import fetch_sector_flow_ranking, fetch_etf_quotes
from trade_digest.data.holdings_quotes import enrich_holdings_with_quotes
from trade_digest.data.macro import fetch_macro_calendar, condense_macro_updates
from trade_digest.data.news import fetch_recent_news
from trade_digest.state import is_dca_strategy_due, load_llm_cache, save_dca_strategy_run_date, save_llm_cache
from trade_digest.analysis.holdings_alert import evaluate_alerts
from trade_digest.analysis.llm_client import get_llm_client
from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts
from trade_digest.logging_config import setup_logging
from trade_digest.health import record_run_result, check_recent_health, KEY_LLM, KEY_EMAIL
from trade_digest.notify.emailer import resolve_smtp_config, try_create_email_sender
from trade_digest.notify.render import render_report
from trade_digest.notify.dispatch import register, send_all
from trade_digest.notify.feishu import try_create_feishu_sender
from trade_digest.notify.telegram import try_create_telegram_sender

logger = logging.getLogger(__name__)

TACTICAL_CATEGORIES = {"gold", "securities_trading"}


def _html_to_plain(html: str) -> str:
    """将简报 HTML 转为可读纯文本，保留链接和段落结构。"""
    # <a href="X">text</a> → text (X)
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', r"\2 (\1)", html)
    # 块级元素前后加换行
    for tag in ("h1", "h2", "h3", "p", "table", "/table", "tr", "/tr", "ol", "/ol", "hr"):
        text = text.replace(f"<{tag}", f"\n<{tag}")
        text = text.replace(f"</{tag}>", f"</{tag}>\n")
    # <br> → 换行
    text = re.sub(r"<br\s*/?>", "\n", text)
    # <td>/<th> → 分隔符（必须匹配完整的开始标签，包括 style 属性，否则残留属性文本会漏进输出）
    text = re.sub(r"</t[dh]>\s*<t[dh][^>]*>", " | ", text)
    text = re.sub(r"</t[dh]>", "  ", text)
    # <li> → bullet
    text = re.sub(r"<li[^>]*>", "• ", text)
    text = re.sub(r"</li>", "\n", text)
    # 去除剩余 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 清理空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _collect_data(session: str, today: date, *, force: bool = False) -> dict:
    """采集所有市场数据，返回结构化 dict。供 run() 和 api.py 共用。

    Args:
        force: 强制运行，跳过交易日检查（用于周末/节假日手动测试）

    Raises:
        RuntimeError: 非 A 股交易日且未指定 force
    """
    if not force and not is_trading_day(today):
        raise RuntimeError(f"{today.isoformat()} 不是 A 股交易日，使用 --force 可强制运行")

    settings = load_settings(CONFIG_DIR / "settings.yaml")
    holdings = load_holdings(CONFIG_DIR / "holdings.yaml")

    market_overview = fetch_market_overview(session)
    sector_flow = fetch_sector_flow_ranking(settings["sector_flow"]["top_n"])

    watchlist_codes = [etf["code"] for etf in settings["sector_flow"]["watchlist_etfs"]]
    watchlist_quotes_by_code = fetch_etf_quotes(watchlist_codes)
    watchlist_quotes = [{"code": code, **quote} for code, quote in watchlist_quotes_by_code.items()]

    holdings_flat = enrich_holdings_with_quotes(holdings)
    triggered_alerts = []
    for position in holdings_flat:
        triggered_alerts.extend(evaluate_alerts(position))

    tactical_positions = [p for p in holdings_flat if p["category"] in TACTICAL_CATEGORIES]

    macro_updates_raw = fetch_macro_calendar(settings["macro"]["regions"], today)
    macro_condensed = condense_macro_updates(macro_updates_raw)

    news_items = fetch_recent_news(settings["news"]["fetch_limit"])

    dca_due = is_dca_strategy_due(settings["dca_strategy"]["refresh_days"], today, STATE_FILE)

    return {
        "settings": settings,
        "holdings": holdings,
        "market_overview": market_overview,
        "sector_flow": sector_flow,
        "watchlist_quotes": watchlist_quotes,
        "holdings_flat": holdings_flat,
        "triggered_alerts": triggered_alerts,
        "tactical_positions": tactical_positions,
        "macro_highlights": macro_condensed["highlights"],
        "macro_condensed_counts": macro_condensed["condensed_counts"],
        "news_items": news_items,
        "dca_due": dca_due,
        "health_warnings": check_recent_health(),
    }


def run(session: str, today: date, *, force: bool = False) -> None:
    # 初始化日志系统（文件轮转 + 控制台）
    setup_logging()

    try:
        ctx = _collect_data(session, today, force=force)
    except RuntimeError:
        logger.info("Not an A-share trading day, skipping session=%s", session)
        # 非交易日也记录运行结果
        record_run_result(today, session, trading_day=False, components={})
        return

    payload = build_payload(
        ctx["market_overview"], ctx["sector_flow"], ctx["watchlist_quotes"],
        ctx["macro_highlights"], ctx["news_items"], ctx["tactical_positions"], ctx["dca_due"],
    )

    cache_file = STATE_FILE.parent / "llm_cache.json"
    cache_key = f"{today.isoformat()}_{session}"

    llm_result = load_llm_cache(cache_file, cache_key)
    if llm_result is None:
        llm_client = get_llm_client()
        llm_result = synthesize_report(llm_client, payload)
        if llm_result is not None:
            save_llm_cache(cache_file, cache_key, llm_result)
    else:
        logger.info("Using cached LLM result for %s", cache_key)

    if ctx["dca_due"] and llm_result and llm_result.get("dca_strategy"):
        save_dca_strategy_run_date(today, STATE_FILE)

    macro_priority_alerts = build_macro_priority_alerts(
        ctx["macro_highlights"], ctx["settings"]["macro"]["surprise_threshold_pct"],
    )
    news_priority_alerts = (llm_result or {}).get("priority_alerts") or []
    priority_alerts = macro_priority_alerts + news_priority_alerts

    html = render_report(
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

    # 注册通知渠道
    email_available = False
    try:
        smtp = resolve_smtp_config()
        recipients = ctx["settings"]["email"]["recipients"]
        if recipients:
            register(lambda cfg=smtp, rcpt=recipients: try_create_email_sender(cfg, rcpt))
            email_available = True
    except (KeyError, ValueError):
        logger.info("Email channel not configured")
    register(try_create_feishu_sender)
    register(try_create_telegram_sender)

    # 追踪各组件运行状态
    components = {
        "market_overview": isinstance(ctx["market_overview"], (list, dict)),
        "sector_flow": ctx["sector_flow"] is not None,
        KEY_LLM: llm_result is not None,
        KEY_EMAIL: False,
    }

    # 生成纯文本版本（给 Telegram / 飞书 text 等渠道用）
    plain = _html_to_plain(html)

    try:
        sent_count = send_all(
            html=html,
            subject=f"{today.isoformat()} {session} 交易简报",
            plain=plain,
        )
        if sent_count > 0:
            components[KEY_EMAIL] = True
    except RuntimeError as e:
        logger.error("%s", e)
    except Exception:
        logger.exception("Failed to dispatch notifications")

    # 记录本次运行结果
    record_run_result(today, session, trading_day=True, components=components)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", choices=["morning", "evening"], required=True)
    parser.add_argument("--force", action="store_true", help="强制运行，跳过交易日检查")
    args = parser.parse_args()
    run(args.session, date.today(), force=args.force)
