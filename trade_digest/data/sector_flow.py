# trade_digest/data/sector_flow.py
import logging

import akshare as ak

from trade_digest.timeout import with_timeout

logger = logging.getLogger(__name__)


def fetch_sector_flow_ranking(top_n: int) -> dict | None:
    try:
        df = with_timeout(ak.stock_fund_flow_concept, symbol="即时")
        df = df.sort_values("净额", ascending=False)
        top = df.head(top_n)
        remaining = df.iloc[top_n:]  # exclude rows already in `top` so inflow/outflow never overlap
        bottom = remaining.tail(top_n).sort_values("净额")

        def to_records(sub_df):
            return [
                {"name": row["行业"], "change_pct": float(row["行业-涨跌幅"]), "net_inflow": float(row["净额"])}
                for _, row in sub_df.iterrows()
            ]

        return {"top_inflow": to_records(top), "top_outflow": to_records(bottom)}
    except Exception:
        logger.exception("Failed to fetch sector fund flow ranking")
        return None


def fetch_etf_quotes(codes: list[str]) -> dict:
    if not codes:
        return {}
    try:
        df = with_timeout(ak.fund_etf_category_sina, symbol="ETF基金")
        df = df.assign(short_code=df["代码"].str[-6:])
        result = {}
        for code in codes:
            matches = df[df["short_code"] == code]
            if matches.empty:
                continue
            row = matches.iloc[0]
            result[code] = {
                "name": row["名称"],
                "price": float(row["最新价"]),
                "change_pct": float(row["涨跌幅"]),
            }
        return result
    except Exception:
        logger.exception("Failed to fetch ETF quotes")
        return {}
