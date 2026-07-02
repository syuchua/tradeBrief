from pathlib import Path

from trade_digest.config.loader import load_settings, load_holdings


def test_load_settings_reads_yaml(tmp_path):
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("sector_flow:\n  top_n: 10\n", encoding="utf-8")

    result = load_settings(settings_file)

    assert result == {"sector_flow": {"top_n": 10}}


def test_load_holdings_reads_yaml(tmp_path):
    holdings_file = tmp_path / "holdings.yaml"
    holdings_file.write_text("as_of: 2026-07-02\ncategories: {}\n", encoding="utf-8")

    result = load_holdings(holdings_file)

    assert result["categories"] == {}
