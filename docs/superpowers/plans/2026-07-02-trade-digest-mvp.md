# 金融趋势聚合分析工具 — Phase 1 (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `trade_digest` Python package that fetches A股/宏观/持仓数据, runs one structured LLM call, and emails a concise morning/evening digest, per `docs/superpowers/specs/2026-07-02-trade-digest-design.md`.

**Architecture:** A `data/` layer of small fetch functions (each wrapping one verified non-eastmoney akshare interface, catching its own exceptions and returning `None`/`[]` on failure), an `analysis/` layer that evaluates holdings-rule alerts and makes one structured-payload LLM call, and a `notify/` layer that renders and sends the HTML email. `main.py` wires these together behind `--session morning|evening`, gated by a trading-calendar check.

**Tech Stack:** Python 3.11, managed with `uv` (already initialized: `pyproject.toml`, `.venv`, `uv.lock`). Dependencies: `akshare`, `pyyaml`, `requests`, `pytest` (already installed via `uv add`).

## Global Constraints

- Python 3.11, all commands run via `uv run ...` (never bare `python`/`pytest`).
- Only use the non-eastmoney akshare interfaces verified in spec section 5 (`tool_trade_date_hist_sina`, `stock_zh_index_spot_sina`, `stock_market_activity_legu`, `stock_margin_sse`, `index_us_stock_sina`, `index_global_hist_sina`, `stock_fund_flow_concept`, `fund_etf_category_sina`, `news_economic_baidu`, `stock_news_main_cx`, `futures_foreign_commodity_realtime`). Never call `*_em` (eastmoney) functions — they are unreachable from this network.
- No real network calls in automated tests — every `akshare`/`requests`/`smtplib` call is mocked via `unittest.mock.patch`.
- Every data-fetch function catches its own exceptions internally and returns `None` (or `[]` for list-returning functions) on failure — callers never need to wrap fetch calls in `try/except`. The `try` block must wrap the ENTIRE function body (the raw API call AND all subsequent parsing/field access), not just the API call itself — a malformed or unexpected response shape must degrade the same way a network failure does.
- `holdings.yaml`/`settings.yaml` contain personal financial data and are gitignored; only `.example.yaml` templates are committed.
- Commit after every task using `git add <files> && git commit -m "..."`.

---

## File Structure

```
trade_digest/
├── __init__.py
├── state.py
├── config/
│   ├── __init__.py
│   ├── loader.py
│   ├── settings.example.yaml
│   └── holdings.example.yaml
├── data/
│   ├── __init__.py
│   ├── calendar.py
│   ├── market_overview.py
│   ├── sector_flow.py
│   ├── macro.py
│   ├── news.py
│   └── holdings_quotes.py
├── analysis/
│   ├── __init__.py
│   ├── holdings_alert.py
│   ├── llm_client.py
│   └── synthesize.py
├── notify/
│   ├── __init__.py
│   └── emailer.py
└── main.py
tests/
├── conftest.py
├── config/test_loader.py
├── test_state.py
├── data/
│   ├── test_calendar.py
│   ├── test_market_overview.py
│   ├── test_sector_flow.py
│   ├── test_macro.py
│   ├── test_news.py
│   └── test_holdings_quotes.py
├── analysis/
│   ├── test_holdings_alert.py
│   ├── test_llm_client.py
│   └── test_synthesize.py
├── notify/test_emailer.py
└── test_main.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `trade_digest/__init__.py` (empty)
- Create: `trade_digest/data/__init__.py` (empty)
- Create: `trade_digest/analysis/__init__.py` (empty)
- Create: `trade_digest/notify/__init__.py` (empty)
- Create: `trade_digest/config/__init__.py` (empty)
- Create: `trade_digest/config/settings.example.yaml`
- Create: `trade_digest/config/holdings.example.yaml`
- Create: `tests/conftest.py`
- Create: `tests/config/__init__.py`, `tests/data/__init__.py`, `tests/analysis/__init__.py`, `tests/notify/__init__.py` (empty)
- Modify: `pyproject.toml` — add `requests` dependency

**Interfaces:**
- Produces: `trade_digest/config/settings.example.yaml`, `trade_digest/config/holdings.example.yaml` — schemas every later task's config-consuming code depends on.

- [ ] **Step 1: Create package `__init__.py` files**

```bash
mkdir -p trade_digest/data trade_digest/analysis trade_digest/notify trade_digest/config
mkdir -p tests/config tests/data tests/analysis tests/notify
touch trade_digest/__init__.py trade_digest/data/__init__.py trade_digest/analysis/__init__.py trade_digest/notify/__init__.py trade_digest/config/__init__.py
touch tests/config/__init__.py tests/data/__init__.py tests/analysis/__init__.py tests/notify/__init__.py
```

- [ ] **Step 2: Create `tests/conftest.py` so `trade_digest` imports resolve regardless of packaging config**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

- [ ] **Step 3: Create `trade_digest/config/settings.example.yaml`**

```yaml
sector_flow:
  top_n: 10
  watchlist_etfs:
    - {name: 纳指, code: "513100"}
    - {name: 标普, code: "513500"}
    - {name: 恒生科技, code: "513180"}
    - {name: 红利, code: "510880"}
    - {name: 宽基, code: "510300"}
    - {name: 券商, code: "512880"}
    - {name: 黄金, code: "518880"}

macro:
  regions: ["中国", "美国"]
  surprise_threshold_pct: 10

dca_strategy:
  refresh_days: 7

news:
  fetch_limit: 20
  tier3_max_items: 5

email:
  recipients:
    - "you@example.com"
```

- [ ] **Step 4: Create `trade_digest/config/holdings.example.yaml`**

```yaml
as_of: 2026-07-02
categories:
  fund:
    total_weight: 0.40
    positions:
      - {name: 科技板块基金, code: null, weight_within_category: 0.5}
      - {name: 纳指, code: "513100", weight_within_category: 0.15}
      - {name: 标普, code: "513500", weight_within_category: 0.10}
      - {name: 恒生科技(定投), code: "513180", weight_within_category: 0.10}
      - {name: 红利, code: "510880", weight_within_category: 0.10}
      - {name: 宽基, code: "510300", weight_within_category: 0.05}

  gold:
    total_weight: 0.20
    positions:
      - name: 黄金
        code: "518880"  # kept for reference/watchlist display only — price for this category comes from fetch_gold_spot_price() (international spot, USD/oz), not this ETF code
        cost_price: 4350
        alerts:
          - {condition: "price >= 4380", action: "反弹至4380，考虑减仓至10%以下"}

  securities_trading:
    total_weight: 0.13
    positions:
      - {name: 券商, code: "512880", weight_within_category: 0.5}
      - {name: 恒生科技(短线), code: "513180", weight_within_category: 0.08, note: "已割肉一次"}
      - {name: 现金/子弹, code: null, weight_within_category: 0.42}
```

- [ ] **Step 5: Add `requests` dependency**

```bash
uv add requests
```

- [ ] **Step 6: Verify the venv still resolves and pytest runs (with nothing to collect yet)**

Run: `uv run pytest tests/ -v`
Expected: `no tests ran` (exit code 5) — confirms imports/config don't crash collection.

- [ ] **Step 7: Commit**

```bash
git add trade_digest tests pyproject.toml uv.lock
git commit -m "Scaffold trade_digest package structure and example configs"
```

---

### Task 2: Config loader

**Files:**
- Create: `trade_digest/config/loader.py`
- Test: `tests/config/test_loader.py`

**Interfaces:**
- Consumes: nothing
- Produces: `load_settings(path: pathlib.Path) -> dict`, `load_holdings(path: pathlib.Path) -> dict` — every later module that needs config calls these with an explicit path (no implicit default file lookup, so tests never touch the real gitignored config files).

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_loader.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.config.loader'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/config/loader.py
from pathlib import Path

import yaml


def load_settings(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_holdings(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_loader.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/config/loader.py tests/config/test_loader.py
git commit -m "Add YAML config loader for settings and holdings"
```

---

### Task 3: State cache (定投策略 refresh tracking)

**Files:**
- Create: `trade_digest/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing
- Produces: `is_dca_strategy_due(refresh_days: int, today: date, state_file: Path) -> bool`, `save_dca_strategy_run_date(today: date, state_file: Path) -> None` — used by `main.py` (Task 14).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/state.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/state.py tests/test_state.py
git commit -m "Add DCA strategy refresh-tracking state cache"
```

---

### Task 4: Trading calendar

**Files:**
- Create: `trade_digest/data/calendar.py`
- Test: `tests/data/test_calendar.py`

**Interfaces:**
- Consumes: `akshare.tool_trade_date_hist_sina()`
- Produces: `is_trading_day(check_date: date) -> bool` — used by `main.py` (Task 14) as the entry gate.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_calendar.py
from datetime import date
from unittest.mock import patch

import pandas as pd

from trade_digest.data.calendar import is_trading_day

FAKE_TRADE_DATES = pd.DataFrame({"trade_date": [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]})


def test_is_trading_day_true_for_known_trading_day():
    with patch("trade_digest.data.calendar.ak.tool_trade_date_hist_sina", return_value=FAKE_TRADE_DATES):
        assert is_trading_day(date(2026, 7, 2)) is True


