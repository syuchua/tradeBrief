import json
from datetime import date
from pathlib import Path


def is_dca_strategy_due(refresh_days: int, today: date, state_file: Path) -> bool:
    if not state_file.exists():
        return True
    data = json.loads(state_file.read_text(encoding="utf-8"))
    last_run = date.fromisoformat(data["last_run"])
    return (today - last_run).days >= refresh_days


def save_dca_strategy_run_date(today: date, state_file: Path) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"last_run": today.isoformat()}), encoding="utf-8")
