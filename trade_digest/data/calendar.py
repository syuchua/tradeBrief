from datetime import date

import akshare as ak


def is_trading_day(check_date: date) -> bool:
    trade_dates = ak.tool_trade_date_hist_sina()
    trade_date_set = set(trade_dates["trade_date"].tolist())
    return check_date in trade_date_set
