from datetime import date
from unittest.mock import patch, MagicMock

from trade_digest.main import run


def _patch_all(mock_is_trading_day=True):
    patches = {
        "trade_digest.main.setup_logging": patch("trade_digest.main.setup_logging"),
        "trade_digest.main.check_recent_health": patch("trade_digest.main.check_recent_health", return_value=[]),
        "trade_digest.main.record_run_result": patch("trade_digest.main.record_run_result"),
        "trade_digest.main.is_trading_day": patch("trade_digest.main.is_trading_day", return_value=mock_is_trading_day),
        "trade_digest.main.load_settings": patch("trade_digest.main.load_settings", return_value={
            "sector_flow": {"top_n": 5, "watchlist_etfs": [{"name": "纳指", "code": "513100"}]},
            "macro": {"regions": ["中国", "美国"], "surprise_threshold_pct": 10},
            "dca_strategy": {"refresh_days": 7},
            "news": {"fetch_limit": 20, "tier3_max_items": 5},
            "email": {"recipients": ["me@example.com"]},
        }),
        "trade_digest.main.load_holdings": patch("trade_digest.main.load_holdings", return_value={
            "categories": {
                "gold": {"total_weight": 0.2, "positions": [{"name": "黄金", "code": "518880", "cost_price": 4350, "alerts": []}]},
                "securities_trading": {"total_weight": 0.13, "positions": [{"name": "券商", "code": "512880"}]},
                "fund": {"total_weight": 0.4, "positions": [{"name": "纳指", "code": "513100"}]},
            }
        }),
        "trade_digest.main.fetch_market_overview": patch("trade_digest.main.fetch_market_overview", return_value={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None, "hk_market": None}),
        "trade_digest.main.fetch_sector_flow_ranking": patch("trade_digest.main.fetch_sector_flow_ranking", return_value={"top_inflow": [], "top_outflow": []}),
        "trade_digest.main.fetch_etf_quotes": patch("trade_digest.main.fetch_etf_quotes", return_value={}),
        "trade_digest.main.enrich_holdings_with_quotes": patch("trade_digest.main.enrich_holdings_with_quotes", return_value=[
            {"name": "黄金", "category": "gold", "code": "518880", "price": 4360, "cost_price": 4350, "alerts": []},
            {"name": "券商", "category": "securities_trading", "code": "512880", "price": 1.2},
            {"name": "纳指", "category": "fund", "code": "513100", "price": 1.5},
        ]),
        "trade_digest.main.fetch_macro_calendar": patch("trade_digest.main.fetch_macro_calendar", return_value=[]),
        "trade_digest.main.condense_macro_updates": patch("trade_digest.main.condense_macro_updates", return_value={"highlights": [], "condensed_counts": {}}),
        "trade_digest.main.fetch_recent_news": patch("trade_digest.main.fetch_recent_news", return_value=[]),
        "trade_digest.main.is_dca_strategy_due": patch("trade_digest.main.is_dca_strategy_due", return_value=False),
        "trade_digest.main.save_dca_strategy_run_date": patch("trade_digest.main.save_dca_strategy_run_date"),
        "trade_digest.main.load_llm_cache": patch("trade_digest.main.load_llm_cache", return_value=None),
        "trade_digest.main.save_llm_cache": patch("trade_digest.main.save_llm_cache"),
        "trade_digest.main.get_llm_client": patch("trade_digest.main.get_llm_client", return_value=MagicMock()),
        "trade_digest.main.synthesize_report": patch("trade_digest.main.synthesize_report", return_value={"market_summary": "ok", "tactical_scores": [], "priority_alerts": [], "dca_strategy": None, "macro_commentary": None, "sector_highlights": "ok"}),
        "trade_digest.main.render_report": patch("trade_digest.main.render_report", return_value="<html></html>"),
        "trade_digest.main.send_all": patch("trade_digest.main.send_all", return_value=1),
    }
    # resolve_smtp_config 需要返回有效的 SmtpConfig 让 email channel 能注册
    from trade_digest.notify.emailer import SmtpConfig
    mock_smtp = SmtpConfig(host="smtp.test.invalid", port=465, user="test@example.com", password="test", sender="test@example.com")
    patches["trade_digest.main.resolve_smtp_config"] = patch("trade_digest.main.resolve_smtp_config", return_value=mock_smtp)
    started = {name: p.start() for name, p in patches.items()}
    return patches, started


def test_run_skips_everything_on_non_trading_day():
    patches, started = _patch_all(mock_is_trading_day=False)
    try:
        run("morning", date(2026, 7, 4))
        started["trade_digest.main.load_settings"].assert_not_called()
        started["trade_digest.main.send_all"].assert_not_called()
    finally:
        for p in patches.values():
            p.stop()


def test_run_force_bypasses_trading_day_check():
    """--force 跳过交易日检查，周末也能运行。"""
    patches, started = _patch_all(mock_is_trading_day=False)
    try:
        run("morning", date(2026, 7, 4), force=True)
        started["trade_digest.main.send_all"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()


def test_run_sends_email_on_trading_day():
    patches, started = _patch_all(mock_is_trading_day=True)
    try:
        run("morning", date(2026, 7, 2))
        started["trade_digest.main.send_all"].assert_called_once()
        started["trade_digest.main.render_report"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()


def test_run_only_scores_gold_and_securities_trading():
    patches, started = _patch_all(mock_is_trading_day=True)
    try:
        run("morning", date(2026, 7, 2))
        synthesize_call = started["trade_digest.main.synthesize_report"]
        payload_arg = synthesize_call.call_args.args[1]
        tactical_names = {p["name"] for p in payload_arg["watchlist_tactical"]}
        assert tactical_names == {"黄金", "券商"}
    finally:
        for p in patches.values():
            p.stop()


def test_run_saves_dca_state_when_due_and_llm_returned_strategy():
    patches, started = _patch_all(mock_is_trading_day=True)
    started["trade_digest.main.is_dca_strategy_due"].return_value = True
    started["trade_digest.main.synthesize_report"].return_value = {
        "market_summary": "ok", "tactical_scores": [], "priority_alerts": [],
        "dca_strategy": [{"name": "纳指", "suggestion": "继续定投", "reason": "ok"}],
        "macro_commentary": None, "sector_highlights": "ok",
    }
    try:
        run("evening", date(2026, 7, 2))
        started["trade_digest.main.save_dca_strategy_run_date"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()


def test_run_uses_cached_llm_result_when_available():
    patches, started = _patch_all(mock_is_trading_day=True)
    started["trade_digest.main.load_llm_cache"].return_value = {
        "market_summary": "cached", "tactical_scores": [], "priority_alerts": [],
        "dca_strategy": None, "macro_commentary": None, "sector_highlights": "cached",
    }
    try:
        run("morning", date(2026, 7, 2))
        # Should NOT call synthesize_report since cache was hit
        started["trade_digest.main.synthesize_report"].assert_not_called()
        started["trade_digest.main.send_all"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()
