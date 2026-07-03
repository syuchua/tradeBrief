from unittest.mock import patch

import pandas as pd

from trade_digest.data.news import fetch_recent_news


def test_fetch_recent_news_limits_and_maps_fields():
    fake_df = pd.DataFrame({
        "tag": ["市场动态", "公司", "宏观"],
        "summary": ["消息一", "消息二", "消息三"],
        "url": ["https://a", "https://b", "https://c"],
    })
    with patch("trade_digest.data.news.ak.stock_news_main_cx", return_value=fake_df):
        result = fetch_recent_news(limit=2)

    assert result == [
        {"tag": "市场动态", "summary": "消息一", "url": "https://a"},
        {"tag": "公司", "summary": "消息二", "url": "https://b"},
    ]


def test_fetch_recent_news_returns_empty_list_on_error():
    with patch("trade_digest.data.news.ak.stock_news_main_cx", side_effect=RuntimeError("boom")):
        assert fetch_recent_news(limit=5) == []
