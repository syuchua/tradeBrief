from datetime import date

from trade_digest.state import is_dca_strategy_due, save_dca_strategy_run_date


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
