import logging

import akshare as ak

from trade_digest.timeout import with_timeout

logger = logging.getLogger(__name__)


def fetch_recent_news(limit: int) -> list[dict]:
    try:
        df = with_timeout(ak.stock_news_main_cx)
        df = df.head(limit)
        return [{"tag": row["tag"], "summary": row["summary"], "url": row["url"]} for _, row in df.iterrows()]
    except Exception:
        logger.exception("Failed to fetch financial news")
        return []
