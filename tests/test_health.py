from datetime import date
from trade_digest.health import record_run_result, check_recent_health, KEY_LLM, KEY_EMAIL


def test_record_and_check_health(tmp_path):
    health_file = tmp_path / "health.json"
    record_run_result(date(2026, 7, 1), "morning", True, {KEY_LLM: True, KEY_EMAIL: True}, health_file)
    record_run_result(date(2026, 7, 1), "evening", True, {KEY_LLM: False, KEY_EMAIL: True}, health_file)
    record_run_result(date(2026, 7, 2), "morning", True, {KEY_LLM: False, KEY_EMAIL: True}, health_file)
    record_run_result(date(2026, 7, 2), "evening", True, {KEY_LLM: False, KEY_EMAIL: True}, health_file)

    warnings = check_recent_health(health_file, window=3)
    assert any("LLM" in w for w in warnings)


def test_check_health_returns_empty_for_clean_records(tmp_path):
    health_file = tmp_path / "health.json"
    record_run_result(date(2026, 7, 1), "morning", True, {KEY_LLM: True, KEY_EMAIL: True}, health_file)
    assert check_recent_health(health_file) == []


def test_check_health_returns_empty_when_file_missing(tmp_path):
    assert check_recent_health(tmp_path / "nonexistent.json") == []
