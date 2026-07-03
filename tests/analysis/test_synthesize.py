# tests/analysis/test_synthesize.py
from unittest.mock import MagicMock

from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts


def test_build_payload_assembles_all_sections():
    payload = build_payload(
        market_overview={"indices": []},
        sector_flow={"top_inflow": []},
        watchlist_quotes=[{"code": "513100", "name": "纳指ETF", "price": 1.5, "change_pct": 0.4}],
        macro_updates=[{"event": "CPI"}],
        news_items=[{"summary": "news"}],
        tactical_positions=[{"name": "黄金"}],
        dca_strategy_due=True,
    )
    assert payload == {
        "market_overview": {"indices": []},
        "sector_flow": {"top_inflow": []},
        "watchlist_quotes": [{"code": "513100", "name": "纳指ETF", "price": 1.5, "change_pct": 0.4}],
        "macro_updates": [{"event": "CPI"}],
        "news_items": [{"summary": "news"}],
        "watchlist_tactical": [{"name": "黄金"}],
        "dca_strategy_due": True,
    }


def test_synthesize_report_returns_llm_result():
    llm_client = MagicMock()
    llm_client.generate.return_value = {"market_summary": "ok"}

    result = synthesize_report(llm_client, {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    llm_client.generate.assert_called_once()


def test_synthesize_report_returns_none_on_failure():
    llm_client = MagicMock()
    llm_client.generate.side_effect = RuntimeError("LLM down")

    assert synthesize_report(llm_client, {"foo": "bar"}) is None


def test_build_macro_priority_alerts_flags_surprises_above_threshold():
    macro_updates = [
        {"region": "美国", "event": "非农就业", "actual": 250000, "forecast": 180000, "previous": 210000, "importance": 3, "surprise_pct": 38.9},
        {"region": "中国", "event": "PMI", "actual": 50.1, "forecast": 50.0, "previous": 49.8, "importance": 2, "surprise_pct": 0.2},
    ]
    result = build_macro_priority_alerts(macro_updates, surprise_threshold_pct=10)

    assert len(result) == 1
    assert result[0]["tier"] == 2
    assert result[0]["category"] == "宏观超预期"
    assert "非农就业" in result[0]["summary"]


def test_build_macro_priority_alerts_skips_entries_without_surprise_pct():
    macro_updates = [{"region": "中国", "event": "社融", "actual": 1.0, "forecast": None, "previous": 0.9, "importance": 1, "surprise_pct": None}]

    assert build_macro_priority_alerts(macro_updates, surprise_threshold_pct=10) == []
