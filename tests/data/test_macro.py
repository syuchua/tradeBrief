# tests/data/test_macro.py
from datetime import date
from unittest.mock import patch

import pandas as pd

from trade_digest.data.macro import fetch_macro_calendar, condense_macro_updates


def _fake_calendar_df():
    return pd.DataFrame({
        "日期": ["2026-07-02"] * 4,
        "地区": ["中国", "美国", "俄罗斯", "中国"],
        "事件": ["中国CPI年率", "美国非农就业", "俄罗斯零售销售", "中国PMI"],
        "公布": [0.3, 250000, None, None],
        "预期": [0.1, 180000, 5.2, 50.1],
        "前值": [-0.1, 210000, 6.5, 49.8],
        "重要性": [3, 3, 1, 2],
    })


def test_fetch_macro_calendar_filters_regions_and_only_released():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=_fake_calendar_df()):
        result = fetch_macro_calendar(["中国", "美国"], date(2026, 7, 2))

    events = {r["event"] for r in result}
    assert events == {"中国CPI年率", "美国非农就业"}


def test_fetch_macro_calendar_computes_surprise_pct():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=_fake_calendar_df()):
        result = fetch_macro_calendar(["美国"], date(2026, 7, 2))

    nonfarm = result[0]
    assert nonfarm["actual"] == 250000
    assert nonfarm["forecast"] == 180000
    assert round(nonfarm["surprise_pct"], 2) == round(abs(250000 - 180000) / 180000 * 100, 2)


def test_fetch_macro_calendar_returns_empty_list_on_error():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", side_effect=RuntimeError("boom")):
        assert fetch_macro_calendar(["中国"], date(2026, 7, 2)) == []


def test_fetch_macro_calendar_treats_nan_forecast_as_none():
    df = pd.DataFrame({
        "日期": ["2026-07-02"],
        "地区": ["中国"],
        "事件": ["中国某指标"],
        "公布": [1.5],
        "预期": [float("nan")],
        "前值": [1.2],
        "重要性": [2],
    })
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=df):
        result = fetch_macro_calendar(["中国"], date(2026, 7, 2))

    assert result[0]["forecast"] is None
    assert result[0]["surprise_pct"] is None


def test_condense_macro_updates_keeps_fed_focus_events_as_highlights():
    updates = [
        {"region": "美国", "event": "美联储利率决议", "actual": 4.5, "forecast": 4.5, "previous": 4.75, "importance": 2, "surprise_pct": 0.0},
        {"region": "中国", "event": "中国CPI年率", "actual": 0.3, "forecast": 0.1, "previous": -0.1, "importance": 2, "surprise_pct": 200.0},
    ]

    result = condense_macro_updates(updates)

    assert result["highlights"] == updates
    assert result["condensed_counts"] == {}


def test_condense_macro_updates_groups_oil_gas_and_precious_metals_by_keyword():
    updates = [
        {"region": "美国", "event": "美国截至7月3日当周石油钻井总数(口)", "actual": 445.0, "forecast": None, "previous": 440.0, "importance": 2, "surprise_pct": None},
        {"region": "美国", "event": "美国7月1日NYMEX铂金库存变动-每日(百盎司)", "actual": 0.0, "forecast": None, "previous": 0.0, "importance": 1, "surprise_pct": None},
        {"region": "美国", "event": "美国7月2日iShares黄金持仓变动-每日(吨)", "actual": -1.3, "forecast": None, "previous": -0.35, "importance": 1, "surprise_pct": None},
    ]

    result = condense_macro_updates(updates)

    assert result["highlights"] == []
    assert result["condensed_counts"] == {"油气数据": 1, "贵金属持仓": 2}


def test_condense_macro_updates_falls_back_to_other_category():
    updates = [{"region": "中国", "event": "中国某冷门统计指标", "actual": 1.0, "forecast": None, "previous": 0.9, "importance": 1, "surprise_pct": None}]

    result = condense_macro_updates(updates)

    assert result["highlights"] == []
    assert result["condensed_counts"] == {"其他": 1}
