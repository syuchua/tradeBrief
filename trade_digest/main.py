# trade_digest/main.py
import argparse
import logging
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
from trade_digest.notify.emailer import render_email, send_email, resolve_smtp_config

logger = logging.getLogger(__name__)

TACTICAL_CATEGORIES = {"gold", "securities_trading"}


def run(session: str, today: date) -> None:
    # 初始化日志系统（文件轮转 + 控制台）
    setup_logging()

    # 检查近期健康状态，获取系统告警
    health_warnings = check_recent_health()

    if not is_trading_day(today):
        logger.info("Not an A-share trading day, skipping session=%s", session)
        # 非交易日也记录运行结果
        record_run_result(today, session, trading_day=False, components={})
        return

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
    macro_highlights = macro_condensed["highlights"]
    macro_condensed_counts = macro_condensed["condensed_counts"]

    news_items = fetch_recent_news(settings["news"]["fetch_limit"])

    dca_due = is_dca_strategy_due(settings["dca_strategy"]["refresh_days"], today, STATE_FILE)

    payload = build_payload(market_overview, sector_flow, watchlist_quotes, macro_highlights, news_items, tactical_positions, dca_due)

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

    if dca_due and llm_result and llm_result.get("dca_strategy"):
        save_dca_strategy_run_date(today, STATE_FILE)

    macro_priority_alerts = build_macro_priority_alerts(macro_highlights, settings["macro"]["surprise_threshold_pct"])
    news_priority_alerts = (llm_result or {}).get("priority_alerts") or []
    priority_alerts = macro_priority_alerts + news_priority_alerts

    html = render_email(
        session=session,
        report_date=today.isoformat(),
        market_overview=market_overview,
        sector_flow=sector_flow,
        watchlist_quotes=watchlist_quotes,
        macro_updates=macro_highlights,
        macro_condensed_counts=macro_condensed_counts,
        triggered_alerts=triggered_alerts,
        tactical_positions=tactical_positions,
        news_items=news_items,
        priority_alerts=priority_alerts,
        llm_result=llm_result,
        health_warnings=health_warnings,
        hk_market=market_overview.get("hk_market"),
    )

    # 追踪各组件运行状态
    components = {
        "market_overview": isinstance(market_overview, (list, dict)),
        "sector_flow": sector_flow is not None,
        KEY_LLM: llm_result is not None,
        KEY_EMAIL: False,  # 下面 try/except 中更新
    }

    try:
        smtp = resolve_smtp_config()
        send_email(
            smtp_host=smtp.host,
            smtp_port=smtp.port,
            smtp_user=smtp.user,
            smtp_password=smtp.password,
            sender=smtp.sender,
            recipients=settings["email"]["recipients"],
            subject=f"{today.isoformat()} {session} 交易简报",
            html_body=html,
        )
        components["email"] = True
    except Exception:
        logger.exception("Failed to send email")

    # 记录本次运行结果
    record_run_result(today, session, trading_day=True, components=components)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", choices=["morning", "evening"], required=True)
    args = parser.parse_args()
    run(args.session, date.today())
