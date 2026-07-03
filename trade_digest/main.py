# trade_digest/main.py
import argparse
import logging
import os
from datetime import date
from pathlib import Path

from trade_digest.config.loader import load_settings, load_holdings
from trade_digest.data.calendar import is_trading_day
from trade_digest.data.market_overview import fetch_market_overview
from trade_digest.data.sector_flow import fetch_sector_flow_ranking, fetch_etf_quotes
from trade_digest.data.holdings_quotes import enrich_holdings_with_quotes
from trade_digest.data.macro import fetch_macro_calendar
from trade_digest.data.news import fetch_recent_news
from trade_digest.state import is_dca_strategy_due, save_dca_strategy_run_date
from trade_digest.analysis.holdings_alert import evaluate_alerts
from trade_digest.analysis.llm_client import get_llm_client
from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts
from trade_digest.notify.emailer import render_email, send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"
STATE_FILE = Path(__file__).parent.parent / "state" / "dca_strategy_last_run.json"

TACTICAL_CATEGORIES = {"gold", "securities_trading"}


def run(session: str, today: date) -> None:
    if not is_trading_day(today):
        logger.info("Not an A-share trading day, skipping session=%s", session)
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

    macro_updates = fetch_macro_calendar(settings["macro"]["regions"], today)
    news_items = fetch_recent_news(settings["news"]["fetch_limit"])

    dca_due = is_dca_strategy_due(settings["dca_strategy"]["refresh_days"], today, STATE_FILE)

    payload = build_payload(market_overview, sector_flow, watchlist_quotes, macro_updates, news_items, tactical_positions, dca_due)
    llm_client = get_llm_client()
    llm_result = synthesize_report(llm_client, payload)

    if dca_due and llm_result and llm_result.get("dca_strategy"):
        save_dca_strategy_run_date(today, STATE_FILE)

    macro_priority_alerts = build_macro_priority_alerts(macro_updates, settings["macro"]["surprise_threshold_pct"])
    news_priority_alerts = (llm_result or {}).get("priority_alerts") or []
    priority_alerts = macro_priority_alerts + news_priority_alerts

    html = render_email(
        session=session,
        report_date=today.isoformat(),
        market_overview=market_overview,
        sector_flow=sector_flow,
        watchlist_quotes=watchlist_quotes,
        macro_updates=macro_updates,
        triggered_alerts=triggered_alerts,
        tactical_positions=tactical_positions,
        news_items=news_items,
        priority_alerts=priority_alerts,
        llm_result=llm_result,
    )

    send_email(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=int(os.environ.get("SMTP_PORT", "465")),
        smtp_user=os.environ["SMTP_USER"],
        smtp_password=os.environ["SMTP_PASSWORD"],
        sender=os.environ.get("SMTP_SENDER", os.environ["SMTP_USER"]),
        recipients=settings["email"]["recipients"],
        subject=f"{today.isoformat()} {session} 交易简报",
        html_body=html,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", choices=["morning", "evening"], required=True)
    args = parser.parse_args()
    run(args.session, date.today())
