# tests/data/test_sector_flow.py
from unittest.mock import patch

import pandas as pd

from trade_digest.data.sector_flow import fetch_sector_flow_ranking, fetch_etf_quotes


def _fake_concept_df():
    return pd.DataFrame({
        "行业": ["半导体", "白酒", "煤炭"],
        "行业-涨跌幅": [3.5, -1.2, -2.8],
        "净额": [50000.0, -10000.0, -30000.0],
    })


def test_fetch_sector_flow_ranking_sorts_by_net_inflow():
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", return_value=_fake_concept_df()):
        result = fetch_sector_flow_ranking(top_n=2)

    assert result["top_inflow"][0] == {"name": "半导体", "change_pct": 3.5, "net_inflow": 50000.0}
    assert result["top_outflow"][0] == {"name": "煤炭", "change_pct": -2.8, "net_inflow": -30000.0}


def test_fetch_sector_flow_ranking_top_and_bottom_never_overlap():
    # 3 rows, top_n=2: without exclusion, head(2) and tail(2) would both include row 1 ("白酒").
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", return_value=_fake_concept_df()):
        result = fetch_sector_flow_ranking(top_n=2)

    top_names = {r["name"] for r in result["top_inflow"]}
    bottom_names = {r["name"] for r in result["top_outflow"]}
    assert top_names.isdisjoint(bottom_names)


def test_fetch_sector_flow_ranking_returns_none_on_error():
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", side_effect=RuntimeError("boom")):
        assert fetch_sector_flow_ranking(top_n=5) is None


def _fake_etf_df():
    return pd.DataFrame({
        "代码": ["sz159998", "sh513100", "sh518880"],
        "名称": ["计算机ETF天弘", "纳指ETF", "黄金ETF"],
        "最新价": [1.014, 1.5, 6.2],
        "涨跌幅": [-4.789, 1.1, 0.3],
    })


def test_fetch_etf_quotes_matches_by_six_digit_code():
    with patch("trade_digest.data.sector_flow.ak.fund_etf_category_sina", return_value=_fake_etf_df()):
        result = fetch_etf_quotes(["513100", "518880", "999999"])

    assert result["513100"] == {"name": "纳指ETF", "price": 1.5, "change_pct": 1.1}
    assert result["518880"] == {"name": "黄金ETF", "price": 6.2, "change_pct": 0.3}
    assert "999999" not in result


def test_fetch_etf_quotes_returns_empty_dict_on_error():
    with patch("trade_digest.data.sector_flow.ak.fund_etf_category_sina", side_effect=RuntimeError("boom")):
        assert fetch_etf_quotes(["513100"]) == {}


def test_fetch_etf_quotes_returns_empty_dict_for_no_codes():
    assert fetch_etf_quotes([]) == {}
