from trade_digest.analysis.holdings_alert import evaluate_alerts, parse_condition


def test_parse_condition_extracts_field_operator_value():
    assert parse_condition("price >= 4380") == ("price", ">=", 4380.0)
    assert parse_condition("price<4300") == ("price", "<", 4300.0)


def test_evaluate_alerts_triggers_on_boundary():
    position = {
        "name": "黄金",
        "price": 4380,
        "alerts": [{"condition": "price >= 4380", "action": "减仓至10%以下"}],
    }
    result = evaluate_alerts(position)
    assert result == [{"name": "黄金", "action": "减仓至10%以下", "condition": "price >= 4380"}]


def test_evaluate_alerts_does_not_trigger_below_threshold():
    position = {
        "name": "黄金",
        "price": 4379.99,
        "alerts": [{"condition": "price >= 4380", "action": "减仓至10%以下"}],
    }
    assert evaluate_alerts(position) == []


def test_evaluate_alerts_skips_when_price_missing():
    position = {"name": "科技板块基金", "price": None, "alerts": [{"condition": "price >= 100", "action": "x"}]}
    assert evaluate_alerts(position) == []


def test_evaluate_alerts_handles_no_alerts_key():
    position = {"name": "现金", "price": None}
    assert evaluate_alerts(position) == []
