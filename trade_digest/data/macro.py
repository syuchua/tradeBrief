# trade_digest/data/macro.py
import logging
from datetime import date

import akshare as ak

logger = logging.getLogger(__name__)


def _to_float(value) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if result != result:  # NaN check (NaN is the only float that isn't equal to itself)
            return None
        return result
    except (TypeError, ValueError):
        return None


def fetch_macro_calendar(regions: list[str], today: date) -> list[dict]:
    try:
        df = ak.news_economic_baidu(date=today.strftime("%Y%m%d"))
        df = df[df["地区"].isin(regions)]
        df = df[df["公布"].notna()]

        results = []
        for _, row in df.iterrows():
            actual = _to_float(row["公布"])
            forecast = _to_float(row["预期"])
            surprise_pct = None
            if actual is not None and forecast:
                surprise_pct = abs(actual - forecast) / abs(forecast) * 100
            results.append({
                "region": row["地区"],
                "event": row["事件"],
                "actual": actual,
                "forecast": forecast,
                "previous": _to_float(row["前值"]),
                "importance": row["重要性"],
                "surprise_pct": surprise_pct,
            })
        return results
    except Exception:
        logger.exception("Failed to fetch macro economic calendar")
        return []
