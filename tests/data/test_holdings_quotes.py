from unittest.mock import patch

from trade_digest.data.holdings_quotes import enrich_holdings_with_quotes

HOLDINGS = {
    "categories": {
        "fund": {
            "total_weight": 0.40,
            "positions": [
                {"name": "科技板块基金", "code": None, "weight_within_category": 0.5},
                {"name": "纳指", "code": "513100", "weight_within_category": 0.15},
            ],
        },
        "gold": {
            "total_weight": 0.20,
            "positions": [
                {"name": "黄金", "code": "518880", "cost_price": 4350, "alerts": [{"condition": "price >= 4380", "action": "减仓"}]},
            ],
        },
    }
}


def test_enrich_holdings_flattens_categories_and_attaches_price():
    fake_quotes = {"513100": {"name": "纳指ETF", "price": 1.55, "change_pct": 0.4}}
    with patch("trade_digest.data.holdings_quotes.fetch_etf_quotes", return_value=fake_quotes) as mock_fetch, \
         patch("trade_digest.data.holdings_quotes.fetch_gold_spot_price", return_value=4360.5) as mock_gold:
        result = enrich_holdings_with_quotes(HOLDINGS)

    mock_fetch.assert_called_once_with(["513100"])
    mock_gold.assert_called_once()
    by_name = {p["name"]: p for p in result}
    assert by_name["纳指"]["category"] == "fund"
    assert by_name["纳指"]["price"] == 1.55
    assert by_name["纳指"]["change_pct"] == 0.4
    assert by_name["黄金"]["price"] == 4360.5
    assert by_name["黄金"]["change_pct"] is None
    assert by_name["黄金"]["cost_price"] == 4350
    assert by_name["科技板块基金"]["price"] is None
    assert by_name["科技板块基金"]["change_pct"] is None


def test_enrich_holdings_handles_no_codes():
    holdings = {"categories": {"fund": {"total_weight": 1.0, "positions": [{"name": "现金", "code": None}]}}}
    with patch("trade_digest.data.holdings_quotes.fetch_etf_quotes", return_value={}) as mock_fetch, \
         patch("trade_digest.data.holdings_quotes.fetch_gold_spot_price") as mock_gold:
        result = enrich_holdings_with_quotes(holdings)

    mock_fetch.assert_called_once_with([])
    mock_gold.assert_not_called()
    assert result[0]["price"] is None
