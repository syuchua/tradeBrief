# tests/data/test_market_overview.py
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from trade_digest.data.market_overview import (
    fetch_index_snapshot,
    fetch_market_breadth,
    fetch_margin_ratio,
    fetch_us_market_snapshot,
    fetch_asia_snapshot,
    fetch_gold_spot_price,
    fetch_hk_snapshot,
    fetch_market_overview,
)


def test_fetch_index_snapshot_filters_major_indices():
    fake_df = pd.DataFrame({
        "代码": ["sh000001", "sz399001", "sh600000"],
        "名称": ["上证指数", "深证成指", "浦发银行"],
        "最新价": [3400.5, 10500.2, 8.5],
        "涨跌幅": [0.5, -0.3, 1.2],
    })
    with patch("trade_digest.data.market_overview.ak.stock_zh_index_spot_sina", return_value=fake_df):
        result = fetch_index_snapshot()
    assert result == [
        {"name": "上证指数", "price": 3400.5, "change_pct": 0.5},
        {"name": "深证成指", "price": 10500.2, "change_pct": -0.3},
    ]


def test_fetch_index_snapshot_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_zh_index_spot_sina", side_effect=RuntimeError("boom")):
        assert fetch_index_snapshot() is None


def test_fetch_market_breadth_parses_long_format():
    fake_df = pd.DataFrame({
        "item": ["上涨", "涨停", "下跌", "跌停", "统计日期"],
        "value": [2112.0, 158.0, 2955.0, 44.0, "2026-07-02 15:00:00"],
    })
    with patch("trade_digest.data.market_overview.ak.stock_market_activity_legu", return_value=fake_df):
        result = fetch_market_breadth()
    assert result == {"up_count": 2112, "down_count": 2955, "limit_up": 158, "limit_down": 44}


def test_fetch_market_breadth_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_market_activity_legu", side_effect=RuntimeError("boom")):
        assert fetch_market_breadth() is None


def test_fetch_margin_ratio_takes_latest_row():
    fake_df = pd.DataFrame({
        "信用交易日期": ["20260630", "20260701"],
        "融资余额": [1000000.0, 1010000.0],
        "融资买入额": [50000.0, 52000.0],
    })
    with patch("trade_digest.data.market_overview.ak.stock_margin_sse", return_value=fake_df):
        result = fetch_margin_ratio()
    assert result == {"financing_balance": 1010000.0, "financing_buy": 52000.0}


def test_fetch_margin_ratio_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_margin_sse", side_effect=RuntimeError("boom")):
        assert fetch_margin_ratio() is None


def test_fetch_us_market_snapshot_reads_latest_close():
    fake_df = pd.DataFrame({
        "date": [date(2026, 6, 30), date(2026, 7, 1)],
        "close": [7441.27, 7483.23],
    })
    with patch("trade_digest.data.market_overview.ak.index_us_stock_sina", return_value=fake_df):
        result = fetch_us_market_snapshot()
    assert result == {"sp500_close": 7483.23}


def test_fetch_asia_snapshot_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.index_global_hist_sina", side_effect=RuntimeError("boom")):
        assert fetch_asia_snapshot() is None


def test_fetch_gold_spot_price_reads_latest_price():
    fake_df = pd.DataFrame({"名称": ["伦敦金"], "最新价": [4167.91]})
    with patch("trade_digest.data.market_overview.ak.futures_foreign_commodity_realtime", return_value=fake_df):
        assert fetch_gold_spot_price() == 4167.91


def test_fetch_gold_spot_price_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.futures_foreign_commodity_realtime", side_effect=RuntimeError("boom")):
        assert fetch_gold_spot_price() is None


def test_fetch_hk_snapshot_reads_latest_close():
    fake_df = pd.DataFrame({
        "date": [date(2026, 7, 2), date(2026, 7, 3)],
        "close": [23055.03, 23350.03],
    })
    with patch("trade_digest.data.market_overview.ak.stock_hk_index_daily_sina", return_value=fake_df):
        result = fetch_hk_snapshot()
    assert result == {"hsi_close": 23350.03}


def test_fetch_hk_snapshot_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_hk_index_daily_sina", side_effect=RuntimeError("boom")):
        assert fetch_hk_snapshot() is None


def test_fetch_market_overview_includes_asia_only_for_morning():
    with patch("trade_digest.data.market_overview.fetch_index_snapshot", return_value=[]), \
         patch("trade_digest.data.market_overview.fetch_market_breadth", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_margin_ratio", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_us_market_snapshot", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_asia_snapshot", return_value={"nikkei_close": 39000.0}) as asia_mock, \
         patch("trade_digest.data.market_overview.fetch_hk_snapshot", return_value={"hsi_close": 23350.03}) as hk_mock:
        morning = fetch_market_overview("morning")
        evening = fetch_market_overview("evening")

    assert morning["asia_market"] == {"nikkei_close": 39000.0}
    assert evening["asia_market"] is None
    asia_mock.assert_called_once()
    # hk_market 不分 session，早晚盘都获取
    assert morning["hk_market"] == {"hsi_close": 23350.03}
    assert evening["hk_market"] == {"hsi_close": 23350.03}
    assert hk_mock.call_count == 2
