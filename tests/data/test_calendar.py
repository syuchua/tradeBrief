from datetime import date
from unittest.mock import patch

import pandas as pd

from trade_digest.data.calendar import is_trading_day

FAKE_TRADE_DATES = pd.DataFrame({"trade_date": [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]})


def test_is_trading_day_true_for_known_trading_day():
    with patch("trade_digest.data.calendar.ak.tool_trade_date_hist_sina", return_value=FAKE_TRADE_DATES):
        assert is_trading_day(date(2026, 7, 2)) is True


def test_is_trading_day_false_for_weekend():
    with patch("trade_digest.data.calendar.ak.tool_trade_date_hist_sina", return_value=FAKE_TRADE_DATES):
        assert is_trading_day(date(2026, 7, 4)) is False
