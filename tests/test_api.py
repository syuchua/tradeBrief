from datetime import date
from unittest.mock import patch, MagicMock, PropertyMock

from trade_digest.api import generate_report, export_html, export_markdown, ReportContext


def _patch_collect_data():
    """Mock _collect_data 返回最小有效数据。"""
    return patch("trade_digest.api._collect_data", return_value={
        "settings": {"macro": {"surprise_threshold_pct": 10}, "email": {"recipients": ["test@test.com"]}},
        "holdings": {"categories": {}},
        "market_overview": {"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None},
        "sector_flow": None,
        "watchlist_quotes": [],
        "holdings_flat": [],
        "triggered_alerts": [],
        "tactical_positions": [],
        "macro_highlights": [],
        "macro_condensed_counts": {},
        "news_items": [],
        "dca_due": False,
        "health_warnings": [],
    })


@patch("trade_digest.api.render_email", return_value="<html><body>test</body></html>")
@patch("trade_digest.api.get_llm_client")
@patch("trade_digest.api.synthesize_report", return_value={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None})
def test_generate_report_returns_report_context(mock_synth, mock_llm, mock_render):
    with _patch_collect_data():
        report = generate_report("morning", date(2026, 7, 3), enable_llm=True)
    assert isinstance(report, ReportContext)
    assert report.session == "morning"
    assert report.html == "<html><body>test</body></html>"
    assert report.llm_result["market_summary"] == "ok"


@patch("trade_digest.api.render_email", return_value="<html><body>no llm</body></html>")
def test_generate_report_skips_llm_when_disabled(mock_render):
    with _patch_collect_data():
        report = generate_report("morning", date(2026, 7, 3), enable_llm=False)
    assert report.llm_result is None
    assert "no llm" in report.html


def test_export_html_writes_file(tmp_path):
    with _patch_collect_data(), \
         patch("trade_digest.api.setup_logging"), \
         patch("trade_digest.api.render_email", return_value="<html><body>export test</body></html>"), \
         patch("trade_digest.api.get_llm_client"), \
         patch("trade_digest.api.synthesize_report", return_value={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None}):
        path = export_html("morning", date(2026, 7, 3), output_dir=tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "export test" in content
    assert path.suffix == ".html"


def test_export_markdown_writes_file(tmp_path):
    html = "<h1>标题</h1><p>内容</p><ul><li>项目一</li><li>项目二</li></ul>"
    with _patch_collect_data(), \
         patch("trade_digest.api.setup_logging"), \
         patch("trade_digest.api.render_email", return_value=html), \
         patch("trade_digest.api.get_llm_client"), \
         patch("trade_digest.api.synthesize_report", return_value={"market_summary": "ok", "sector_highlights": "ok", "macro_commentary": None, "tactical_scores": [], "priority_alerts": [], "dca_strategy": None}):
        path = export_markdown("evening", date(2026, 7, 3), output_dir=tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# 标题" in content
    assert "- 项目一" in content
    assert path.suffix == ".md"
