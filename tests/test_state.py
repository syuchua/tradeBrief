from datetime import date

from trade_digest.state import is_dca_strategy_due, load_llm_cache, save_dca_strategy_run_date, save_llm_cache


def test_due_when_state_file_missing(tmp_path):
    state_file = tmp_path / "dca_strategy_last_run.json"

    assert is_dca_strategy_due(7, date(2026, 7, 2), state_file) is True


def test_not_due_within_refresh_window(tmp_path):
    state_file = tmp_path / "dca_strategy_last_run.json"
    save_dca_strategy_run_date(date(2026, 6, 28), state_file)

    assert is_dca_strategy_due(7, date(2026, 7, 2), state_file) is False


def test_due_after_refresh_window(tmp_path):
    state_file = tmp_path / "dca_strategy_last_run.json"
    save_dca_strategy_run_date(date(2026, 6, 20), state_file)

    assert is_dca_strategy_due(7, date(2026, 7, 2), state_file) is True


def test_save_creates_parent_dirs(tmp_path):
    state_file = tmp_path / "nested" / "dca_strategy_last_run.json"

    save_dca_strategy_run_date(date(2026, 7, 2), state_file)

    assert state_file.exists()


def test_load_llm_cache_returns_none_for_missing_file(tmp_path):
    assert load_llm_cache(tmp_path / "nonexistent.json", "2026-07-02_morning") is None


def test_save_and_load_llm_cache_roundtrip(tmp_path):
    cache_file = tmp_path / "llm_cache.json"
    result = {"market_summary": "test"}
    save_llm_cache(cache_file, "2026-07-02_morning", result)
    loaded = load_llm_cache(cache_file, "2026-07-02_morning")
    assert loaded == result


def test_load_llm_cache_returns_none_for_wrong_key(tmp_path):
    cache_file = tmp_path / "llm_cache.json"
    save_llm_cache(cache_file, "2026-07-02_morning", {"x": 1})
    assert load_llm_cache(cache_file, "2026-07-02_evening") is None
