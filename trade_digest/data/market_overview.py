# trade_digest/data/market_overview.py
import logging
from datetime import date, timedelta

import akshare as ak

from trade_digest.timeout import with_timeout

logger = logging.getLogger(__name__)

MAJOR_INDEX_CODES = {"sh000001", "sz399001", "sz399006", "sh000300", "sh000688"}


def fetch_index_snapshot() -> list[dict] | None:
    """Fetch A-share major index snapshots with fallback data source."""
    try:
        df = with_timeout(ak.stock_zh_index_spot_sina)
        df = df[df["代码"].isin(MAJOR_INDEX_CODES)]
        return [
            {"name": row["名称"], "price": float(row["最新价"]), "change_pct": float(row["涨跌幅"])}
            for _, row in df.iterrows()
        ]
    except Exception:
        logger.warning("Primary index source (sina) failed, trying fallback (eastmoney)")
        try:
            df = with_timeout(ak.stock_zh_index_daily, symbol="sh000001")  # 上证指数
            # stock_zh_index_daily 返回的是历史数据，取最新一行
            # 只需要上证指数作为最基础的 fallback
            latest = df.iloc[-1]
            return [{"name": "上证指数", "price": float(latest["close"]), "change_pct": float(latest.get("pct_chg", 0))}]
        except Exception:
            logger.exception("Both primary and fallback index sources failed")
            return None


def fetch_market_breadth() -> dict | None:
    try:
        df = with_timeout(ak.stock_market_activity_legu)
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
        df = with_timeout(
            ak.stock_margin_sse,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
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
        df = with_timeout(ak.index_us_stock_sina, symbol=".INX")
        latest = df.iloc[-1]
        return {"sp500_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch US market snapshot")
        return None


def fetch_asia_snapshot() -> dict | None:
    try:
        df = with_timeout(ak.index_global_hist_sina, symbol="日经225指数")
        latest = df.iloc[-1]
        return {"nikkei_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch Asia market snapshot (best-effort)")
        return None


def fetch_gold_spot_price() -> float | None:
    """International spot gold (伦敦金/XAU) in USD/oz — used for holdings.yaml's
    gold cost_price/alert comparisons, which are denominated in USD/oz, not the
    domestic gold ETF's per-share CNY price (a different, unrelated number)."""
    try:
        df = with_timeout(ak.futures_foreign_commodity_realtime, symbol="XAU")
        return float(df.iloc[0]["最新价"])
    except Exception:
        logger.exception("Failed to fetch international gold spot price")
        return None


def fetch_hk_snapshot() -> dict | None:
    """获取恒生指数收盘价，使用 ak.stock_hk_index_daily_sina(symbol="HSI")。"""
    try:
        df = with_timeout(ak.stock_hk_index_daily_sina, symbol="HSI")
        latest = df.iloc[-1]
        return {"hsi_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch Hong Kong market snapshot (best-effort)")
        return None


def fetch_market_overview(session: str) -> dict:
    return {
        "indices": fetch_index_snapshot(),
        "breadth": fetch_market_breadth(),
        "margin": fetch_margin_ratio(),
        "us_market": fetch_us_market_snapshot(),
        "asia_market": fetch_asia_snapshot() if session == "morning" else None,
        "hk_market": fetch_hk_snapshot(),
    }
