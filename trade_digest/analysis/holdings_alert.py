import operator
import re

_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}

_CONDITION_PATTERN = re.compile(r"^(\w+)\s*(>=|<=|>|<|==)\s*(-?\d+(?:\.\d+)?)$")


def parse_condition(condition: str) -> tuple[str, str, float]:
    match = _CONDITION_PATTERN.match(condition.strip())
    if not match:
        raise ValueError(f"Unsupported condition format: {condition!r}")
    field, op_symbol, value = match.groups()
    return field, op_symbol, float(value)


def evaluate_alerts(position: dict) -> list[dict]:
    triggered = []
    if position.get("price") is None:
        return triggered
    for alert in position.get("alerts", []):
        field, op_symbol, threshold = parse_condition(alert["condition"])
        field_value = position.get(field)
        if field_value is None:
            continue
        if _OPERATORS[op_symbol](field_value, threshold):
            triggered.append({"name": position["name"], "action": alert["action"], "condition": alert["condition"]})
    return triggered
