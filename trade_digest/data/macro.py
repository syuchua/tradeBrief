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
        if df.empty:
            return []
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


_FOCUS_KEYWORDS = [
    "利率", "降息", "加息", "CPI", "PPI", "PMI", "非农", "失业率", "GDP",
    "零售销售", "贸易帐", "社融", "M2", "LPR", "议息", "联储", "美联储", "央行", "PCE",
]

_CONDENSE_GROUPS = {
    "油气数据": ["原油", "石油", "天然气", "钻井"],
    "贵金属持仓": ["黄金", "白银", "铂金", "钯金", "COMEX", "NYMEX", "iShares", "SPDR"],
}


def condense_macro_updates(macro_updates: list[dict]) -> dict:
    highlights = []
    condensed_counts: dict[str, int] = {}
    for update in macro_updates:
        event = update["event"]
        if any(keyword in event for keyword in _FOCUS_KEYWORDS):
            highlights.append(update)
            continue
        group = next(
            (name for name, keywords in _CONDENSE_GROUPS.items() if any(keyword in event for keyword in keywords)),
            "其他",
        )
        condensed_counts[group] = condensed_counts.get(group, 0) + 1
    return {"highlights": highlights, "condensed_counts": condensed_counts}
