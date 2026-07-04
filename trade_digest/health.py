# trade_digest/health.py
import json
from datetime import date
from pathlib import Path

_HEALTH_FILE_DEFAULT = Path(__file__).parent.parent / "state" / "health.json"

# 需要健康检查的组件 key，供 main.py 和 check_recent_health 共同引用
KEY_LLM = "llm"
KEY_EMAIL = "email"

# 健康检查规则：(key, label, advice)
_HEALTH_CHECKS = [
    (KEY_LLM, "LLM 调用", "请检查 API key 和额度"),
    (KEY_EMAIL, "邮件发送", "请检查 SMTP 配置"),
]


def record_run_result(
    run_date: date,
    session: str,
    trading_day: bool,
    components: dict[str, bool],
    health_file: Path | None = None,
) -> None:
    """Append a run result record to the health JSON log."""
    target = health_file or _HEALTH_FILE_DEFAULT
    target.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if target.exists():
        try:
            records = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            records = []

    records.append({
        "date": run_date.isoformat(),
        "session": session,
        "trading_day": trading_day,
        "components": components,
    })

    # 只保留最近 90 条记录，防止无限增长
    if len(records) > 90:
        records = records[-90:]

    target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def check_recent_health(health_file: Path | None = None, window: int = 5) -> list[str]:
    """Check recent health records and return alert messages if issues found.

    Returns a list of warning strings. Empty list means all clear.
    """
    target = health_file or _HEALTH_FILE_DEFAULT

    if not target.exists():
        return []

    try:
        records = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    recent = records[-window:]
    warnings = []

    for key, label, advice in _HEALTH_CHECKS:
        failures = sum(1 for r in recent if not r.get("components", {}).get(key, True))
        if failures >= min(3, len(recent)):
            warnings.append(f"⚠️ {label} 最近 {failures}/{len(recent)} 次运行失败，{advice}")

    return warnings
