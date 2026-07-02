# trade_digest/data/market_overview.py
import logging
from datetime import date, timedelta

import akshare as ak

logger = logging.getLogger(__name__)

MAJOR_INDEX_CODES = {"sh000001", "sz399001", "sz399006", "sh000300", "sh000688"}


def fetch_index_snapshot() -> list[dict] | None:
    try:
        df = ak.stock_zh_index_spot_sina()
        df = df[df["代码"].isin(MAJOR_INDEX_CODES)]
        return [
            {"name": row["名称"], "price": float(row["最新价"]), "change_pct": float(row["涨跌幅"])}
            for _, row in df.iterrows()
        ]
    except Exception:
        logger.exception("Failed to fetch index snapshot")
        return None


def fetch_market_breadth() -> dict | None:
    try:
        df = ak.stock_market_activity_legu()
        values = dict(zip(df["item"], df["value"]))
        return {
            "up_count": int(values["上涨"]),
            "down_count": int(values["下跌"]),
            "limit_up": int(values["涨停"]),
            "limit_down": int(values["跌停"]),
        }
    except Exception:
        logger.exception("Failed to fetch market breadth")
        return None


def fetch_margin_ratio() -> dict | None:
    try:
        end = date.today()
        start = end - timedelta(days=10)
        df = ak.stock_margin_sse(start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
        latest = df.iloc[-1]
        return {
            "financing_balance": float(latest["融资余额"]),
            "financing_buy": float(latest["融资买入额"]),
        }
    except Exception:
        logger.exception("Failed to fetch margin ratio")
        return None


def fetch_us_market_snapshot() -> dict | None:
    try:
        df = ak.index_us_stock_sina(symbol=".INX")
        latest = df.iloc[-1]
        return {"sp500_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch US market snapshot")
        return None


def fetch_asia_snapshot() -> dict | None:
    try:
        df = ak.index_global_hist_sina(symbol="日经225指数")
        latest = df.iloc[-1]
        return {"nikkei_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch Asia market snapshot (best-effort)")
        return None


def fetch_market_overview(session: str) -> dict:
    return {
        "indices": fetch_index_snapshot(),
        "breadth": fetch_market_breadth(),
        "margin": fetch_margin_ratio(),
        "us_market": fetch_us_market_snapshot(),
        "asia_market": fetch_asia_snapshot() if session == "morning" else None,
    }
