# trade_digest/analysis/synthesize.py
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名严谨、克制的证券分析助手，为个人投资者生成A股盘中/盘后简报。
只做参考性判断，不给绝对化买卖建议，对不确定的信息明确标注不确定性。

你会收到一个结构化JSON，包含：market_overview（大盘概览）、sector_flow（板块资金流）、
watchlist_quotes（你关注的ETF清单当前行情，可结合sector_flow一起解读）、
macro_updates（今日新发布的宏观数据，可能为空数组）、news_items（近期财经新闻原文标题/摘要）、
watchlist_tactical（需要打分的短线仓位和黄金持仓，每项含price/cost_price等字段）、
dca_strategy_due（是否需要生成定投策略参考）。

请返回一个JSON对象，包含以下字段：
- market_summary: 字符串，大盘概览解读
- sector_highlights: 字符串，板块资金流解读
- macro_commentary: 字符串或null，若macro_updates为空则为null
- tactical_scores: 数组，watchlist_tactical中每个标的对应一项 {"name":..., "score": "看多"|"中性"|"看空", "reason": "一句话理由"}
- priority_alerts: 数组，从news_items中筛选出的重要事件（不包括宏观数据，宏观数据的分级由其他规则单独处理），每项 {"tier": 1|2|3|4, "category": "黑天鹅"|"重大利空利好"|"财报订单"|"常规", "summary": "一句话", "reason": "一句话"}。
  第一档(黑天鹅/重大科技突破/泡沫破裂)应极少出现，多数情况下不应有第一档条目；第四档(对市场冲击不大或用户不关注板块)默认不需要在邮件中展开，仅统计数量。
- dca_strategy: 若dca_strategy_due为true，返回数组 {"name":..., "suggestion": "继续定投"|"可考虑加大"|"可考虑阶段性减少", "reason": "一句话理由"}；否则为null

只返回这个JSON对象，不要包含其他文字。"""


def build_payload(
    market_overview: dict,
    sector_flow: dict | None,
    watchlist_quotes: list[dict],
    macro_updates: list[dict],
    news_items: list[dict],
    tactical_positions: list[dict],
    dca_strategy_due: bool,
) -> dict:
    return {
        "market_overview": market_overview,
        "sector_flow": sector_flow,
        "watchlist_quotes": watchlist_quotes,
        "macro_updates": macro_updates,
        "news_items": news_items,
        "watchlist_tactical": tactical_positions,
        "dca_strategy_due": dca_strategy_due,
    }


def synthesize_report(llm_client, payload: dict) -> dict | None:
    try:
        return llm_client.generate(SYSTEM_PROMPT, payload)
    except Exception:
        logger.exception("LLM synthesis failed")
        return None


def build_macro_priority_alerts(macro_updates: list[dict], surprise_threshold_pct: float) -> list[dict]:
    """Tier-2 alerts for macro releases that deviate from forecast beyond the threshold.

    This is a deterministic rule (spec §8), not an LLM judgment call — it runs
    independently of synthesize_report and its output is merged with the LLM's
    (non-macro) priority_alerts by main.py.
    """
    alerts = []
    for update in macro_updates:
        surprise_pct = update.get("surprise_pct")
        if surprise_pct is None or surprise_pct < surprise_threshold_pct:
            continue
        alerts.append({
            "tier": 2,
            "category": "宏观超预期",
            "summary": f"[{update['region']}] {update['event']}: 公布{update['actual']} vs 预期{update['forecast']}",
            "reason": f"偏离预期 {surprise_pct:.1f}%",
        })
    return alerts
