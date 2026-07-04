# tests/notify/test_emailer.py
from unittest.mock import patch, MagicMock

from trade_digest.notify.emailer import render_email, send_email


def test_render_email_includes_core_sections_with_llm_result():
    html = render_email(
        session="morning",
        report_date="2026-07-02",
        market_overview={"indices": [{"name": "上证指数", "price": 3400.0, "change_pct": 0.5}], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow={"top_inflow": [{"name": "半导体", "change_pct": 3.5, "net_inflow": 50000.0}], "top_outflow": []},
        watchlist_quotes=[{"code": "513100", "name": "纳指ETF", "price": 1.5, "change_pct": 1.1}],
        macro_updates=[],
        macro_condensed_counts={},
        triggered_alerts=[{"name": "黄金", "action": "减仓至10%以下", "condition": "price >= 4380"}],
        tactical_positions=[{"name": "黄金", "price": 4380}],
        news_items=[{"tag": "市场", "summary": "消息一", "url": "https://a"}],
        priority_alerts=[],
        llm_result={"market_summary": "大盘平稳", "sector_highlights": "半导体流入", "macro_commentary": None, "tactical_scores": [{"name": "黄金", "score": "中性", "reason": "接近目标价"}], "priority_alerts": [], "dca_strategy": None},
    )

    assert "早盘" in html
    assert "2026-07-02" in html
    assert "上证指数" in html
    assert "半导体" in html
    assert "纳指ETF" in html
    assert "减仓至10%以下" in html
    assert "大盘平稳" in html
    assert "AI解读生成失败" not in html


def test_render_email_shows_fallback_banner_when_llm_result_is_none():
    html = render_email(
        session="evening",
        report_date="2026-07-02",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[],
        macro_condensed_counts={},
        triggered_alerts=[],
        tactical_positions=[{"name": "黄金", "price": 4360, "cost_price": 4350}],
        news_items=[],
        priority_alerts=[],
        llm_result=None,
    )

    assert "AI解读生成失败" in html
    assert "晚间" in html
    assert "黄金" in html
    assert "4360" in html


def test_render_email_highlights_tier_one_and_two_and_summarizes_tier_four():
    html = render_email(
        session="evening",
        report_date="2026-07-02",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[],
        macro_condensed_counts={},
        triggered_alerts=[],
        tactical_positions=[],
        news_items=[],
        priority_alerts=[
            {"tier": 2, "category": "宏观超预期", "summary": "非农大超预期", "reason": "偏离38.9%"},
            {"tier": 4, "category": "常规", "summary": "无关紧要的消息", "reason": "不关注板块"},
            {"tier": 4, "category": "常规", "summary": "另一条无关消息", "reason": "不关注板块"},
        ],
        llm_result={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None},
    )

    assert "非农大超预期" in html
    assert "无关紧要的消息" not in html
    assert "另有2条常规消息" in html


def test_render_email_never_leaks_none_for_missing_price_or_forecast():
    # Positions with no live price (e.g. a cash sub-position) and macro releases
    # with no consensus forecast are both legitimate real-world cases (confirmed
    # by manual end-to-end verification) — the literal string "None" must never
    # appear in the rendered HTML.
    html = render_email(
        session="evening",
        report_date="2026-07-02",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[{"region": "美国", "event": "美国某钻井数", "actual": 445.0, "forecast": None, "previous": 440.0, "importance": 1, "surprise_pct": None}],
        macro_condensed_counts={},
        triggered_alerts=[],
        tactical_positions=[{"name": "现金/子弹", "price": None}],
        news_items=[],
        priority_alerts=[],
        llm_result={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None},
    )

    assert "None" not in html
    assert "无实时报价" in html
    assert "无数据" in html


def test_render_email_shows_macro_condensed_counts_as_one_liner():
    html = render_email(
        session="evening",
        report_date="2026-07-02",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[],
        macro_condensed_counts={"油气数据": 4, "贵金属持仓": 12},
        triggered_alerts=[],
        tactical_positions=[],
        news_items=[],
        priority_alerts=[],
        llm_result=None,
    )

    assert "油气数据4项更新" in html
    assert "贵金属持仓12项更新" in html


def test_render_email_shows_health_warnings():
    html = render_email(
        session="morning",
        report_date="2026-07-03",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[],
        macro_condensed_counts={},
        triggered_alerts=[],
        tactical_positions=[],
        news_items=[],
        priority_alerts=[],
        llm_result={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None},
        health_warnings=["⚠️ LLM 调用最近 3/5 次运行失败，请检查 API key 和额度"],
    )

    assert "系统告警" in html
    assert "LLM 调用" in html
    assert "#fff3cd" in html
    assert "#ffa500" in html


def test_render_email_no_health_warnings_by_default():
    html = render_email(
        session="morning",
        report_date="2026-07-03",
        market_overview={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        sector_flow=None,
        watchlist_quotes=[],
        macro_updates=[],
        macro_condensed_counts={},
        triggered_alerts=[],
        tactical_positions=[],
        news_items=[],
        priority_alerts=[],
        llm_result=None,
    )

    assert "系统告警" not in html


def test_send_email_calls_smtp_with_expected_args():
    fake_server = MagicMock()
    with patch("trade_digest.notify.emailer.smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_smtp_ssl.return_value.__enter__.return_value = fake_server
        send_email(
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_user="me@example.com",
            smtp_password="secret",
            sender="me@example.com",
            recipients=["me@example.com"],
            subject="Test",
            html_body="<p>hi</p>",
        )

    mock_smtp_ssl.assert_called_once_with("smtp.example.com", 465)
    fake_server.login.assert_called_once_with("me@example.com", "secret")
    fake_server.sendmail.assert_called_once()