def test_is_trading_day_false_for_weekend():
    with patch("trade_digest.data.calendar.ak.tool_trade_date_hist_sina", return_value=FAKE_TRADE_DATES):
        assert is_trading_day(date(2026, 7, 4)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_calendar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.calendar'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/calendar.py
from datetime import date

import akshare as ak


def is_trading_day(check_date: date) -> bool:
    trade_dates = ak.tool_trade_date_hist_sina()
    trade_date_set = set(trade_dates["trade_date"].tolist())
    return check_date in trade_date_set
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_calendar.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/data/calendar.py tests/data/test_calendar.py
git commit -m "Add A-share trading-day calendar check"
```

---

### Task 5: Market overview

**Files:**
- Create: `trade_digest/data/market_overview.py`
- Test: `tests/data/test_market_overview.py`

**Interfaces:**
- Consumes: `akshare.stock_zh_index_spot_sina()`, `akshare.stock_market_activity_legu()`, `akshare.stock_margin_sse()`, `akshare.index_us_stock_sina()`, `akshare.index_global_hist_sina()`
- Produces: `fetch_market_overview(session: str) -> dict` with keys `indices`, `breadth`, `margin`, `us_market`, `asia_market` (each `None` on failure) — consumed by `main.py` (Task 14) and fed into the LLM payload (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_market_overview.py
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd

from trade_digest.data.market_overview import (
    fetch_index_snapshot,
    fetch_market_breadth,
    fetch_margin_ratio,
    fetch_us_market_snapshot,
    fetch_asia_snapshot,
    fetch_gold_spot_price,
    fetch_market_overview,
)


def test_fetch_index_snapshot_filters_major_indices():
    fake_df = pd.DataFrame({
        "代码": ["sh000001", "sz399001", "sh600000"],
        "名称": ["上证指数", "深证成指", "浦发银行"],
        "最新价": [3400.5, 10500.2, 8.5],
        "涨跌幅": [0.5, -0.3, 1.2],
    })
    with patch("trade_digest.data.market_overview.ak.stock_zh_index_spot_sina", return_value=fake_df):
        result = fetch_index_snapshot()
    assert result == [
        {"name": "上证指数", "price": 3400.5, "change_pct": 0.5},
        {"name": "深证成指", "price": 10500.2, "change_pct": -0.3},
    ]


def test_fetch_index_snapshot_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_zh_index_spot_sina", side_effect=RuntimeError("boom")):
        assert fetch_index_snapshot() is None


def test_fetch_market_breadth_parses_long_format():
    fake_df = pd.DataFrame({
        "item": ["上涨", "涨停", "下跌", "跌停", "统计日期"],
        "value": [2112.0, 158.0, 2955.0, 44.0, "2026-07-02 15:00:00"],
    })
    with patch("trade_digest.data.market_overview.ak.stock_market_activity_legu", return_value=fake_df):
        result = fetch_market_breadth()
    assert result == {"up_count": 2112, "down_count": 2955, "limit_up": 158, "limit_down": 44}


def test_fetch_market_breadth_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_market_activity_legu", side_effect=RuntimeError("boom")):
        assert fetch_market_breadth() is None


def test_fetch_margin_ratio_takes_latest_row():
    fake_df = pd.DataFrame({
        "信用交易日期": ["20260630", "20260701"],
        "融资余额": [1000000.0, 1010000.0],
        "融资买入额": [50000.0, 52000.0],
    })
    with patch("trade_digest.data.market_overview.ak.stock_margin_sse", return_value=fake_df):
        result = fetch_margin_ratio()
    assert result == {"financing_balance": 1010000.0, "financing_buy": 52000.0}


def test_fetch_margin_ratio_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.stock_margin_sse", side_effect=RuntimeError("boom")):
        assert fetch_margin_ratio() is None


def test_fetch_us_market_snapshot_reads_latest_close():
    fake_df = pd.DataFrame({
        "date": [date(2026, 6, 30), date(2026, 7, 1)],
        "close": [7441.27, 7483.23],
    })
    with patch("trade_digest.data.market_overview.ak.index_us_stock_sina", return_value=fake_df):
        result = fetch_us_market_snapshot()
    assert result == {"sp500_close": 7483.23}


def test_fetch_asia_snapshot_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.index_global_hist_sina", side_effect=RuntimeError("boom")):
        assert fetch_asia_snapshot() is None


def test_fetch_gold_spot_price_reads_latest_price():
    fake_df = pd.DataFrame({"名称": ["伦敦金"], "最新价": [4167.91]})
    with patch("trade_digest.data.market_overview.ak.futures_foreign_commodity_realtime", return_value=fake_df):
        assert fetch_gold_spot_price() == 4167.91


def test_fetch_gold_spot_price_returns_none_on_error():
    with patch("trade_digest.data.market_overview.ak.futures_foreign_commodity_realtime", side_effect=RuntimeError("boom")):
        assert fetch_gold_spot_price() is None


def test_fetch_market_overview_includes_asia_only_for_morning():
    with patch("trade_digest.data.market_overview.fetch_index_snapshot", return_value=[]), \
         patch("trade_digest.data.market_overview.fetch_market_breadth", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_margin_ratio", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_us_market_snapshot", return_value=None), \
         patch("trade_digest.data.market_overview.fetch_asia_snapshot", return_value={"nikkei_close": 39000.0}) as asia_mock:
        morning = fetch_market_overview("morning")
        evening = fetch_market_overview("evening")

    assert morning["asia_market"] == {"nikkei_close": 39000.0}
    assert evening["asia_market"] is None
    asia_mock.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_market_overview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.market_overview'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/market_overview.py
import logging
from datetime import date, timedelta

import akshare as ak

logger = logging.getLogger(__name__)

MAJOR_INDEX_CODES = {"sh000001", "sz399001", "sz399006", "sh000300", "sh000688"}


def fetch_index_snapshot() -> list[dict] | None:
    try:
        df = ak.stock_zh_index_spot_sina()
        df = df[df["代码"].isin(MAJOR_INDEX_CODES)]
        return [
            {"name": row["名称"], "price": float(row["最新价"]), "change_pct": float(row["涨跌幅"])}
            for _, row in df.iterrows()
        ]
    except Exception:
        logger.exception("Failed to fetch index snapshot")
        return None


def fetch_market_breadth() -> dict | None:
    try:
        df = ak.stock_market_activity_legu()
        values = dict(zip(df["item"], df["value"]))
        return {
            "up_count": int(values["上涨"]),
            "down_count": int(values["下跌"]),
            "limit_up": int(values["涨停"]),
            "limit_down": int(values["跌停"]),
        }
    except Exception:
        logger.exception("Failed to fetch market breadth")
        return None


def fetch_margin_ratio() -> dict | None:
    try:
        end = date.today()
        start = end - timedelta(days=10)
        df = ak.stock_margin_sse(start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
        latest = df.iloc[-1]
        return {
            "financing_balance": float(latest["融资余额"]),
            "financing_buy": float(latest["融资买入额"]),
        }
    except Exception:
        logger.exception("Failed to fetch margin ratio")
        return None


def fetch_us_market_snapshot() -> dict | None:
    try:
        df = ak.index_us_stock_sina(symbol=".INX")
        latest = df.iloc[-1]
        return {"sp500_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch US market snapshot")
        return None


def fetch_asia_snapshot() -> dict | None:
    try:
        df = ak.index_global_hist_sina(symbol="NKY")
        latest = df.iloc[-1]
        return {"nikkei_close": float(latest["close"])}
    except Exception:
        logger.exception("Failed to fetch Asia market snapshot (best-effort)")
        return None


def fetch_gold_spot_price() -> float | None:
    """International spot gold (伦敦金/XAU) in USD/oz — used for holdings.yaml's
    gold cost_price/alert comparisons, which are denominated in USD/oz, not the
    domestic gold ETF's per-share CNY price (a different, unrelated number)."""
    try:
        df = ak.futures_foreign_commodity_realtime(symbol="XAU")
        return float(df.iloc[0]["最新价"])
    except Exception:
        logger.exception("Failed to fetch international gold spot price")
        return None


def fetch_market_overview(session: str) -> dict:
    return {
        "indices": fetch_index_snapshot(),
        "breadth": fetch_market_breadth(),
        "margin": fetch_margin_ratio(),
        "us_market": fetch_us_market_snapshot(),
        "asia_market": fetch_asia_snapshot() if session == "morning" else None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_market_overview.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Manually confirm the `index_global_hist_sina` symbol against live data**

The spec flags this call as best-effort because `symbol="NKY"` raised `KeyError` in exploratory testing. Run this once against the real network to find the working symbol format, and update `fetch_asia_snapshot` if needed (it degrades to `None` either way, so this step only improves data completeness, it does not block the task):

```bash
uv run python -c "
import akshare as ak
print(ak.index_global_name_table().to_string())
try:
    print(ak.index_global_hist_sina(symbol='NKY').tail(2))
except Exception as e:
    print('still failing:', e)
"
```

If a working symbol/format is found, update the `symbol=` argument in `fetch_asia_snapshot` accordingly and re-run Step 4's tests to confirm they still pass (the tests mock the call, so they pass regardless — this is purely a live-data correctness fix).

- [ ] **Step 6: Commit**

```bash
git add trade_digest/data/market_overview.py tests/data/test_market_overview.py
git commit -m "Add market overview data fetch (indices, breadth, margin, US/Asia snapshots)"
```

---

### Task 6: Sector fund flow and ETF quotes

**Files:**
- Create: `trade_digest/data/sector_flow.py`
- Test: `tests/data/test_sector_flow.py`

**Interfaces:**
- Consumes: `akshare.stock_fund_flow_concept()`, `akshare.fund_etf_category_sina()`
- Produces: `fetch_sector_flow_ranking(top_n: int) -> dict | None` (keys `top_inflow`, `top_outflow`), `fetch_etf_quotes(codes: list[str]) -> dict[str, dict]` (keyed by 6-digit code, values have `name`/`price`/`change_pct`) — both consumed by `main.py` (Task 14); `fetch_etf_quotes` is also imported by `trade_digest/data/holdings_quotes.py` (Task 7).

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_sector_flow.py
from unittest.mock import patch

import pandas as pd

from trade_digest.data.sector_flow import fetch_sector_flow_ranking, fetch_etf_quotes


def _fake_concept_df():
    return pd.DataFrame({
        "行业": ["半导体", "白酒", "煤炭"],
        "行业-涨跌幅": [3.5, -1.2, -2.8],
        "净额": [50000.0, -10000.0, -30000.0],
    })


def test_fetch_sector_flow_ranking_sorts_by_net_inflow():
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", return_value=_fake_concept_df()):
        result = fetch_sector_flow_ranking(top_n=2)

    assert result["top_inflow"][0] == {"name": "半导体", "change_pct": 3.5, "net_inflow": 50000.0}
    assert result["top_outflow"][0] == {"name": "煤炭", "change_pct": -2.8, "net_inflow": -30000.0}


def test_fetch_sector_flow_ranking_top_and_bottom_never_overlap():
    # 3 rows, top_n=2: without exclusion, head(2) and tail(2) would both include row 1 ("白酒").
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", return_value=_fake_concept_df()):
        result = fetch_sector_flow_ranking(top_n=2)

    top_names = {r["name"] for r in result["top_inflow"]}
    bottom_names = {r["name"] for r in result["top_outflow"]}
    assert top_names.isdisjoint(bottom_names)


def test_fetch_sector_flow_ranking_returns_none_on_error():
    with patch("trade_digest.data.sector_flow.ak.stock_fund_flow_concept", side_effect=RuntimeError("boom")):
        assert fetch_sector_flow_ranking(top_n=5) is None


def _fake_etf_df():
    return pd.DataFrame({
        "代码": ["sz159998", "sh513100", "sh518880"],
        "名称": ["计算机ETF天弘", "纳指ETF", "黄金ETF"],
        "最新价": [1.014, 1.5, 6.2],
        "涨跌幅": [-4.789, 1.1, 0.3],
    })


def test_fetch_etf_quotes_matches_by_six_digit_code():
    with patch("trade_digest.data.sector_flow.ak.fund_etf_category_sina", return_value=_fake_etf_df()):
        result = fetch_etf_quotes(["513100", "518880", "999999"])

    assert result["513100"] == {"name": "纳指ETF", "price": 1.5, "change_pct": 1.1}
    assert result["518880"] == {"name": "黄金ETF", "price": 6.2, "change_pct": 0.3}
    assert "999999" not in result


def test_fetch_etf_quotes_returns_empty_dict_on_error():
    with patch("trade_digest.data.sector_flow.ak.fund_etf_category_sina", side_effect=RuntimeError("boom")):
        assert fetch_etf_quotes(["513100"]) == {}


def test_fetch_etf_quotes_returns_empty_dict_for_no_codes():
    assert fetch_etf_quotes([]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_sector_flow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.sector_flow'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/sector_flow.py
import logging

import akshare as ak

logger = logging.getLogger(__name__)


def fetch_sector_flow_ranking(top_n: int) -> dict | None:
    try:
        df = ak.stock_fund_flow_concept(symbol="即时")
        df = df.sort_values("净额", ascending=False)
        top = df.head(top_n)
        remaining = df.iloc[top_n:]  # exclude rows already in `top` so inflow/outflow never overlap
        bottom = remaining.tail(top_n).sort_values("净额")

        def to_records(sub_df):
            return [
                {"name": row["行业"], "change_pct": float(row["行业-涨跌幅"]), "net_inflow": float(row["净额"])}
                for _, row in sub_df.iterrows()
            ]

        return {"top_inflow": to_records(top), "top_outflow": to_records(bottom)}
    except Exception:
        logger.exception("Failed to fetch sector fund flow ranking")
        return None


def fetch_etf_quotes(codes: list[str]) -> dict:
    if not codes:
        return {}
    try:
        df = ak.fund_etf_category_sina(symbol="ETF基金")
        df = df.assign(short_code=df["代码"].str[-6:])
        result = {}
        for code in codes:
            matches = df[df["short_code"] == code]
            if matches.empty:
                continue
            row = matches.iloc[0]
            result[code] = {
                "name": row["名称"],
                "price": float(row["最新价"]),
                "change_pct": float(row["涨跌幅"]),
            }
        return result
    except Exception:
        logger.exception("Failed to fetch ETF quotes")
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_sector_flow.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/data/sector_flow.py tests/data/test_sector_flow.py
git commit -m "Add sector fund flow ranking and ETF quote lookup"
```

---

### Task 7: Holdings quotes enrichment

**Files:**
- Create: `trade_digest/data/holdings_quotes.py`
- Test: `tests/data/test_holdings_quotes.py`

**Interfaces:**
- Consumes: `trade_digest.data.sector_flow.fetch_etf_quotes(codes: list[str]) -> dict`
- Produces: `enrich_holdings_with_quotes(holdings: dict) -> list[dict]` — a flat list of positions (each with `category`, `name`, `code`, `price`, and any other keys from `holdings.yaml` like `cost_price`/`alerts`/`weight_within_category` preserved). Consumed by `main.py` (Task 14) and `analysis/holdings_alert.py` (Task 8).

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_holdings_quotes.py
from unittest.mock import patch

from trade_digest.data.holdings_quotes import enrich_holdings_with_quotes

HOLDINGS = {
    "categories": {
        "fund": {
            "total_weight": 0.40,
            "positions": [
                {"name": "科技板块基金", "code": None, "weight_within_category": 0.5},
                {"name": "纳指", "code": "513100", "weight_within_category": 0.15},
            ],
        },
        "gold": {
            "total_weight": 0.20,
            "positions": [
                {"name": "黄金", "code": "518880", "cost_price": 4350, "alerts": [{"condition": "price >= 4380", "action": "减仓"}]},
            ],
        },
    }
}


def test_enrich_holdings_flattens_categories_and_attaches_price():
    fake_quotes = {"513100": {"name": "纳指ETF", "price": 1.55, "change_pct": 0.4}}
    with patch("trade_digest.data.holdings_quotes.fetch_etf_quotes", return_value=fake_quotes) as mock_fetch, \
         patch("trade_digest.data.holdings_quotes.fetch_gold_spot_price", return_value=4360.5) as mock_gold:
        result = enrich_holdings_with_quotes(HOLDINGS)

    mock_fetch.assert_called_once_with(["513100"])
    mock_gold.assert_called_once()
    by_name = {p["name"]: p for p in result}
    assert by_name["纳指"]["category"] == "fund"
    assert by_name["纳指"]["price"] == 1.55
    assert by_name["黄金"]["price"] == 4360.5
    assert by_name["黄金"]["cost_price"] == 4350
    assert by_name["科技板块基金"]["price"] is None


def test_enrich_holdings_handles_no_codes():
    holdings = {"categories": {"fund": {"total_weight": 1.0, "positions": [{"name": "现金", "code": None}]}}}
    with patch("trade_digest.data.holdings_quotes.fetch_etf_quotes", return_value={}) as mock_fetch, \
         patch("trade_digest.data.holdings_quotes.fetch_gold_spot_price") as mock_gold:
        result = enrich_holdings_with_quotes(holdings)

    mock_fetch.assert_called_once_with([])
    mock_gold.assert_not_called()
    assert result[0]["price"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_holdings_quotes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.holdings_quotes'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/holdings_quotes.py
from trade_digest.data.sector_flow import fetch_etf_quotes
from trade_digest.data.market_overview import fetch_gold_spot_price


def enrich_holdings_with_quotes(holdings: dict) -> list[dict]:
    flat = []
    for category, cat_data in holdings["categories"].items():
        for position in cat_data["positions"]:
            flat.append({**position, "category": category})

    codes = [p["code"] for p in flat if p.get("code") and p["category"] != "gold"]
    quotes = fetch_etf_quotes(codes)
    gold_price = fetch_gold_spot_price() if any(p["category"] == "gold" for p in flat) else None

    for position in flat:
        if position["category"] == "gold":
            position["price"] = gold_price
            continue
        code = position.get("code")
        quote = quotes.get(code) if code else None
        position["price"] = quote["price"] if quote else None

    return flat
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_holdings_quotes.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/data/holdings_quotes.py tests/data/test_holdings_quotes.py
git commit -m "Add holdings flattening and live-price enrichment"
```

---

### Task 8: Holdings alert rules

**Files:**
- Create: `trade_digest/analysis/holdings_alert.py`
- Test: `tests/analysis/test_holdings_alert.py`

**Interfaces:**
- Consumes: a position dict shaped like `enrich_holdings_with_quotes` output (`price`, `alerts: [{"condition": str, "action": str}]`)
- Produces: `evaluate_alerts(position: dict) -> list[dict]` returning triggered `{"name": str, "action": str, "condition": str}` entries — consumed by `main.py` (Task 14).

- [ ] **Step 1: Write the failing tests**

```python
# tests/analysis/test_holdings_alert.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/analysis/test_holdings_alert.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.analysis.holdings_alert'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/analysis/holdings_alert.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/analysis/test_holdings_alert.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/analysis/holdings_alert.py tests/analysis/test_holdings_alert.py
git commit -m "Add structured condition parsing and holdings alert evaluation"
```

---

### Task 9: Macro economic calendar

**Files:**
- Create: `trade_digest/data/macro.py`
- Test: `tests/data/test_macro.py`

**Interfaces:**
- Consumes: `akshare.news_economic_baidu(date: str)`
- Produces: `fetch_macro_calendar(regions: list[str], today: date) -> list[dict]` with keys `region`/`event`/`actual`/`forecast`/`previous`/`importance`/`surprise_pct`; `condense_macro_updates(macro_updates: list[dict]) -> dict` with keys `highlights` (core Fed/macro-indicator events, shown individually) and `condensed_counts` (`dict[str, int]`, e.g. `{"油气数据": 4, "贵金属持仓": 12}`, for routine commodity-inventory noise merged into one-line summaries) — both consumed by `main.py` (Task 14).

**Design note (added after Task 15 manual verification):** a real run showed `fetch_macro_calendar` returning 20+ near-identical daily commodity inventory/positioning line items (NYMEX/COMEX/iShares/SPDR gold/silver/platinum holdings, weekly drilling-rig counts) that flooded the email and buried the handful of events that actually matter (Fed rate decisions, CPI, PMI, non-farm payrolls). `condense_macro_updates` is a pure, deterministic keyword classifier — not an LLM call — that separates "always show individually" events (matching a core-macro-indicator keyword list) from routine data (grouped by keyword into a count per category, defaulting to `"其他"` if no group matches). `main.py` passes only `highlights` onward to `build_payload`/`build_macro_priority_alerts`/`render_email`, and `condensed_counts` separately to `render_email` for a one-line summary.

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_macro.py
from datetime import date
from unittest.mock import patch

import pandas as pd

from trade_digest.data.macro import fetch_macro_calendar, condense_macro_updates


def _fake_calendar_df():
    return pd.DataFrame({
        "日期": ["2026-07-02"] * 4,
        "地区": ["中国", "美国", "俄罗斯", "中国"],
        "事件": ["中国CPI年率", "美国非农就业", "俄罗斯零售销售", "中国PMI"],
        "公布": [0.3, 250000, None, None],
        "预期": [0.1, 180000, 5.2, 50.1],
        "前值": [-0.1, 210000, 6.5, 49.8],
        "重要性": [3, 3, 1, 2],
    })


def test_fetch_macro_calendar_filters_regions_and_only_released():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=_fake_calendar_df()):
        result = fetch_macro_calendar(["中国", "美国"], date(2026, 7, 2))

    events = {r["event"] for r in result}
    assert events == {"中国CPI年率", "美国非农就业"}


def test_fetch_macro_calendar_computes_surprise_pct():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=_fake_calendar_df()):
        result = fetch_macro_calendar(["美国"], date(2026, 7, 2))

    nonfarm = result[0]
    assert nonfarm["actual"] == 250000
    assert nonfarm["forecast"] == 180000
    assert round(nonfarm["surprise_pct"], 2) == round(abs(250000 - 180000) / 180000 * 100, 2)


def test_fetch_macro_calendar_returns_empty_list_on_error():
    with patch("trade_digest.data.macro.ak.news_economic_baidu", side_effect=RuntimeError("boom")):
        assert fetch_macro_calendar(["中国"], date(2026, 7, 2)) == []


def test_fetch_macro_calendar_treats_nan_forecast_as_none():
    df = pd.DataFrame({
        "日期": ["2026-07-02"],
        "地区": ["中国"],
        "事件": ["中国某指标"],
        "公布": [1.5],
        "预期": [float("nan")],
        "前值": [1.2],
        "重要性": [2],
    })
    with patch("trade_digest.data.macro.ak.news_economic_baidu", return_value=df):
        result = fetch_macro_calendar(["中国"], date(2026, 7, 2))

    assert result[0]["forecast"] is None
    assert result[0]["surprise_pct"] is None


def test_condense_macro_updates_keeps_fed_focus_events_as_highlights():
    updates = [
        {"region": "美国", "event": "美联储利率决议", "actual": 4.5, "forecast": 4.5, "previous": 4.75, "importance": 2, "surprise_pct": 0.0},
        {"region": "中国", "event": "中国CPI年率", "actual": 0.3, "forecast": 0.1, "previous": -0.1, "importance": 2, "surprise_pct": 200.0},
    ]

    result = condense_macro_updates(updates)

    assert result["highlights"] == updates
    assert result["condensed_counts"] == {}


def test_condense_macro_updates_groups_oil_gas_and_precious_metals_by_keyword():
    updates = [
        {"region": "美国", "event": "美国截至7月3日当周石油钻井总数(口)", "actual": 445.0, "forecast": None, "previous": 440.0, "importance": 2, "surprise_pct": None},
        {"region": "美国", "event": "美国7月1日NYMEX铂金库存变动-每日(百盎司)", "actual": 0.0, "forecast": None, "previous": 0.0, "importance": 1, "surprise_pct": None},
        {"region": "美国", "event": "美国7月2日iShares黄金持仓变动-每日(吨)", "actual": -1.3, "forecast": None, "previous": -0.35, "importance": 1, "surprise_pct": None},
    ]

    result = condense_macro_updates(updates)

    assert result["highlights"] == []
    assert result["condensed_counts"] == {"油气数据": 1, "贵金属持仓": 2}


def test_condense_macro_updates_falls_back_to_other_category():
    updates = [{"region": "中国", "event": "中国某冷门统计指标", "actual": 1.0, "forecast": None, "previous": 0.9, "importance": 1, "surprise_pct": None}]

    result = condense_macro_updates(updates)

    assert result["highlights"] == []
    assert result["condensed_counts"] == {"其他": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_macro.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.macro'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/macro.py
import logging
from datetime import date

import akshare as ak

logger = logging.getLogger(__name__)


def _to_float(value) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if result != result:  # NaN check (NaN is the only float that isn't equal to itself)
            return None
        return result
    except (TypeError, ValueError):
        return None


def fetch_macro_calendar(regions: list[str], today: date) -> list[dict]:
    try:
        df = ak.news_economic_baidu(date=today.strftime("%Y%m%d"))
        df = df[df["地区"].isin(regions)]
        df = df[df["公布"].notna()]

        results = []
        for _, row in df.iterrows():
            actual = _to_float(row["公布"])
            forecast = _to_float(row["预期"])
            surprise_pct = None
            if actual is not None and forecast:
                surprise_pct = abs(actual - forecast) / abs(forecast) * 100
            results.append({
                "region": row["地区"],
                "event": row["事件"],
                "actual": actual,
                "forecast": forecast,
                "previous": _to_float(row["前值"]),
                "importance": row["重要性"],
                "surprise_pct": surprise_pct,
            })
        return results
    except Exception:
        logger.exception("Failed to fetch macro economic calendar")
        return []


_FOCUS_KEYWORDS = [
    "利率", "降息", "加息", "CPI", "PPI", "PMI", "非农", "失业率", "GDP",
    "零售销售", "贸易帐", "社融", "M2", "LPR", "议息", "联储", "美联储", "央行", "PCE",
]

_CONDENSE_GROUPS = {
    "油气数据": ["原油", "石油", "天然气", "钻井"],
    "贵金属持仓": ["黄金", "白银", "铂金", "钯金", "COMEX", "NYMEX", "iShares", "SPDR"],
}


def condense_macro_updates(macro_updates: list[dict]) -> dict:
    highlights = []
    condensed_counts: dict[str, int] = {}
    for update in macro_updates:
        event = update["event"]
        if any(keyword in event for keyword in _FOCUS_KEYWORDS):
            highlights.append(update)
            continue
        group = next(
            (name for name, keywords in _CONDENSE_GROUPS.items() if any(keyword in event for keyword in keywords)),
            "其他",
        )
        condensed_counts[group] = condensed_counts.get(group, 0) + 1
    return {"highlights": highlights, "condensed_counts": condensed_counts}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_macro.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/data/macro.py tests/data/test_macro.py
git commit -m "Add macro economic calendar fetch with surprise-percent calculation"
```

---

### Task 10: Financial news

**Files:**
- Create: `trade_digest/data/news.py`
- Test: `tests/data/test_news.py`

**Interfaces:**
- Consumes: `akshare.stock_news_main_cx()`
- Produces: `fetch_recent_news(limit: int) -> list[dict]` with keys `tag`/`summary`/`url` — consumed by `main.py` (Task 14).

- [ ] **Step 1: Write the failing tests**

```python
# tests/data/test_news.py
from unittest.mock import patch

import pandas as pd

from trade_digest.data.news import fetch_recent_news


def test_fetch_recent_news_limits_and_maps_fields():
    fake_df = pd.DataFrame({
        "tag": ["市场动态", "公司", "宏观"],
        "summary": ["消息一", "消息二", "消息三"],
        "url": ["https://a", "https://b", "https://c"],
    })
    with patch("trade_digest.data.news.ak.stock_news_main_cx", return_value=fake_df):
        result = fetch_recent_news(limit=2)

    assert result == [
        {"tag": "市场动态", "summary": "消息一", "url": "https://a"},
        {"tag": "公司", "summary": "消息二", "url": "https://b"},
    ]


def test_fetch_recent_news_returns_empty_list_on_error():
    with patch("trade_digest.data.news.ak.stock_news_main_cx", side_effect=RuntimeError("boom")):
        assert fetch_recent_news(limit=5) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/data/test_news.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.data.news'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/data/news.py
import logging

import akshare as ak

logger = logging.getLogger(__name__)


def fetch_recent_news(limit: int) -> list[dict]:
    try:
        df = ak.stock_news_main_cx()
        df = df.head(limit)
        return [{"tag": row["tag"], "summary": row["summary"], "url": row["url"]} for _, row in df.iterrows()]
    except Exception:
        logger.exception("Failed to fetch financial news")
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/data/test_news.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/data/news.py tests/data/test_news.py
git commit -m "Add Caixin financial news fetch"
```

---

### Task 11: LLM client abstraction

**Files:**
- Create: `trade_digest/analysis/llm_client.py`
- Test: `tests/analysis/test_llm_client.py`

**Interfaces:**
- Consumes: `requests.post`, environment variables `LLM_PROVIDER`/`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`
- Produces: `LLMClient` protocol with `.generate(system_prompt: str, payload: dict) -> dict`; `OpenAICompatibleClient`, `AnthropicClient`; `get_llm_client() -> LLMClient` — consumed by `analysis/synthesize.py` (Task 12).

**Note on scope:** both clients ask the model for JSON via prompt instructions and `json.loads` the response, rather than full JSON-schema tool-use forcing (the spec's aspirational description). A malformed response raises `json.JSONDecodeError`, which `synthesize_report` (Task 12) already catches as an LLM failure and degrades gracefully — so this simplification doesn't weaken the spec's error-handling guarantee, and schema-forcing can be added later without changing this interface.

- [ ] **Step 1: Write the failing tests**

```python
# tests/analysis/test_llm_client.py
import os
from unittest.mock import patch, MagicMock

import pytest

from trade_digest.analysis.llm_client import OpenAICompatibleClient, AnthropicClient, get_llm_client


def test_openai_compatible_client_parses_json_content():
    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": '{"market_summary": "ok"}'}}]}
    fake_response.raise_for_status.return_value = None
    client = OpenAICompatibleClient(base_url="https://api.example.com/v1", api_key="key", model="gpt-test")

    with patch("trade_digest.analysis.llm_client.requests.post", return_value=fake_response) as mock_post:
        result = client.generate("system prompt", {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.example.com/v1/chat/completions"


def test_anthropic_client_parses_json_content():
    fake_response = MagicMock()
    fake_response.json.return_value = {"content": [{"text": '{"market_summary": "ok"}'}]}
    fake_response.raise_for_status.return_value = None
    client = AnthropicClient(api_key="key", model="claude-test")

    with patch("trade_digest.analysis.llm_client.requests.post", return_value=fake_response) as mock_post:
        result = client.generate("system prompt", {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.anthropic.com/v1/messages"


def test_get_llm_client_returns_anthropic_when_configured():
    env = {"LLM_PROVIDER": "anthropic", "LLM_API_KEY": "key", "LLM_MODEL": "claude-test"}
    with patch.dict(os.environ, env, clear=True):
        client = get_llm_client()
    assert isinstance(client, AnthropicClient)


def test_get_llm_client_defaults_to_openai_compatible():
    env = {"LLM_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=True):
        client = get_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/analysis/test_llm_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.analysis.llm_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/analysis/llm_client.py
import json
import os
from typing import Protocol

import requests

_JSON_INSTRUCTION = "\n\nRespond with a single valid JSON object only, no other text, no markdown code fences."


class LLMClient(Protocol):
    def generate(self, system_prompt: str, payload: dict) -> dict: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, payload: dict) -> dict:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt + _JSON_INSTRUCTION},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)


class AnthropicClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, payload: dict) -> dict:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 2048,
                "system": system_prompt + _JSON_INSTRUCTION,
                "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        return json.loads(content)


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "openai")
    api_key = os.environ["LLM_API_KEY"]
    model = os.environ.get("LLM_MODEL") or ("claude-sonnet-5" if provider == "anthropic" else "gpt-4o-mini")
    if provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model)
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    return OpenAICompatibleClient(base_url=base_url, api_key=api_key, model=model)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/analysis/test_llm_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/analysis/llm_client.py tests/analysis/test_llm_client.py
git commit -m "Add OpenAI-compatible and Anthropic LLM client abstraction"
```

---

### Task 12: LLM synthesis (structured payload + system prompt)

**Files:**
- Create: `trade_digest/analysis/synthesize.py`
- Test: `tests/analysis/test_synthesize.py`

**Interfaces:**
- Consumes: `LLMClient.generate(system_prompt, payload) -> dict` (Task 11)
- Produces: `build_payload(market_overview, sector_flow, watchlist_quotes, macro_updates, news_items, tactical_positions, dca_strategy_due) -> dict`, `synthesize_report(llm_client, payload) -> dict | None` (returns `None` on any LLM failure), `build_macro_priority_alerts(macro_updates: list[dict], surprise_threshold_pct: float) -> list[dict]` — consumed by `main.py` (Task 14).

**Design note — why macro surprise tiering is code, not LLM:** spec §8 requires "大幅超预期的宏观数据" (tier 2) to be judged by a numeric rule (今值 vs 预期), not by the LLM reading text. `build_macro_priority_alerts` applies `surprise_threshold_pct` from `settings.yaml` directly to `macro_updates[i]["surprise_pct"]` (computed in Task 9) and produces ready-made tier-2 alert entries deterministically. The LLM's `priority_alerts` output (via `SYSTEM_PROMPT`) is scoped to *non-macro* events only (news-driven black-swan/tier-1, digestible-impact/tier-2, earnings-orders/tier-3, routine/tier-4) since it has no reliable "expected value" to compare against for those. `main.py` (Task 14) merges both lists before rendering.

- [ ] **Step 1: Write the failing tests**

```python
# tests/analysis/test_synthesize.py
from unittest.mock import MagicMock

from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts


def test_build_payload_assembles_all_sections():
    payload = build_payload(
        market_overview={"indices": []},
        sector_flow={"top_inflow": []},
        watchlist_quotes=[{"code": "513100", "name": "纳指ETF", "price": 1.5, "change_pct": 0.4}],
        macro_updates=[{"event": "CPI"}],
        news_items=[{"summary": "news"}],
        tactical_positions=[{"name": "黄金"}],
        dca_strategy_due=True,
    )
    assert payload == {
        "market_overview": {"indices": []},
        "sector_flow": {"top_inflow": []},
        "watchlist_quotes": [{"code": "513100", "name": "纳指ETF", "price": 1.5, "change_pct": 0.4}],
        "macro_updates": [{"event": "CPI"}],
        "news_items": [{"summary": "news"}],
        "watchlist_tactical": [{"name": "黄金"}],
        "dca_strategy_due": True,
    }


def test_synthesize_report_returns_llm_result():
    llm_client = MagicMock()
    llm_client.generate.return_value = {"market_summary": "ok"}

    result = synthesize_report(llm_client, {"foo": "bar"})

    assert result == {"market_summary": "ok"}
    llm_client.generate.assert_called_once()


def test_synthesize_report_returns_none_on_failure():
    llm_client = MagicMock()
    llm_client.generate.side_effect = RuntimeError("LLM down")

    assert synthesize_report(llm_client, {"foo": "bar"}) is None


def test_build_macro_priority_alerts_flags_surprises_above_threshold():
    macro_updates = [
        {"region": "美国", "event": "非农就业", "actual": 250000, "forecast": 180000, "previous": 210000, "importance": 3, "surprise_pct": 38.9},
        {"region": "中国", "event": "PMI", "actual": 50.1, "forecast": 50.0, "previous": 49.8, "importance": 2, "surprise_pct": 0.2},
    ]
    result = build_macro_priority_alerts(macro_updates, surprise_threshold_pct=10)

    assert len(result) == 1
    assert result[0]["tier"] == 2
    assert result[0]["category"] == "宏观超预期"
    assert "非农就业" in result[0]["summary"]


def test_build_macro_priority_alerts_skips_entries_without_surprise_pct():
    macro_updates = [{"region": "中国", "event": "社融", "actual": 1.0, "forecast": None, "previous": 0.9, "importance": 1, "surprise_pct": None}]

    assert build_macro_priority_alerts(macro_updates, surprise_threshold_pct=10) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/analysis/test_synthesize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.analysis.synthesize'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/analysis/synthesize.py
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名严谨、克制的证券分析助手，为个人投资者生成A股盘中/盘后简报。
只做参考性判断，不给绝对化买卖建议，对不确定的信息明确标注不确定性。

你会收到一个结构化JSON，包含：market_overview（大盘概览）、sector_flow（板块资金流）、
watchlist_quotes（你关注的ETF清单当前行情，可结合sector_flow一起解读）、
macro_updates（今日新发布的宏观数据，可能为空数组）、news_items（近期财经新闻原文标题/摘要）、
watchlist_tactical（需要打分的短线仓位和黄金持仓，每项含price/cost_price等字段）、
dca_strategy_due（是否需要生成定投策略参考）。

请返回一个JSON对象，包含以下字段：
- market_summary: 字符串，大盘概览解读
- sector_highlights: 字符串，板块资金流解读
- macro_commentary: 字符串或null，若macro_updates为空则为null
- tactical_scores: 数组，watchlist_tactical中每个标的对应一项 {"name":..., "score": "看多"|"中性"|"看空", "reason": "一句话理由"}
- priority_alerts: 数组，从news_items中筛选出的重要事件（不包括宏观数据，宏观数据的分级由其他规则单独处理），每项 {"tier": 1|2|3|4, "category": "黑天鹅"|"重大利空利好"|"财报订单"|"常规", "summary": "一句话", "reason": "一句话"}。
  第一档(黑天鹅/重大科技突破/泡沫破裂)应极少出现，多数情况下不应有第一档条目；第四档(对市场冲击不大或用户不关注板块)默认不需要在邮件中展开，仅统计数量。
- dca_strategy: 若dca_strategy_due为true，返回数组 {"name":..., "suggestion": "继续定投"|"可考虑加大"|"可考虑阶段性减少", "reason": "一句话理由"}；否则为null

只返回这个JSON对象，不要包含其他文字。"""


def build_payload(
    market_overview: dict,
    sector_flow: dict | None,
    watchlist_quotes: list[dict],
    macro_updates: list[dict],
    news_items: list[dict],
    tactical_positions: list[dict],
    dca_strategy_due: bool,
) -> dict:
    return {
        "market_overview": market_overview,
        "sector_flow": sector_flow,
        "watchlist_quotes": watchlist_quotes,
        "macro_updates": macro_updates,
        "news_items": news_items,
        "watchlist_tactical": tactical_positions,
        "dca_strategy_due": dca_strategy_due,
    }


def synthesize_report(llm_client, payload: dict) -> dict | None:
    try:
        return llm_client.generate(SYSTEM_PROMPT, payload)
    except Exception:
        logger.exception("LLM synthesis failed")
        return None


def build_macro_priority_alerts(macro_updates: list[dict], surprise_threshold_pct: float) -> list[dict]:
    """Tier-2 alerts for macro releases that deviate from forecast beyond the threshold.

    This is a deterministic rule (spec §8), not an LLM judgment call — it runs
    independently of synthesize_report and its output is merged with the LLM's
    (non-macro) priority_alerts by main.py.
    """
    alerts = []
    for update in macro_updates:
        surprise_pct = update.get("surprise_pct")
        if surprise_pct is None or surprise_pct < surprise_threshold_pct:
            continue
        alerts.append({
            "tier": 2,
            "category": "宏观超预期",
            "summary": f"[{update['region']}] {update['event']}: 公布{update['actual']} vs 预期{update['forecast']}",
            "reason": f"偏离预期 {surprise_pct:.1f}%",
        })
    return alerts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/analysis/test_synthesize.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/analysis/synthesize.py tests/analysis/test_synthesize.py
git commit -m "Add structured LLM payload builder and synthesis call with failure handling"
```

---

### Task 13: Email rendering and sending

**Files:**
- Create: `trade_digest/notify/emailer.py`
- Test: `tests/notify/test_emailer.py`

**Interfaces:**
- Consumes: output shapes from Tasks 5/6/8/9/10/12 (all plain dicts/lists)
- Produces: `render_email(session, report_date, market_overview, sector_flow, watchlist_quotes, macro_updates, macro_condensed_counts, triggered_alerts, tactical_positions, news_items, priority_alerts, llm_result) -> str` (HTML), `send_email(smtp_host, smtp_port, smtp_user, smtp_password, sender, recipients, subject, html_body) -> None` — both consumed by `main.py` (Task 14). `priority_alerts` is the pre-merged list (macro-driven tier-2 alerts from `build_macro_priority_alerts` + the LLM's news-driven `priority_alerts`) — `render_email` itself does no merging, just rendering. `watchlist_quotes` is the flat list from `fetch_etf_quotes` (Task 6), converted to `[{"code":..., "name":..., "price":..., "change_pct":...}, ...]` by `main.py`. `macro_updates` here is the `highlights` list and `macro_condensed_counts` is the `condensed_counts` dict, both from Task 9's `condense_macro_updates` (added after Task 15 manual verification surfaced macro-noise flooding).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/notify/test_emailer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.notify.emailer'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/notify/emailer.py
import smtplib
from email.mime.text import MIMEText

SESSION_LABELS = {"morning": "早盘", "evening": "晚间"}


def _fmt_nullable(value) -> str:
    return "无数据" if value is None else str(value)


def _render_indices(indices: list[dict] | None) -> str:
    if not indices:
        return "<p>（大盘指数数据缺失）</p>"
    rows = "".join(f"<li>{i['name']}: {i['price']} ({i['change_pct']:+.2f}%)</li>" for i in indices)
    return f"<ul>{rows}</ul>"


def _render_sector_flow(sector_flow: dict | None) -> str:
    if not sector_flow:
        return "<p>（板块资金流数据缺失）</p>"
    inflow = "".join(f"<li>{s['name']}: 净流入 {s['net_inflow']:.0f}</li>" for s in sector_flow.get("top_inflow", []))
    outflow = "".join(f"<li>{s['name']}: 净流出 {s['net_inflow']:.0f}</li>" for s in sector_flow.get("top_outflow", []))
    return f"<p>流入靠前：</p><ul>{inflow}</ul><p>流出靠前：</p><ul>{outflow}</ul>"


def _render_watchlist(watchlist_quotes: list[dict]) -> str:
    if not watchlist_quotes:
        return ""
    items = "".join(f"<li>{q['name']}: {q['price']} ({q['change_pct']:+.2f}%)</li>" for q in watchlist_quotes)
    return f"<h3>关注ETF行情</h3><ul>{items}</ul>"


def _render_alerts(triggered_alerts: list[dict]) -> str:
    if not triggered_alerts:
        return ""
    items = "".join(f"<li>{a['name']}: {a['action']}</li>" for a in triggered_alerts)
    return f"<h3>持仓提醒</h3><ul>{items}</ul>"


def _render_tactical_scores(llm_result: dict | None) -> str:
    scores = (llm_result or {}).get("tactical_scores") or []
    if not scores:
        return ""
    items = "".join(f"<li>{s['name']}: {s['score']} — {s['reason']}</li>" for s in scores)
    return f"<h3>短线/黄金打分</h3><ul>{items}</ul>"


def _render_tactical_positions(tactical_positions: list[dict]) -> str:
    if not tactical_positions:
        return ""
    items = "".join(
        f"<li>{p['name']}: {p['price'] if p['price'] is not None else '无实时报价'}"
        + (f"（成本 {p['cost_price']}）" if p.get("cost_price") is not None else "")
        + "</li>"
        for p in tactical_positions
    )
    return f"<h3>短线/黄金持仓现价</h3><ul>{items}</ul>"


def _render_news(news_items: list[dict]) -> str:
    if not news_items:
        return ""
    items = "".join(f"<li>[{n['tag']}] {n['summary']}</li>" for n in news_items[:5])
    return f"<h3>相关新闻</h3><ul>{items}</ul>"


def _render_priority_alerts(priority_alerts: list[dict], tier3_max_items: int = 5) -> str:
    if not priority_alerts:
        return ""
    tier12 = [a for a in priority_alerts if a["tier"] in (1, 2)]
    tier3 = [a for a in priority_alerts if a["tier"] == 3][:tier3_max_items]
    tier4_count = sum(1 for a in priority_alerts if a["tier"] == 4)

    parts = []
    if tier12:
        items = "".join(f"<li><strong>[第{a['tier']}档 {a['category']}]</strong> {a['summary']} — {a['reason']}</li>" for a in tier12)
        parts.append(f"<h2 style='color:#b00'>重要提醒</h2><ul>{items}</ul>")
    if tier3:
        items = "".join(f"<li>[{a['category']}] {a['summary']}</li>" for a in tier3)
        parts.append(f"<h3>其他关注</h3><ul>{items}</ul>")
    if tier4_count:
        parts.append(f"<p>另有{tier4_count}条常规消息，影响较小，未展开。</p>")
    return "".join(parts)


def render_email(
    session: str,
    report_date: str,
    market_overview: dict,
    sector_flow: dict | None,
    watchlist_quotes: list[dict],
    macro_updates: list[dict],
    macro_condensed_counts: dict[str, int],
    triggered_alerts: list[dict],
    tactical_positions: list[dict],
    news_items: list[dict],
    priority_alerts: list[dict],
    llm_result: dict | None,
) -> str:
    session_label = SESSION_LABELS.get(session, session)
    parts = [f"<h1>{report_date} {session_label}简报</h1>"]

    if llm_result is None:
        parts.append("<p><strong>AI解读生成失败，仅展示原始数据</strong></p>")

    parts.append(_render_priority_alerts(priority_alerts))

    parts.append("<h2>大盘概览</h2>")
    parts.append(_render_indices(market_overview.get("indices")))
    if llm_result and llm_result.get("market_summary"):
        parts.append(f"<p>{llm_result['market_summary']}</p>")

    parts.append("<h2>板块资金流</h2>")
    parts.append(_render_sector_flow(sector_flow))
    parts.append(_render_watchlist(watchlist_quotes))
    if llm_result and llm_result.get("sector_highlights"):
        parts.append(f"<p>{llm_result['sector_highlights']}</p>")

    if macro_updates or macro_condensed_counts:
        parts.append("<h2>宏观数据</h2>")
        if macro_updates:
            items = "".join(
                f"<li>[{m['region']}] {m['event']}: 公布{_fmt_nullable(m['actual'])} "
                f"预期{_fmt_nullable(m['forecast'])} 前值{_fmt_nullable(m['previous'])}</li>"
                for m in macro_updates
            )
            parts.append(f"<ul>{items}</ul>")
        if macro_condensed_counts:
            summary = "；".join(f"{name}{count}项更新" for name, count in macro_condensed_counts.items())
            parts.append(f"<p>另有：{summary}（常规数据更新，未展开）</p>")
        if llm_result and llm_result.get("macro_commentary"):
            parts.append(f"<p>{llm_result['macro_commentary']}</p>")

    parts.append(_render_alerts(triggered_alerts))
    parts.append(_render_tactical_positions(tactical_positions))
    parts.append(_render_tactical_scores(llm_result))

    dca_strategy = (llm_result or {}).get("dca_strategy")
    if dca_strategy:
        items = "".join(f"<li>{s['name']}: {s['suggestion']} — {s['reason']}</li>" for s in dca_strategy)
        parts.append(f"<h3>定投策略参考</h3><ul>{items}</ul>")

    parts.append(_render_news(news_items))
    parts.append("<hr><p><em>仅供参考，不构成投资建议</em></p>")

    return "\n".join(p for p in parts if p)


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: str,
    recipients: list[str],
    subject: str,
    html_body: str,
) -> None:
    message = MIMEText(html_body, "html", "utf-8")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(sender, recipients, message.as_string())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/notify/test_emailer.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add trade_digest/notify/emailer.py tests/notify/test_emailer.py
git commit -m "Add HTML email rendering and SMTP sending"
```

---

### Task 14: Main orchestration entry point

**Files:**
- Create: `trade_digest/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: every function produced in Tasks 2–13
- Produces: `run(session: str, today: date) -> None` (the testable orchestration function) and a `if __name__ == "__main__":` CLI wrapper using `argparse` with `--session {morning,evening}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
from datetime import date
from unittest.mock import patch, MagicMock

from trade_digest.main import run


def _patch_all(mock_is_trading_day=True):
    patches = {
        "trade_digest.main.is_trading_day": patch("trade_digest.main.is_trading_day", return_value=mock_is_trading_day),
        "trade_digest.main.load_settings": patch("trade_digest.main.load_settings", return_value={
            "sector_flow": {"top_n": 5, "watchlist_etfs": [{"name": "纳指", "code": "513100"}]},
            "macro": {"regions": ["中国", "美国"], "surprise_threshold_pct": 10},
            "dca_strategy": {"refresh_days": 7},
            "news": {"fetch_limit": 20, "tier3_max_items": 5},
            "email": {"recipients": ["me@example.com"]},
        }),
        "trade_digest.main.load_holdings": patch("trade_digest.main.load_holdings", return_value={
            "categories": {
                "gold": {"total_weight": 0.2, "positions": [{"name": "黄金", "code": "518880", "cost_price": 4350, "alerts": []}]},
                "securities_trading": {"total_weight": 0.13, "positions": [{"name": "券商", "code": "512880"}]},
                "fund": {"total_weight": 0.4, "positions": [{"name": "纳指", "code": "513100"}]},
            }
        }),
        "trade_digest.main.fetch_market_overview": patch("trade_digest.main.fetch_market_overview", return_value={"indices": [], "breadth": None, "margin": None, "us_market": None, "asia_market": None}),
        "trade_digest.main.fetch_sector_flow_ranking": patch("trade_digest.main.fetch_sector_flow_ranking", return_value={"top_inflow": [], "top_outflow": []}),
        "trade_digest.main.fetch_etf_quotes": patch("trade_digest.main.fetch_etf_quotes", return_value={}),
        "trade_digest.main.enrich_holdings_with_quotes": patch("trade_digest.main.enrich_holdings_with_quotes", return_value=[
            {"name": "黄金", "category": "gold", "code": "518880", "price": 4360, "cost_price": 4350, "alerts": []},
            {"name": "券商", "category": "securities_trading", "code": "512880", "price": 1.2},
            {"name": "纳指", "category": "fund", "code": "513100", "price": 1.5},
        ]),
        "trade_digest.main.fetch_macro_calendar": patch("trade_digest.main.fetch_macro_calendar", return_value=[]),
        "trade_digest.main.condense_macro_updates": patch("trade_digest.main.condense_macro_updates", return_value={"highlights": [], "condensed_counts": {}}),
        "trade_digest.main.fetch_recent_news": patch("trade_digest.main.fetch_recent_news", return_value=[]),
        "trade_digest.main.is_dca_strategy_due": patch("trade_digest.main.is_dca_strategy_due", return_value=False),
        "trade_digest.main.save_dca_strategy_run_date": patch("trade_digest.main.save_dca_strategy_run_date"),
        "trade_digest.main.get_llm_client": patch("trade_digest.main.get_llm_client", return_value=MagicMock()),
        "trade_digest.main.synthesize_report": patch("trade_digest.main.synthesize_report", return_value={"market_summary": "ok", "tactical_scores": [], "priority_alerts": [], "dca_strategy": None, "macro_commentary": None, "sector_highlights": "ok"}),
        "trade_digest.main.render_email": patch("trade_digest.main.render_email", return_value="<html></html>"),
        "trade_digest.main.send_email": patch("trade_digest.main.send_email"),
    }
    started = {name: p.start() for name, p in patches.items()}
    return patches, started


def test_run_skips_everything_on_non_trading_day():
    patches, started = _patch_all(mock_is_trading_day=False)
    try:
        run("morning", date(2026, 7, 4))
        started["trade_digest.main.load_settings"].assert_not_called()
        started["trade_digest.main.send_email"].assert_not_called()
    finally:
        for p in patches.values():
            p.stop()


def test_run_sends_email_on_trading_day():
    patches, started = _patch_all(mock_is_trading_day=True)
    try:
        run("morning", date(2026, 7, 2))
        started["trade_digest.main.send_email"].assert_called_once()
        started["trade_digest.main.render_email"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()


def test_run_only_scores_gold_and_securities_trading():
    patches, started = _patch_all(mock_is_trading_day=True)
    try:
        run("morning", date(2026, 7, 2))
        synthesize_call = started["trade_digest.main.synthesize_report"]
        payload_arg = synthesize_call.call_args.args[1]
        tactical_names = {p["name"] for p in payload_arg["watchlist_tactical"]}
        assert tactical_names == {"黄金", "券商"}
    finally:
        for p in patches.values():
            p.stop()


def test_run_saves_dca_state_when_due_and_llm_returned_strategy():
    patches, started = _patch_all(mock_is_trading_day=True)
    started["trade_digest.main.is_dca_strategy_due"].return_value = True
    started["trade_digest.main.synthesize_report"].return_value = {
        "market_summary": "ok", "tactical_scores": [], "priority_alerts": [],
        "dca_strategy": [{"name": "纳指", "suggestion": "继续定投", "reason": "ok"}],
        "macro_commentary": None, "sector_highlights": "ok",
    }
    try:
        run("evening", date(2026, 7, 2))
        started["trade_digest.main.save_dca_strategy_run_date"].assert_called_once()
    finally:
        for p in patches.values():
            p.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trade_digest.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# trade_digest/main.py
import argparse
import logging
import os
from datetime import date
from pathlib import Path

from trade_digest.config.loader import load_settings, load_holdings
from trade_digest.data.calendar import is_trading_day
from trade_digest.data.market_overview import fetch_market_overview
from trade_digest.data.sector_flow import fetch_sector_flow_ranking, fetch_etf_quotes
from trade_digest.data.holdings_quotes import enrich_holdings_with_quotes
from trade_digest.data.macro import fetch_macro_calendar, condense_macro_updates
from trade_digest.data.news import fetch_recent_news
from trade_digest.state import is_dca_strategy_due, save_dca_strategy_run_date
from trade_digest.analysis.holdings_alert import evaluate_alerts
from trade_digest.analysis.llm_client import get_llm_client
from trade_digest.analysis.synthesize import build_payload, synthesize_report, build_macro_priority_alerts
from trade_digest.notify.emailer import render_email, send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent / "config"
STATE_FILE = Path(__file__).parent.parent / "state" / "dca_strategy_last_run.json"

TACTICAL_CATEGORIES = {"gold", "securities_trading"}


def run(session: str, today: date) -> None:
    if not is_trading_day(today):
        logger.info("Not an A-share trading day, skipping session=%s", session)
        return

    settings = load_settings(CONFIG_DIR / "settings.yaml")
    holdings = load_holdings(CONFIG_DIR / "holdings.yaml")

    market_overview = fetch_market_overview(session)
    sector_flow = fetch_sector_flow_ranking(settings["sector_flow"]["top_n"])

    watchlist_codes = [etf["code"] for etf in settings["sector_flow"]["watchlist_etfs"]]
    watchlist_quotes_by_code = fetch_etf_quotes(watchlist_codes)
    watchlist_quotes = [{"code": code, **quote} for code, quote in watchlist_quotes_by_code.items()]

    holdings_flat = enrich_holdings_with_quotes(holdings)
    triggered_alerts = []
    for position in holdings_flat:
        triggered_alerts.extend(evaluate_alerts(position))

    tactical_positions = [p for p in holdings_flat if p["category"] in TACTICAL_CATEGORIES]

    macro_updates_raw = fetch_macro_calendar(settings["macro"]["regions"], today)
    macro_condensed = condense_macro_updates(macro_updates_raw)
    macro_highlights = macro_condensed["highlights"]
    macro_condensed_counts = macro_condensed["condensed_counts"]

    news_items = fetch_recent_news(settings["news"]["fetch_limit"])

    dca_due = is_dca_strategy_due(settings["dca_strategy"]["refresh_days"], today, STATE_FILE)

    payload = build_payload(market_overview, sector_flow, watchlist_quotes, macro_highlights, news_items, tactical_positions, dca_due)
    llm_client = get_llm_client()
    llm_result = synthesize_report(llm_client, payload)

    if dca_due and llm_result and llm_result.get("dca_strategy"):
        save_dca_strategy_run_date(today, STATE_FILE)

    macro_priority_alerts = build_macro_priority_alerts(macro_highlights, settings["macro"]["surprise_threshold_pct"])
    news_priority_alerts = (llm_result or {}).get("priority_alerts") or []
    priority_alerts = macro_priority_alerts + news_priority_alerts

    html = render_email(
        session=session,
        report_date=today.isoformat(),
        market_overview=market_overview,
        sector_flow=sector_flow,
        watchlist_quotes=watchlist_quotes,
        macro_updates=macro_highlights,
        macro_condensed_counts=macro_condensed_counts,
        triggered_alerts=triggered_alerts,
        tactical_positions=tactical_positions,
        news_items=news_items,
        priority_alerts=priority_alerts,
        llm_result=llm_result,
    )

    send_email(
        smtp_host=os.environ["SMTP_HOST"],
        smtp_port=int(os.environ.get("SMTP_PORT", "465")),
        smtp_user=os.environ["SMTP_USER"],
        smtp_password=os.environ["SMTP_PASSWORD"],
        sender=os.environ.get("SMTP_SENDER", os.environ["SMTP_USER"]),
        recipients=settings["email"]["recipients"],
        subject=f"{today.isoformat()} {session} 交易简报",
        html_body=html,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", choices=["morning", "evening"], required=True)
    args = parser.parse_args()
    run(args.session, date.today())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_main.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: PASS (all tests across all tasks, no network calls made)

- [ ] **Step 6: Commit**

```bash
git add trade_digest/main.py tests/test_main.py
git commit -m "Wire orchestration entry point with --session morning|evening"
```

---

### Task 15: Local config setup and manual end-to-end verification

**Files:**
- Create: `trade_digest/config/settings.yaml` (copy of `.example.yaml`, gitignored)
- Create: `trade_digest/config/holdings.yaml` (copy of `.example.yaml`, gitignored)

This task has no automated test — it validates the whole pipeline against real network calls, a real SMTP account, and a real LLM key, per spec section 13's manual verification step.

- [ ] **Step 1: Create the real (gitignored) config files from the examples**

```bash
cp trade_digest/config/settings.example.yaml trade_digest/config/settings.yaml
cp trade_digest/config/holdings.example.yaml trade_digest/config/holdings.yaml
```

Edit `trade_digest/config/settings.yaml`'s `email.recipients` to your real email address, and `trade_digest/config/holdings.yaml` to match your actual current positions (fill in the real fund code for 科技板块基金 if it has one, or leave `null`).

- [ ] **Step 2: Set required environment variables for one real run**

```bash
export LLM_PROVIDER=openai   # or anthropic
export LLM_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini # or claude-sonnet-5 for anthropic
export SMTP_HOST=smtp.example.com
export SMTP_PORT=465
export SMTP_USER=you@example.com
export SMTP_PASSWORD=your-smtp-app-password
export SMTP_SENDER=you@example.com
```

- [ ] **Step 3: Run a real morning session**

```bash
uv run python -m trade_digest.main --session morning
```

Expected: no exceptions; check your inbox for the rendered email. If `main.py` isn't runnable as `-m trade_digest.main` (module execution requires the repo root on `PYTHONPATH`), run it as:

```bash
uv run python trade_digest/main.py --session morning
```

- [ ] **Step 4: Inspect the received email**

Confirm: 大盘概览/板块资金流/持仓提醒/AI解读 sections render with real data (or documented degraded fallbacks if a specific source failed), no raw Python objects or `None` leaking into the visible text, and the "仅供参考，不构成投资建议" disclaimer is present.

- [ ] **Step 5: Fix any live-data surprises found during this run**

Common candidates based on exploratory testing: `fetch_asia_snapshot`'s symbol (see Task 5 Step 5), exact column names if akshare has changed since spec-writing, or SMTP provider-specific auth requirements (e.g. app-specific passwords for Gmail/QQ邮箱). Adjust the relevant `data/*.py` file, re-run the affected unit test file to confirm mocks still pass, then re-run Step 3.

- [ ] **Step 6: Commit only the example-file changes, if any were needed**

The real `settings.yaml`/`holdings.yaml` stay gitignored (personal data). If Step 5 required code fixes, commit those:

```bash
git add trade_digest/
git commit -m "Fix live-data issues found during manual end-to-end verification"
```

---

## Self-Review Notes

- **Spec coverage**: 目标/推送时段(§1-2) → Task 14/15; 架构(§3) → File Structure + Tasks 2-14; 数据流(§4) → Task 14; 数据源(§5) → Tasks 4-10; 持仓配置(§6) → Task 1 configs + Task 7-8; 打分分层(§7) → Task 14's `TACTICAL_CATEGORIES` filter + `dca_strategy_due`; 优先级分级(§8) → macro surprises via Task 12's `build_macro_priority_alerts` (code-rule, matches spec's "宏观数据用...数值化规则判断") merged in Task 14 with the LLM's news-driven `priority_alerts` (Task 12's `SYSTEM_PROMPT`), rendered by Task 13's `_render_priority_alerts`; LLM设计(§9) → Tasks 11-12; 邮件渲染(§10) → Task 13; 调度(§11) → Task 14's `run(session, today)` split from the CLI wrapper; 错误处理(§12) → every fetch function's try/except-return-None pattern (Tasks 4-10) plus Task 12's `synthesize_report` catch; 测试计划(§13) → Tasks 1-14's mocked unit tests + Task 15's manual run.
- **Placeholder scan**: no TBD/TODO left; the one open item (`fetch_asia_snapshot`'s exact sina symbol) is called out explicitly as a documented follow-up with a concrete verification command, not a vague "handle it later".
- **Type consistency checked**: `fetch_etf_quotes(codes: list[str]) -> dict` (Task 6) is called identically from `holdings_quotes.py` (Task 7) and `main.py` (Task 14); `evaluate_alerts(position: dict) -> list[dict]` (Task 8) consumes exactly the shape `enrich_holdings_with_quotes` (Task 7) produces; `synthesize_report(llm_client, payload) -> dict | None` (Task 12) return type matches what `render_email`'s `llm_result: dict | None` parameter (Task 13) expects; `build_macro_priority_alerts(macro_updates, surprise_threshold_pct) -> list[dict]` (Task 12) and the LLM's `priority_alerts` are concatenated in `main.py` (Task 14) into one list matching `render_email`'s `priority_alerts: list[dict]` parameter (Task 13), which reads `a["tier"]`/`a["category"]`/`a["summary"]`/`a["reason"]` from every entry regardless of source — both producers use exactly those four keys; `run(session: str, today: date)` (Task 14) is the single seam every test patches against.
- **Self-review fix applied**: the initial draft delegated *all* priority-tier classification (including macro surprises) to the LLM, which contradicted the approved spec §8 requirement that macro-surprise tier-2 classification be a deterministic code rule. Fixed by adding `build_macro_priority_alerts` (Task 12) as a pure function independent of the LLM call, and narrowing the `SYSTEM_PROMPT`'s `priority_alerts` scope to news-driven (non-macro) events only.
- **Self-review fix applied**: `macro.py`'s `_to_float` treated NaN forecast/previous values as valid floats (since `float(nan)` doesn't raise), which would have let `surprise_pct` silently become `nan` instead of `None` when akshare omits a forecast. Fixed with an explicit NaN check and covered by `test_fetch_macro_calendar_treats_nan_forecast_as_none` (Task 9).
- **Self-review fix applied (pre-flight scan)**: the initial draft had `main.py` call `fetch_etf_quotes(watchlist_codes)` and discard the result ("warms up watchlist quotes for future dashboard use") — spec §5/§10 require 关注ETF清单 quotes to actually appear in the report, and a discarded return value with no consumer is dead code a task reviewer would flag as YAGNI-violating speculative code. Fixed by threading `watchlist_quotes` through `build_payload` (Task 12) and `render_email`'s new `_render_watchlist` section (Task 13), consumed by `main.py` (Task 14).
- **Fix applied during execution (Task 5 review finding)**: every data-fetch function's `try` block wrapped only the raw akshare call, not the subsequent DataFrame parsing — a malformed/unexpected response shape (missing column, empty frame) would raise uncaught, contradicting the Global Constraint that callers never need to wrap fetch calls in `try/except`. This was a plan-mandated defect (the example code itself had this shape) present in Tasks 5, 6, 9, and 10. Fixed in the plan text for all four tasks — the `try` block now wraps the entire function body — and the human confirmed fixing immediately rather than deferring past MVP.
- **Fix applied during execution (Task 6 review finding)**: `fetch_sector_flow_ranking`'s `df.head(top_n)`/`df.tail(top_n)` could overlap when `top_n * 2 > len(df)`, letting one sector appear in both `top_inflow` and `top_outflow` — a plan-mandated defect (present in the example code) confirmed to actually manifest with the task's own 3-row test fixture and `top_n=2`. Fixed in the plan text by excluding the `top` rows before taking `tail(top_n)` for `bottom`, and added a test (`test_fetch_sector_flow_ranking_top_and_bottom_never_overlap`) asserting the two result sets are disjoint. The human confirmed fixing immediately.
- **Fix applied during execution (Task 13 review finding)**: `render_email`'s `tactical_positions` parameter (raw price/cost_price for gold and short-term securities holdings) was accepted but never rendered — only the LLM's `tactical_scores` interpretation showed up, meaning the raw position data disappeared from the email entirely whenever the LLM call failed (`llm_result=None`), leaving only alert-trigger lines (a different, narrower signal). Fixed by adding `_render_tactical_positions` (renders name/price/cost_price for each tactical position, independent of `llm_result`) and calling it in `render_email` alongside `_render_tactical_scores`. Also strengthened `test_render_email_shows_fallback_banner_when_llm_result_is_none` to pass a non-empty `tactical_positions` list and assert it renders — this simultaneously closes the reviewer's noted test-coverage gap ("llm=None with non-empty raw data" was previously untested).
- **Fix applied during execution (Task 15 manual verification finding)**: a real end-to-end run surfaced two Python `None` values leaking into the visible email text — `现金/子弹: None` (a holdings position with no live price, since it has no exchange code) and `预期None` repeated across many macro releases (obscure indicators like drilling-rig counts genuinely have no consensus forecast in the data source). Neither was caught by unit tests because no test exercised a `None` price or `None` forecast through the actual rendering path. Fixed by adding `_fmt_nullable(value)` (renders `None` as `"无数据"`) used for the macro line's `actual`/`forecast`/`previous` fields, and by having `_render_tactical_positions` render `"无实时报价"` instead of the raw price when `price is None`. Added `test_render_email_never_leaks_none_for_missing_price_or_forecast` asserting the literal string `"None"` never appears in rendered output. This is exactly the class of bug spec §13's manual-verification step exists to catch.
- **Fix applied during execution (Task 15 manual verification finding — gold price unit mismatch)**: the real run showed 黄金's rendered "price" as `8.672` (the domestic 黄金ETF's per-share CNY price from `fetch_etf_quotes`), while `holdings.yaml`'s `cost_price: 4350`/alert threshold `4380` are denominated in USD/oz (international spot gold) per the human's clarification — these numbers were never comparable, silently defeating the entire gold alert feature (the `"price >= 4380"` condition could never realistically trigger). Fixed by adding `fetch_gold_spot_price()` (Task 5, using the verified non-eastmoney interface `ak.futures_foreign_commodity_realtime(symbol="XAU")`, returning 伦敦金/London gold in USD/oz) and special-casing `enrich_holdings_with_quotes` (Task 7) so any position in the `gold` category sources its `price` from the spot feed instead of an ETF-code lookup. The 关注ETF清单/watchlist section (a distinct feature, for glancing at ETF market data) is unaffected and still shows the gold ETF's own share price, which is the correct behavior for that section.
- **Fix applied during execution (Task 15 manual verification finding — macro noise flooding)**: the real run's 宏观数据 section listed 25 near-identical daily commodity inventory/positioning line items (NYMEX/COMEX/iShares/SPDR gold/silver/platinum holdings, weekly drilling-rig counts), burying the few events that actually matter and violating the spec's "精简" (concise) design goal. Per the human's guidance ("merge same-category data; the focus should be Fed-published data, except oil/gas and gold holdings data"), added `condense_macro_updates` (Task 9) — a deterministic keyword classifier (not an LLM call) splitting `macro_updates` into `highlights` (core Fed/macro-indicator keywords: 利率/CPI/PMI/非农/GDP/联储/etc., shown individually) and `condensed_counts` (everything else, grouped by keyword into per-category counts, e.g. `{"油气数据": 4, "贵金属持仓": 12}`, rendered as one summary line instead of 16 bullet points). `main.py` (Task 14) now runs raw `fetch_macro_calendar` output through this classifier before it reaches `build_payload`, `build_macro_priority_alerts`, or `render_email` — so the LLM's prompt is also less cluttered, not just the email.
