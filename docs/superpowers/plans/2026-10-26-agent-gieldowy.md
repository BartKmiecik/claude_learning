# Agent Giełdowy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A training-project CLI that collects 12 months of daily prices (GPW stocks, WIG indices, TFI funds) plus news, runs a persona-driven Claude agent that predicts one-month moves using its journaled past, and renders an interactive HTML report.

**Architecture:** Deterministic pipeline (fetch → CSV → signal computation) feeds a single Claude API call whose persona lives in YAML and whose "past" lives in a JSONL journal (predictions + scored outcomes + reflections). A plotly-based report renders data, signals, the agent's analysis, journal history, and news.

**Tech Stack:** Python ≥3.10 (venv, pytest, black), pandas, requests, feedparser, PyYAML, plotly, anthropic SDK (≥1.0). Data sources (probe-verified 2026-10-26): Yahoo chart API v8 (stocks/indices, `.WA` symbols) and bankier.pl public API (fund NAVs); RSS (bankier.pl/money.pl) for news.

**Spec:** [2026-10-26-agent-gieldowy-design.md](../specs/2026-10-26-agent-gieldowy-design.md) — the plan argues from the spec; executors read both.

## Global Constraints

- Python ≥ 3.10; virtualenv at `projects/agent-gieldowy/.venv`; all commands below run from `projects/agent-gieldowy/` with `.venv/Scripts/python -m ...` on Windows.
- TDD: write the failing test first, watch it fail, then implement. One commit per task.
- No live API calls in unit tests — mock HTTP (requests) and mock the Anthropic client. Live smoke tests live behind the `live` pytest marker and are excluded by default (`addopts = "-m 'not live'"`).
- Default model is exactly `claude-opus-5-5`, overridable via env var `AGENT_GIELDOWY_MODEL` (no code change needed to switch).
- Structured output via `output_config={"format": {"type": "json_schema", "schema": ...}}` — never the deprecated `output_format`, never assistant prefill.
- Disclaimer text verbatim in the report: `narzędzie szkoleniowe, nie porada inwestycyjna`.
- Flat-file storage only: `data/<symbol>.csv`, `data/news.json`, `journal/entries.jsonl`. No database.
- Report copy, persona, and journal content are in Polish; code identifiers in English.
- Every commit message ends with the line `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- Black hook: recreated repo-wide in `.claude/settings.json` (Task 1) — the Project 1 convention.

## Review Focus

The five input classes / failure modes the spec implies but is silent on, most likely to bite a real user, most likely first:

1. **A source returns success but no data** (Yahoo `chart.result` null for a bad/renamed symbol; bankier `data` empty) — a reasonable person expects a per-symbol warning and the other instruments still collected. → Pinned in Task 3 (`test_unknown_symbol_reported_not_fatal`).
2. **Running `collect` twice on the same day** — a reasonable person expects the second run to append 0 rows and never duplicate history. → Pinned in Task 3 (`test_incremental_no_duplicates`).
3. **A prediction that passes the schema but omits a watchlist instrument or invents a new symbol** — a reasonable person expects rejection, one retry, then a clear error (never silently persisted). → Pinned in Task 7 (`test_analyze_rejects_missing_and_unknown_symbols`).
4. **Generating the report with an empty journal or missing data files** (first run, or `analyze` failed earlier) — a reasonable person expects the report to render with explicit "brak danych / brak prognozy" placeholders, not a crash. → Pinned in Task 9 (`test_report_empty_state`).
5. **Running `evaluate` twice** — a reasonable person expects the second run to score nothing new (idempotent, no duplicated outcomes/reflections). → Pinned in Task 8 (`test_evaluate_idempotent`).

---

## File Structure

```
projects/agent-gieldowy/
├── pyproject.toml            # package, deps, pytest config, entry point agent-gieldowy
├── .gitignore                # .venv/, data/, journal/, __pycache__, *.egg-info
├── README.md                 # what/why/how (brief)
├── watchlist.yaml            # stocks/indices/funds sections (user-editable)
├── persona.yaml              # agent identity, history, biases (user-editable)
├── src/agent_gieldowy/
│   ├── __init__.py           # empty package marker
│   ├── config.py             # load_watchlist, all_symbols
│   ├── collector.py          # http_get, fetch_quotes, save_incremental, collect
│   ├── news.py               # fetch_news, save_news
│   ├── signals.py            # compute_signals (pure, flat dict)
│   ├── persona.py            # load_persona, render_system_prompt
│   ├── journal.py            # append_entry, read_entries, update_entry, build_digest
│   ├── agent.py              # PREDICTION_SCHEMA, analyze, validate_prediction, prompt builders, AgentError
│   ├── evaluate.py           # scoring + due-entry selection + reflection + evaluate
│   ├── report.py             # render_report (plotly HTML)
│   └── cli.py                # argparse: collect/analyze/evaluate/report/run
└── tests/
    ├── conftest.py           # FakeSession, FakeClient, fixtures
    ├── test_signals.py
    ├── test_collector.py
    ├── test_news.py
    ├── test_journal.py
    ├── test_persona.py
    ├── test_agent.py
    ├── test_evaluate.py
    ├── test_report.py
    ├── test_cli.py
    └── test_live.py          # @pytest.mark.live — manual only
```

---

### Task 1: Scaffolding

**Files:**
- Create: `projects/agent-gieldowy/pyproject.toml`, `projects/agent-gieldowy/.gitignore`, `projects/agent-gieldowy/README.md`, `projects/agent-gieldowy/src/agent_gieldowy/__init__.py`, `projects/agent-gieldowy/tests/__init__.py`, `.claude/settings.json` (repo root)
- Modify: none

**Interfaces:**
- Consumes: nothing
- Produces: installable package `agent-gieldowy` with entry point `agent-gieldowy = agent_gieldowy.cli:main` (cli.py created in Task 10 — entry point import resolves then); pytest configured with `pythonpath = ["src"]`

- [ ] **Step 1: Create the project files**

`projects/agent-gieldowy/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-gieldowy"
version = "0.1.0"
description = "Training project: Polish market data pipeline + persona-driven LLM market analyst"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "requests>=2.31",
    "feedparser>=6.0",
    "pyyaml>=6.0",
    "plotly>=5.18",
    "anthropic>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "black>=24.0"]

[project.scripts]
agent-gieldowy = "agent_gieldowy.cli:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src", "tests"]
testpaths = ["tests"]
addopts = "-m 'not live'"
markers = ["live: live smoke tests — run manually with `pytest -m live`"]
```

`projects/agent-gieldowy/.gitignore`:

```
.venv/
data/
journal/
__pycache__/
.pytest_cache/
*.egg-info/
report.html
```

`projects/agent-gieldowy/README.md`:

```markdown
# Agent Giełdowy

Projekt szkoleniowy (learning path, Project 2): pipeline danych z polskiego rynku
(Yahoo — akcje/indeksy GPW; bankier.pl — fundusze TFI; RSS — newsy) + agent Claude API
z osobowością i dziennikiem przeszłości, prognozujący ruchy kursów na 1 miesiąc,
z raportem HTML (plotly).

Narzędzie szkoleniowe, nie porada inwestycyjna.

## Użycie

    agent-gieldowy run        # collect → analyze → report
    agent-gieldowy collect    # pobierz dane + newsy
    agent-gieldowy analyze    # sygnały + analiza agenta (wymaga danych uwierzytelniających Claude API)
    agent-gieldowy evaluate   # oceń prognozy starsze niż 30 dni
    agent-gieldowy report     # wygeneruj report.html

Konfiguracja: `watchlist.yaml`, `persona.yaml`; model przez zmienną środowiskową
`AGENT_GIELDOWY_MODEL` (domyślnie `claude-opus-5-5`).

## Dev

    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"
    .venv/Scripts/python -m pytest
```

`projects/agent-gieldowy/src/agent_gieldowy/__init__.py`:

```python
"""Agent Giełdowy — training project: PL market pipeline + persona-driven LLM analyst."""
```

`projects/agent-gieldowy/tests/__init__.py`: empty file (0 bytes).

`.claude/settings.json` at the repo root (recreates the Project 1 black-hook convention; the `python -c` wrapper makes the hook shell-dialect-independent and always exits 0):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import os, subprocess, sys; proj = os.path.abspath('projects/agent-gieldowy'); subprocess.run([os.path.join(proj, '.venv', 'Scripts', 'python.exe'), '-m', 'black', 'src', 'tests'], cwd=proj, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); raise SystemExit(0)\""
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Create the virtualenv and install**

Run from `projects/agent-gieldowy/`:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

- [ ] **Step 3: Verify the install**

Run: `.venv/Scripts/python -m pytest`
Expected: `no tests ran` (exit code 5) — the suite is empty but pytest is configured.

Run: `.venv/Scripts/python -c "import agent_gieldowy; print(agent_gieldowy.__doc__)"`
Expected: prints `Agent Giełdowy — training project: PL market pipeline + persona-driven LLM analyst.`

- [ ] **Step 4: Verify the black hook fires**

Create a deliberately unformatted temp file `projects/agent-gieldowy/tests/_hook_probe.py` with content `x=1` (one line, no spaces), wait a moment, then delete the file. If the hook fired, the file content becomes `x = 1`. If it did not fire, note it in the task report for the user to check hook configuration.

- [ ] **Step 5: Commit**

```bash
git add projects/agent-gieldowy .claude/settings.json
git commit -m "feat(agent-gieldowy): scaffold package, pytest, and black hook

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: signals — pure indicator functions

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/signals.py`
- Test: `projects/agent-gieldowy/tests/test_signals.py`

**Interfaces:**
- Consumes: nothing
- Produces: `compute_signals(df: pd.DataFrame) -> dict` where `df` has a `close` column and is sorted oldest→newest; returns a **flat** dict with exactly these keys (all `float`, except the last three which are `bool`/`None`): `return_1m`, `return_3m`, `return_12m`, `annualized_volatility`, `momentum_6m`, `sma50`, `sma200`, `rsi14`, `max_drawdown`, `sma50_above_sma200` (`None` when < 200 rows), `golden_cross_recent` (`False` when < 200 rows), `death_cross_recent` (`False` when < 200 rows). NaN when not enough data (e.g. `return_12m` on a 10-row frame). Consumed by agent.py (Task 7), report.py (Task 9), cli.py (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/test_signals.py`:

```python
import math

import numpy as np
import pandas as pd
import pytest

from agent_gieldowy.signals import compute_signals


def frame(closes, dates=None):
    if dates is None:
        dates = pd.bdate_range("2025-01-01", periods=len(closes))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes})


def test_returns_on_rising_series():
    closes = list(range(1, 401))  # 400 rows
    s = compute_signals(frame(closes))
    assert s["return_1m"] > 0
    assert s["return_3m"] > 0
    assert s["return_12m"] > 0
    assert s["momentum_6m"] > 0


def test_returns_on_falling_series():
    closes = list(range(400, 0, -1))
    s = compute_signals(frame(closes))
    assert s["return_1m"] < 0
    assert s["momentum_6m"] < 0


def test_constant_series_has_zero_volatility_and_neutral_rsi():
    s = compute_signals(frame([100.0] * 300))
    assert s["annualized_volatility"] == pytest.approx(0.0)
    assert s["rsi14"] == pytest.approx(50.0)


def test_rising_series_rsi_is_100():
    s = compute_signals(frame([100.0 + i for i in range(300)]))
    assert s["rsi14"] == pytest.approx(100.0)


def test_max_drawdown_from_peak():
    closes = [100.0] * 50 + [50.0] * 50  # drops 50% from the peak
    s = compute_signals(frame(closes))
    assert s["max_drawdown"] == pytest.approx(-0.5)


def test_cross_flags_golden_cross_recent():
    # SMA50 below SMA200 for 200 rows, then a sharp rally crosses it up in the last 5
    closes = [100.0] * 200 + [300.0] * 5
    s = compute_signals(frame(closes))
    assert s["sma50_above_sma200"] is True
    assert s["golden_cross_recent"] is True
    assert s["death_cross_recent"] is False


def test_insufficient_data_returns_nan_and_none():
    s = compute_signals(frame([100.0, 101.0, 102.0]))
    assert math.isnan(s["return_12m"])
    assert math.isnan(s["sma200"])
    assert s["sma50_above_sma200"] is None
    assert s["golden_cross_recent"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.signals'`

- [ ] **Step 3: Implement signals.py**

`src/agent_gieldowy/signals.py`:

```python
"""Deterministic technical signals computed from a (date, close) frame. Pure — no I/O."""

import math

import pandas as pd

TRADING_DAYS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}


def _returns(df: pd.DataFrame, periods: int) -> float:
    if len(df) <= periods:
        return float("nan")
    base = df["close"].iloc[-(periods + 1)]
    last = df["close"].iloc[-1]
    if base == 0:
        return float("nan")
    return float(last / base - 1)


def _annualized_volatility(df: pd.DataFrame) -> float:
    daily = df["close"].pct_change().dropna()
    if len(daily) < 2:
        return float("nan")
    return float(daily.std() * (252 ** 0.5))


def _sma(df: pd.DataFrame, window: int) -> float:
    if len(df) < window:
        return float("nan")
    return float(df["close"].rolling(window).mean().iloc[-1])


def _cross_flags(df: pd.DataFrame) -> dict:
    if len(df) < 200:
        return {"sma50_above_sma200": None, "golden_cross_recent": False, "death_cross_recent": False}
    s50 = df["close"].rolling(50).mean()
    s200 = df["close"].rolling(200).mean()
    above_now = bool(s50.iloc[-1] > s200.iloc[-1])
    above_5_days_ago = bool(s50.iloc[-6] > s200.iloc[-6])
    return {
        "sma50_above_sma200": above_now,
        "golden_cross_recent": above_now and not above_5_days_ago,
        "death_cross_recent": not above_now and above_5_days_ago,
    }


def _rsi14(df: pd.DataFrame) -> float:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()
    if len(avg_loss.dropna()) == 0:
        return float("nan")
    ag, al = float(avg_gain.iloc[-1]), float(avg_loss.iloc[-1])
    if ag == 0 and al == 0:
        return 50.0
    if al == 0:
        return 100.0
    return float(100 - 100 / (1 + ag / al))


def _max_drawdown(df: pd.DataFrame) -> float:
    return float((df["close"] / df["close"].cummax() - 1).min())


def compute_signals(df: pd.DataFrame) -> dict:
    """Flat dict of signals for a (date, close) frame sorted oldest→newest."""
    signals = {
        "return_1m": _returns(df, TRADING_DAYS["1M"]),
        "return_3m": _returns(df, TRADING_DAYS["3M"]),
        "return_12m": _returns(df, TRADING_DAYS["12M"]),
        "annualized_volatility": _annualized_volatility(df),
        "momentum_6m": _returns(df, TRADING_DAYS["6M"]),
        "sma50": _sma(df, 50),
        "sma200": _sma(df, 200),
        "rsi14": _rsi14(df),
        "max_drawdown": _max_drawdown(df),
    }
    signals.update(_cross_flags(df))
    return signals
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_signals.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/signals.py projects/agent-gieldowy/tests/test_signals.py
git commit -m "feat(agent-gieldowy): add pure signal functions

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: config + collector (Yahoo + bankier)

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/config.py`, `projects/agent-gieldowy/src/agent_gieldowy/collector.py`, `projects/agent-gieldowy/watchlist.yaml`
- Test: `projects/agent-gieldowy/tests/test_collector.py`, `projects/agent-gieldowy/tests/conftest.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `config.load_watchlist(path) -> dict` with keys `stocks` / `indices` / `funds`, each a list of symbol strings.
  - `config.all_symbols(watchlist) -> list[dict]`, each item `{"symbol": str, "kind": "stock"|"index"|"fund"}` (watchlist section order: stocks, indices, funds).
  - `collector.http_get(url, params=None, session=None) -> requests.Response` — GET with `HEADERS`, `TIMEOUT=10`, retries `MAX_RETRIES=2` with sleep 1s/2s; raises `CollectorError` after exhausting retries.
  - `collector.CollectorError(Exception)`; `collector.UnknownSymbolError(CollectorError)`.
  - `collector.fetch_quotes(symbol: str, kind: str, session=None) -> pd.DataFrame` with columns `date` (ISO string `YYYY-MM-DD`), `close` (float), trimmed to the last 365 calendar days, sorted oldest→newest.
  - `collector.save_incremental(symbol: str, new_df: pd.DataFrame, data_dir) -> int` — appends only rows newer than the last local date; returns rows appended (0 if nothing new).
  - `collector.collect(watchlist: dict, data_dir, session=None) -> dict` — `{symbol: {"status": "ok", "rows": int, "appended": int}}` or `{symbol: {"status": "error", "error": str}}`; **one failing symbol never aborts the others**. Consumed by cli.py (Task 10), evaluate.py (Task 8 via CSV files).

- [ ] **Step 1: Write the shared test fixtures**

`tests/conftest.py`:

```python
import json
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import requests


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class FakeSession:
    """Scripted responses, one per get() call, consumed in order.

    A response may be a FakeResponse or a callable(url, params, headers, timeout)
    that raises — callables let tests script network failures.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        response = self.responses.pop(0)
        if callable(response):
            return response(url, params, headers, timeout)
        return response


def yahoo_payload(dates, closes):
    """Minimal Yahoo chart API v8 payload for the given business-day dates and closes."""
    timestamps = [int(pd.Timestamp(d).timestamp()) for d in dates]
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }


def bankier_payload(dates, navs):
    """Minimal bankier fund chart payload: data[0].data = [[epoch_ms, nav], ...]."""
    rows = [[int(pd.Timestamp(d).timestamp() * 1000), nav] for d, nav in zip(dates, navs)]
    return {"parameters": {"symbol": "X", "range": "max"}, "data": [{"data": rows}]}


def bdate_range(days):
    return pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=days)


@pytest.fixture
def watchlist():
    return {
        "stocks": ["PKO.WA"],
        "indices": ["WIG20.WA"],
        "funds": ["AGF04"],
    }
```

- [ ] **Step 2: Write the failing tests**

`tests/test_collector.py`:

```python
import pandas as pd
import pytest
import requests

from agent_gieldowy.collector import (
    CollectorError,
    UnknownSymbolError,
    collect,
    fetch_quotes,
    save_incremental,
)
from agent_gieldowy.config import all_symbols, load_watchlist
from conftest import FakeResponse, FakeSession, bankier_payload, bdate_range, yahoo_payload


def test_load_watchlist_and_all_symbols(tmp_path, watchlist):
    p = tmp_path / "watchlist.yaml"
    p.write_text("stocks:\n  - PKO.WA\nindices:\n  - WIG20.WA\nfunds:\n  - AGF04\n", encoding="utf-8")
    wl = load_watchlist(p)
    assert all_symbols(wl) == [
        {"symbol": "PKO.WA", "kind": "stock"},
        {"symbol": "WIG20.WA", "kind": "index"},
        {"symbol": "AGF04", "kind": "fund"},
    ]


def test_fetch_quotes_stock_trims_to_365_days():
    dates = bdate_range(800)  # ~3 years of business days
    closes = [100.0 + i * 0.1 for i in range(800)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    assert len(df) < 800
    assert (df["date"] >= (pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")).all()
    assert list(df.columns) == ["date", "close"]
    assert df["date"].is_monotonic_increasing


def test_fetch_quotes_fund_parses_bankier_payload():
    dates = bdate_range(400)
    navs = [50.0 + i * 0.05 for i in range(400)]
    session = FakeSession([FakeResponse(bankier_payload(dates, navs))])
    df = fetch_quotes("AGF04", "fund", session)
    assert len(df) < 400  # trimmed to the last 365 calendar days
    assert df["date"].ge((pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")).all()
    assert df["close"].iloc[-1] == pytest.approx(69.95)  # 50.0 + 399*0.05


def test_unknown_symbol_reported_not_fatal(tmp_path, watchlist):
    # Review Focus #1: empty result for one symbol must not abort the others
    session = FakeSession(
        [
            FakeResponse({"chart": {"result": None}}),  # PKO.WA unknown
            FakeResponse(yahoo_payload(bdate_range(400), [100.0] * 400)),  # WIG20.WA ok
            FakeResponse(bankier_payload(bdate_range(400), [50.0] * 400)),  # AGF04 ok
        ]
    )
    results = collect(watchlist, tmp_path / "data", session)
    assert results["PKO.WA"]["status"] == "error"
    assert "PKO.WA" in results["PKO.WA"]["error"]
    assert results["WIG20.WA"]["status"] == "ok"
    assert results["AGF04"]["status"] == "ok"


def test_incremental_no_duplicates(tmp_path):
    # Review Focus #2: collecting twice on the same day appends nothing new
    dates = bdate_range(400)
    closes = [100.0 + i for i in range(400)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    first = save_incremental("PKO.WA", df, tmp_path)
    second = save_incremental("PKO.WA", df, tmp_path)
    stored = pd.read_csv(tmp_path / "PKO.WA.csv")
    assert first == len(df)
    assert second == 0
    assert not stored["date"].duplicated().any()


def test_incremental_appends_only_new_rows(tmp_path):
    dates = bdate_range(400)
    closes = [100.0 + i for i in range(400)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    save_incremental("PKO.WA", df, tmp_path)
    new_day = pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)
    new_rows = pd.DataFrame({"date": [new_day.strftime("%Y-%m-%d")], "close": [999.0]})
    appended = save_incremental("PKO.WA", new_rows, tmp_path)
    stored = pd.read_csv(tmp_path / "PKO.WA.csv")
    assert appended == 1
    assert stored.iloc[-1]["close"] == 999.0


def test_retries_then_raises_on_persistent_network_error():
    def boom(url, params=None, headers=None, timeout=None):
        raise requests.RequestException("connection refused")

    session = FakeSession([boom, boom, boom])
    with pytest.raises(CollectorError):
        fetch_quotes("PKO.WA", "stock", session)
    assert len(session.calls) == 3
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.collector'`

- [ ] **Step 4: Implement config.py**

`src/agent_gieldowy/config.py`:

```python
"""Watchlist configuration loading."""

import yaml


def load_watchlist(path) -> dict:
    """Load watchlist.yaml — dict with sections 'stocks', 'indices', 'funds'."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_symbols(watchlist: dict) -> list:
    """Flatten the watchlist into [{'symbol', 'kind'}], in section order."""
    kind_by_section = {"stocks": "stock", "indices": "index", "funds": "fund"}
    items = []
    for section, kind in kind_by_section.items():
        for symbol in watchlist.get(section, []) or []:
            items.append({"symbol": symbol, "kind": kind})
    return items
```

- [ ] **Step 5: Implement collector.py**

`src/agent_gieldowy/collector.py`:

```python
"""Collect 12 months of daily quotes from Yahoo (stocks/indices) and bankier.pl (funds).

Both sources are normalized to a common (date, close) frame and stored per symbol
in data/<symbol>.csv, incrementally (only new days are appended).
"""

import time
from pathlib import Path

import pandas as pd
import requests

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
BANKIER_URL = "https://api.bankier.pl/quotes/public/bankier-tfi/bankier-fund-chart-data"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 10
MAX_RETRIES = 2


class CollectorError(Exception):
    """A data source failed after retries."""


class UnknownSymbolError(CollectorError):
    """The source returned success but no data for this symbol."""


def http_get(url: str, params=None, session=None) -> requests.Response:
    """GET with retries; raises CollectorError after MAX_RETRIES exhausted."""
    sess = session or requests
    last = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = sess.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # noqa: PERF203
            last = exc
            if attempt < MAX_RETRIES:
                time.sleep(1 + attempt)
    raise CollectorError(f"request failed after retries: {url}: {last}")


def _cutoff_iso() -> str:
    return (pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime("%Y-%m-%d")


def _to_iso_date(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%d")


def fetch_quotes(symbol: str, kind: str, session=None) -> pd.DataFrame:
    """Daily (date, close) frame for the last 365 calendar days, oldest→newest."""
    if kind == "fund":
        resp = http_get(BANKIER_URL, params={"symbol": symbol}, session=session)
        payload = resp.json()
        rows = payload["data"][0]["data"]  # [[epoch_ms, nav], ...]
        if not rows:
            raise UnknownSymbolError(f"bankier returned no data for {symbol}")
        df = pd.DataFrame(rows, columns=["epoch_ms", "close"])
        df["date"] = _to_iso_date(pd.to_datetime(df["epoch_ms"], unit="ms", utc=True))
        df = df[["date", "close"]]
    else:
        resp = http_get(YAHOO_URL.format(symbol=symbol), params={"range": "2y", "interval": "1d"}, session=session)
        result = (resp.json().get("chart") or {}).get("result")
        if not result:
            raise UnknownSymbolError(f"Yahoo has no data for {symbol}")
        ts = result[0]["timestamp"]
        closes = result[0]["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({"ts": ts, "close": closes})
        df["date"] = _to_iso_date(pd.to_datetime(df["ts"], unit="s", utc=True))
        df = df.dropna(subset=["close"])[["date", "close"]]
    df = df[df["date"] >= _cutoff_iso()].sort_values("date").reset_index(drop=True)
    return df


def save_incremental(symbol: str, new_df: pd.DataFrame, data_dir) -> int:
    """Append rows newer than the last local date; return rows appended."""
    data_dir = Path(data_dir)
    path = data_dir / f"{symbol}.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["date", "close"])
    if not old.empty:
        new_df = new_df[new_df["date"] > old["date"].max()]
    if new_df.empty:
        return 0
    merged = pd.concat([old, new_df], ignore_index=True).drop_duplicates(subset="date")
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(path, index=False)
    return len(new_df)


def collect(watchlist: dict, data_dir, session=None) -> dict:
    """Collect every watchlist instrument; one failure never aborts the rest."""
    from agent_gieldowy.config import all_symbols

    results = {}
    for item in all_symbols(watchlist):
        try:
            df = fetch_quotes(item["symbol"], item["kind"], session)
            appended = save_incremental(item["symbol"], df, data_dir)
            results[item["symbol"]] = {"status": "ok", "rows": len(df), "appended": appended}
        except CollectorError as exc:
            results[item["symbol"]] = {"status": "error", "error": str(exc)}
    return results
```

- [ ] **Step 6: Create the default watchlist**

`projects/agent-gieldowy/watchlist.yaml`:

```yaml
# Watchlista agenta giełdowego. Symbole zweryfikowane 2026-10-26.
stocks:
  - PKO.WA
  - PZU.WA
  - PKN.WA
indices:
  - WIG20.WA
  - WIG.WA
  - MWIG40.WA
funds:
  - AGF04  # AGIO Kapitał
  - AGF44  # AGIO Akcji PLUS
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collector.py -v`
Expected: PASS (7 tests). Note: `test_retries_then_raises_on_persistent_network_error` calls `session.get` three times — the FakeSession's `get` calls `boom` which raises `requests.RequestException` inside the retry loop; verify no other failures.

- [ ] **Step 8: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/config.py projects/agent-gieldowy/src/agent_gieldowy/collector.py projects/agent-gieldowy/watchlist.yaml projects/agent-gieldowy/tests/conftest.py projects/agent-gieldowy/tests/test_collector.py
git commit -m "feat(agent-gieldowy): add Yahoo/bankier collector with incremental CSV storage

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: news — RSS headlines

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/news.py`
- Test: `projects/agent-gieldowy/tests/test_news.py`

**Interfaces:**
- Consumes: `collector.http_get`, `collector.CollectorError`
- Produces:
  - `news.fetch_news(feed_urls: list[str], limit: int = 20, session=None) -> list[dict]`, each item `{"title": str, "published": str, "link": str}`; keeps the latest `limit` items across all feeds; a failing feed is skipped (the others still return).
  - `news.save_news(items: list[dict], data_dir) -> None` — writes `data/news.json` (UTF-8, ensure_ascii=False, indent=2). Consumed by cli.py (Task 10), report.py (Task 9), agent prompt (Task 7 via the saved file).

- [ ] **Step 1: Verify the RSS feed URLs (probe, not a test)**

Run:

```bash
curl -sI --max-time 15 "https://www.bankier.pl/rss/wiadomosci.xml" | head -1
curl -sI --max-time 15 "https://www.money.pl/rss/main.xml" | head -1
```

Expected: HTTP 200 for at least one of the two. The code below ships both URLs — `fetch_news` tolerates a dead feed by design, so this step only confirms (and if neither works, replace `NEWS_FEEDS` with a feed that does, e.g. `https://www.bankier.pl/rss/gospodarka.xml`, and re-run this step).

- [ ] **Step 2: Write the failing tests**

`tests/test_news.py`:

```python
import json

import pytest

from agent_gieldowy.news import NEWS_FEEDS, fetch_news, save_news
from conftest import FakeResponse, FakeSession

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title>
<item><title>Pierwszy nagłówek</title><pubDate>Mon, 20 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/1</link></item>
<item><title>Drugi nagłówek</title><pubDate>Tue, 21 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/2</link></item>
<item><title>Trzeci nagłówek</title><pubDate>Wed, 22 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/3</link></item>
</channel></rss>
"""


def test_fetch_news_parses_items_and_applies_limit():
    session = FakeSession([FakeResponse(text=RSS_XML)])
    items = fetch_news(["https://feed.example/rss"], limit=2, session=session)
    assert len(items) == 2
    assert items[0]["title"] == "Drugi nagłówek"  # latest `limit` items win
    assert items[0]["link"] == "https://example.com/2"


def test_fetch_news_skips_dead_feed():
    def boom(url, params=None, headers=None, timeout=None):
        from agent_gieldowy.collector import CollectorError

        raise CollectorError("dead feed")

    session = FakeSession([boom, FakeResponse(text=RSS_XML)])
    items = fetch_news(["https://dead.example/rss", "https://live.example/rss"], limit=10, session=session)
    assert len(items) == 3  # only the live feed contributed


def test_save_news_writes_json(tmp_path):
    items = [{"title": "X", "published": "2026-10-26", "link": "https://example.com/x"}]
    save_news(items, tmp_path)
    loaded = json.loads((tmp_path / "news.json").read_text(encoding="utf-8"))
    assert loaded == items


def test_news_feeds_are_configured():
    assert len(NEWS_FEEDS) >= 1
    assert all(u.startswith("https://") for u in NEWS_FEEDS)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_news.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.news'`

- [ ] **Step 4: Implement news.py**

`src/agent_gieldowy/news.py`:

```python
"""Recent financial headlines from RSS feeds (bankier.pl, money.pl fallback)."""

import json
from pathlib import Path

import feedparser

from agent_gieldowy.collector import CollectorError, http_get

NEWS_FEEDS = [
    "https://www.bankier.pl/rss/wiadomosci.xml",
    "https://www.money.pl/rss/main.xml",
]


def fetch_news(feed_urls, limit: int = 20, session=None) -> list:
    """Latest `limit` items across feeds as [{'title', 'published', 'link'}].

    A failing feed is skipped — one dead feed must not kill collect.
    """
    items = []
    for url in feed_urls:
        try:
            resp = http_get(url, session=session)
        except CollectorError:
            continue
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            items.append(
                {
                    "title": entry.get("title", ""),
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                }
            )
    return items[-limit:] if len(items) > limit else items


def save_news(items: list, data_dir) -> None:
    path = Path(data_dir) / "news.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_news.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/news.py projects/agent-gieldowy/tests/test_news.py
git commit -m "feat(agent-gieldowy): add RSS news fetching with dead-feed tolerance

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: journal — the agent's memory store

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/journal.py`
- Test: `projects/agent-gieldowy/tests/test_journal.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `journal.append_entry(entries_path, entry: dict) -> dict` — adds `id` (uuid4 hex) and `created_at` (UTC ISO 8601), appends one JSON line, returns the stored entry.
  - `journal.read_entries(entries_path) -> list[dict]` — oldest→newest; missing file → `[]`; skips blank lines.
  - `journal.update_entry(entries_path, entry_id: str, patch: dict) -> None` — merges `patch` into the entry with that `id`, rewrites the file.
  - `journal.build_digest(entries: list[dict], full_count: int = 3) -> dict` — `{"recent": [last 3 full entries], "older": [compacted older entries], "total_entries": N}`; compaction keeps only `created_at`, `directions` (symbol→direction from the prediction), `outcomes`, `reflection`. Consumed by agent.py (Task 7), evaluate.py (Task 8), report.py (Task 9), cli.py (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/test_journal.py`:

```python
import json

import pytest

from agent_gieldowy.journal import append_entry, build_digest, read_entries, update_entry


@pytest.fixture
def entries_path(tmp_path):
    return tmp_path / "journal" / "entries.jsonl"


def make_entry(prediction=None):
    return {
        "prediction": prediction
        or {
            "horizon": "1M",
            "generated_at": "2026-10-01T12:00:00+00:00",
            "predictions": [
                {"symbol": "PKO.WA", "direction": "up", "range_pct": {"min": -5, "max": 8},
                 "confidence": 65, "rationale": "r", "risks": ["x"]}
            ],
            "summary": "s",
            "analysis": "a",
        }
    }


def test_append_adds_id_and_created_at(entries_path):
    stored = append_entry(entries_path, make_entry())
    assert stored["id"]
    assert stored["created_at"].startswith("2026")
    lines = entries_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == stored


def test_read_missing_file_returns_empty(entries_path):
    assert read_entries(entries_path) == []


def test_append_and_read_roundtrip(entries_path):
    append_entry(entries_path, make_entry())
    append_entry(entries_path, make_entry())
    entries = read_entries(entries_path)
    assert len(entries) == 2
    assert entries[0]["id"] != entries[1]["id"]


def test_update_entry_patches_by_id(entries_path):
    stored = append_entry(entries_path, make_entry())
    update_entry(entries_path, stored["id"], {"reflection": "Byłem zbyt ostrożny."})
    entries = read_entries(entries_path)
    assert entries[0]["reflection"] == "Byłem zbyt ostrożny."
    assert entries[0]["id"] == stored["id"]
    assert len(read_entries(entries_path)) == 1  # no duplicated lines


def test_build_digest_compacts_older_entries(entries_path):
    for i in range(5):
        entry = make_entry()
        entry["prediction"]["predictions"][0]["symbol"] = f"SYM{i}.WA"
        entry["prediction"]["predictions"][0]["direction"] = "down"
        entry["outcomes"] = {"SYM{i}.WA": {"scored": True, "direction_hit": False}}
        entry["reflection"] = f"refleksja {i}"
        append_entry(entries_path, entry)
    digest = build_digest(read_entries(entries_path))
    assert digest["total_entries"] == 5
    assert len(digest["recent"]) == 3
    assert len(digest["older"]) == 2
    older = digest["older"][0]
    assert older["directions"] == {"SYM0.WA": "down"}
    assert older["reflection"] == "refleksja 0"
    assert "analysis" not in older  # compacted away
    assert "analysis" in digest["recent"][0]  # recent entries stay full
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_journal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.journal'`

- [ ] **Step 3: Implement journal.py**

`src/agent_gieldowy/journal.py`:

```python
"""JSONL journal — the agent's growing memory of analyses, predictions, outcomes."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_entry(entries_path, entry: dict) -> dict:
    """Add id/created_at, append one JSON line, return the stored entry."""
    stored = {**entry, "id": uuid.uuid4().hex, "created_at": _now_iso()}
    entries_path = Path(entries_path)
    entries_path.parent.mkdir(parents=True, exist_ok=True)
    with open(entries_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stored, ensure_ascii=False) + "\n")
    return stored


def read_entries(entries_path) -> list:
    """Entries oldest→newest; missing file → []."""
    entries_path = Path(entries_path)
    if not entries_path.exists():
        return []
    entries = []
    for line in entries_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def update_entry(entries_path, entry_id: str, patch: dict) -> None:
    """Merge `patch` into the entry with `id == entry_id`; rewrite the file."""
    entries_path = Path(entries_path)
    entries = read_entries(entries_path)
    for entry in entries:
        if entry["id"] == entry_id:
            entry.update(patch)
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    entries_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _compact(entry: dict) -> dict:
    predictions = entry.get("prediction", {}).get("predictions", [])
    return {
        "created_at": entry.get("created_at"),
        "directions": {p["symbol"]: p["direction"] for p in predictions},
        "outcomes": entry.get("outcomes"),
        "reflection": entry.get("reflection"),
    }


def build_digest(entries: list, full_count: int = 3) -> dict:
    """Deterministic digest: last `full_count` entries in full, older ones compacted."""
    recent = entries[-full_count:] if full_count else []
    older = entries[:-full_count] if full_count else list(entries)
    return {
        "recent": recent,
        "older": [_compact(e) for e in older],
        "total_entries": len(entries),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_journal.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/journal.py projects/agent-gieldowy/tests/test_journal.py
git commit -m "feat(agent-gieldowy): add JSONL journal with deterministic digest

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: persona — identity rendered into a system prompt

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/persona.py`, `projects/agent-gieldowy/persona.yaml`
- Test: `projects/agent-gieldowy/tests/test_persona.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `persona.load_persona(path) -> dict` (YAML)
  - `persona.render_system_prompt(persona: dict) -> str` — Polish system prompt containing every identity field, every `life_history` line, every `biases` line, and an instruction to weigh the journaled past. Consumed by agent.py (Task 7), evaluate.py (Task 8), cli.py (Task 10), report.py (Task 9 via the persona card).

- [ ] **Step 1: Write the failing tests**

`tests/test_persona.py`:

```python
from agent_gieldowy.persona import load_persona, render_system_prompt


PERSONA_YAML = """\
name: "Andrzej Malinowski"
age: 55
city: "Kraków"
profession: "analityk w towarzystwie funduszy inwestycyjnych (TFI)"
social_position: "wyższa klasa średnia"
education: "mgr ekonomii"
life_history:
  - "Przeżył krach 2008 roku."
biases:
  - "awersja do ryzyka"
  - "ufa spółkom dywidendowym"
temperament: "spokojny"
style: "konkretny, po polsku"
"""


def test_load_persona(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA_YAML, encoding="utf-8")
    persona = load_persona(p)
    assert persona["name"] == "Andrzej Malinowski"
    assert persona["age"] == 55


def test_render_system_prompt_contains_identity_history_and_biases(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA_YAML, encoding="utf-8")
    prompt = render_system_prompt(load_persona(p))
    assert "Andrzej Malinowski" in prompt
    assert "analityk w towarzystwie funduszy inwestycyjnych" in prompt
    assert "Przeżył krach 2008 roku." in prompt
    assert "awersja do ryzyka" in prompt
    assert "ufa spółkom dywidendowym" in prompt
    assert "dziennika" in prompt  # instruction to weigh the journaled past
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_persona.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.persona'`

- [ ] **Step 3: Implement persona.py**

`src/agent_gieldowy/persona.py`:

```python
"""Persona YAML → system prompt. The biases are first-class, visible, and editable."""

import yaml


def load_persona(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_system_prompt(persona: dict) -> str:
    history = "\n".join(f"- {line}" for line in persona.get("life_history", []))
    biases = "\n".join(f"- {line}" for line in persona.get("biases", []))
    return (
        f"Jesteś {persona['name']}, {persona['age']} lat, z {persona['city']}. "
        f"Zawód: {persona['profession']}. Pozycja społeczna: {persona['social_position']}. "
        f"Wykształcenie: {persona['education']}.\n\n"
        f"Twoja historia, która kształtuje Twoje sądy:\n{history}\n\n"
        f"Temperament: {persona['temperament']}.\n\n"
        f"Twoje skłonności (świadomie uwzględniaj je w analizie):\n{biases}\n\n"
        f"Styl: {persona['style']}.\n\n"
        "Analizujesz polski rynek i prognozujesz zmiany kursów na 1 miesiąc. "
        "Zawsze uwzględniaj swoją przeszłość z dziennika: wcześniejsze prognozy, "
        "ich wyniki i własne refleksje."
    )
```

- [ ] **Step 4: Create the default persona**

`projects/agent-gieldowy/persona.yaml`:

```yaml
# Osobowość agenta. Edytowalna — zmiana pliku zmienia analizy.
name: "Andrzej Malinowski"
age: 55
city: "Kraków"
profession: "analityk w towarzystwie funduszy inwestycyjnych (TFI)"
social_position: "wyższa klasa średnia; stabilna praca od 30 lat; mieszkanie na własność, oszczędności w funduszach"
education: "mgr ekonomii, Akademia Ekonomiczna w Krakowie"
life_history:
  - "Przeżył krach 2008 roku — stracił wtedy część własnych oszczędności zainwestowanych w akcje banków."
  - "Pamięta panikę covidową 2020 i szybkie odbicie, które przegapił, bo za długo czekał na 'drugie dno'."
  - "Od 2015 inwestuje regularnie w fundusze dywidendowe i obligacje; akcje growth traktuje z nieufnością."
temperament: "spokojny, ostrożny, przywiązany do fundamentalnej wartości; unika pośpiechu i modnych trendów"
biases:
  - "awersja do ryzyka — woli mniejszy, pewniejszy zwrot"
  - "ufa spółkom dywidendowym o stabilnych przepływach"
  - "nieufny wobec spółek wzrostowych i modnych tematów (AI, krypto)"
  - "przecenia wagę własnych doświadczeń z 2008 i 2020"
style: "konkretny, po polsku; krótkie zdania; unika żargonu angielskiego"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_persona.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/persona.py projects/agent-gieldowy/persona.yaml projects/agent-gieldowy/tests/test_persona.py
git commit -m "feat(agent-gieldowy): add persona YAML and system-prompt renderer

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: agent — Claude API call with structured output

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/agent.py`
- Test: `projects/agent-gieldowy/tests/test_agent.py`

**Interfaces:**
- Consumes: `journal.build_digest`, `persona.render_system_prompt` (inputs come from the caller), the `anthropic` SDK (`Anthropic()`, typed exceptions)
- Produces:
  - `agent.AgentError(Exception)` — user-facing, Polish messages.
  - `agent.default_model() -> str` — `os.environ.get("AGENT_GIELDOWY_MODEL", "claude-opus-5-5")`.
  - `agent.PREDICTION_SCHEMA: dict` — JSON Schema for structured output (see Step 3).
  - `agent.fmt(v, pct=False) -> str` — NaN/None → `"—"`, `pct=True` → `f"{v:.1%}"`, else `f"{v:.2f}"`.
  - `agent.build_signals_table(signals_by_symbol: dict[str, dict]) -> str` — one line per symbol using `fmt`.
  - `agent.build_user_message(signals_table: str, news_items: list[dict], digest: dict, watchlist_symbols: list[str]) -> str` — Polish prompt with data, headlines, journal digest, and the task (sideways = expected change within ±2%).
  - `agent.validate_prediction(prediction: dict, watchlist_symbols: list[str]) -> list[str]` — empty list = valid.
  - `agent.analyze(persona_prompt: str, user_message: str, watchlist_symbols: list[str], client=None, model=None) -> dict` — returns the **validated** prediction dict with `generated_at` added (UTC ISO); up to 2 attempts total (retries cover rate limits and invalid responses); raises `AgentError` otherwise. Consumed by cli.py (Task 10), evaluate.py (Task 8 uses `default_model`).

- [ ] **Step 1: Write the failing tests**

`tests/test_agent.py`:

```python
import json
from types import SimpleNamespace

import anthropic
import pytest

from agent_gieldowy.agent import (
    AgentError,
    PREDICTION_SCHEMA,
    analyze,
    build_signals_table,
    build_user_message,
    default_model,
    fmt,
    validate_prediction,
)


def valid_prediction(symbols=("PKO.WA",)):
    return {
        "horizon": "1M",
        "predictions": [
            {
                "symbol": s,
                "direction": "up",
                "range_pct": {"min": -5.0, "max": 8.0},
                "confidence": 65,
                "rationale": "Stabilne fundamenty.",
                "risks": ["Ryzyko polityczne"],
            }
            for s in symbols
        ],
        "summary": "Ostrożnie pozytywnie.",
        "analysis": "Pełna analiza w duchu persony.",
    }


class FakeMessages:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        text = json.dumps(payload)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, payloads):
        self.messages = FakeMessages(payloads)


def test_default_model_uses_env(monkeypatch):
    assert default_model() == "claude-opus-5-5"
    monkeypatch.setenv("AGENT_GIELDOWY_MODEL", "claude-haiku-5-5")
    assert default_model() == "claude-haiku-5-5"


def test_fmt_handles_nan_and_percent():
    assert fmt(float("nan")) == "—"
    assert fmt(None) == "—"
    assert fmt(0.0523, pct=True) == "5.2%"
    assert fmt(1.2345) == "1.23"


def test_build_signals_table_renders_every_symbol():
    signals = {
        "PKO.WA": {
            "return_1m": 0.01, "return_3m": 0.03, "return_12m": 0.12,
            "annualized_volatility": 0.18, "momentum_6m": 0.05,
            "sma50": 51.0, "sma200": 49.0, "rsi14": 55.0, "max_drawdown": -0.2,
            "sma50_above_sma200": True, "golden_cross_recent": False, "death_cross_recent": False,
        }
    }
    table = build_signals_table(signals)
    assert "PKO.WA" in table
    assert "1M 1.0%" in table
    assert "maxDD -20.0%" in table


def test_build_user_message_contains_data_news_digest_and_task():
    digest = {
        "recent": [{"id": "a", "created_at": "2026-10-01T00:00:00+00:00", "prediction": valid_prediction()}],
        "older": [],
        "total_entries": 1,
    }
    msg = build_user_message(
        "PKO.WA: 1M 1.0%",
        [{"title": "Bankier: wzrosty na GPW", "published": "2026-10-26", "link": "https://x/1"}],
        digest,
        ["PKO.WA"],
    )
    assert "PKO.WA: 1M 1.0%" in msg
    assert "Bankier: wzrosty na GPW" in msg
    assert "2026-10-01" in msg
    assert "PKO.WA" in msg
    assert "±2%" in msg  # sideways definition reaches the model


def test_validate_prediction_accepts_valid():
    assert validate_prediction(valid_prediction(["PKO.WA"]), ["PKO.WA"]) == []


def test_analyze_returns_prediction_with_generated_at():
    client = FakeClient([valid_prediction()])
    result = analyze("prompt", "msg", ["PKO.WA"], client=client)
    assert result["horizon"] == "1M"
    assert result["generated_at"].startswith("2026")
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == "prompt"
    assert call["output_config"]["format"]["schema"] == PREDICTION_SCHEMA
    assert call["max_tokens"] == 16000


def test_analyze_rejects_missing_and_unknown_symbols():
    # Review Focus #3: schema-valid JSON that misses an instrument / invents one
    bad = valid_prediction(["PKO.WA"])  # missing WIG20.WA, plus... make one up:
    bad["predictions"].append(
        {"symbol": "FAKE.WA", "direction": "up", "range_pct": {"min": -1, "max": 1},
         "confidence": 10, "rationale": "x", "risks": []}
    )
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError) as exc:
        analyze("p", "m", ["PKO.WA", "WIG20.WA"], client=client)
    assert "WIG20.WA" in str(exc.value)
    assert "FAKE.WA" in str(exc.value)
    assert len(client.messages.calls) == 2  # one retry, then give up


def test_analyze_rejects_inverted_range():
    bad = valid_prediction()
    bad["predictions"][0]["range_pct"] = {"min": 8.0, "max": -5.0}
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError):
        analyze("p", "m", ["PKO.WA"], client=client)
    assert len(client.messages.calls) == 2


def test_analyze_retries_after_rate_limit_then_succeeds():
    rate_limit = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    client = FakeClient([rate_limit, valid_prediction()])
    result = analyze("p", "m", ["PKO.WA"], client=client)
    assert result["predictions"][0]["symbol"] == "PKO.WA"
    assert len(client.messages.calls) == 2


def test_analyze_wraps_auth_error_with_instruction():
    auth = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    client = FakeClient([auth, auth])
    with pytest.raises(AgentError) as exc:
        analyze("p", "m", ["PKO.WA"], client=client)
    assert "ant auth login" in str(exc.value)


def test_analyze_parses_garbage_then_retries():
    class Garbage:
        pass

    client = FakeClient([Garbage(), valid_prediction()])
    result = analyze("p", "m", ["PKO.WA"], client=client)
    assert result["predictions"][0]["symbol"] == "PKO.WA"
```

Note: `json.dumps` of a `SimpleNamespace` raises `TypeError`, not `JSONDecodeError` — the implementation must catch both (see Step 3).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.agent'`

- [ ] **Step 3: Implement agent.py**

`src/agent_gieldowy/agent.py`:

```python
"""The agent: one Claude API call, persona in system, structured prediction out.

Model: claude-opus-5-5 by default, overridable via AGENT_GIELDOWY_MODEL.
Structured output via output_config.format (never the deprecated output_format,
never assistant prefill). Invalid or refused responses are retried once, then
reported — an invalid prediction is never silently persisted.
"""

import json
import math
import os
import time
from datetime import datetime, timezone

import anthropic

PREDICTION_SCHEMA = {
    "type": "object",
    "properties": {
        "horizon": {"type": "string", "const": "1M"},
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "direction": {"type": "string", "enum": ["up", "down", "sideways"]},
                    "range_pct": {
                        "type": "object",
                        "properties": {"min": {"type": "number"}, "max": {"type": "number"}},
                        "required": ["min", "max"],
                        "additionalProperties": False,
                    },
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["symbol", "direction", "range_pct", "confidence", "rationale", "risks"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
        "analysis": {"type": "string"},
    },
    "required": ["horizon", "predictions", "summary", "analysis"],
    "additionalProperties": False,
}


class AgentError(Exception):
    """User-facing agent failure (Polish message)."""


def default_model() -> str:
    return os.environ.get("AGENT_GIELDOWY_MODEL", "claude-opus-5-5")


def fmt(value, pct: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if pct:
        return f"{value:.1%}"
    return f"{value:.2f}"


def build_signals_table(signals_by_symbol: dict) -> str:
    lines = []
    for symbol, s in signals_by_symbol.items():
        lines.append(
            f"{symbol}: 1M {fmt(s['return_1m'], pct=True)}, 3M {fmt(s['return_3m'], pct=True)}, "
            f"12M {fmt(s['return_12m'], pct=True)}, momentum6M {fmt(s['momentum_6m'], pct=True)}, "
            f"zmienność roczna {fmt(s['annualized_volatility'], pct=True)}, RSI14 {fmt(s['rsi14'])}, "
            f"SMA50 {fmt(s['sma50'])}, SMA200 {fmt(s['sma200'])}, "
            f"maxDD {fmt(s['max_drawdown'], pct=True)}, "
            f"SMA50>SMA200 {s['sma50_above_sma200']}, "
            f"goldenCross {s['golden_cross_recent']}, deathCross {s['death_cross_recent']}"
        )
    return "\n".join(lines)


def build_user_message(signals_table: str, news_items: list, digest: dict, watchlist_symbols: list) -> str:
    news = "\n".join(f"- {n['title']} ({n['published']})" for n in news_items) or "- (brak)"
    recent = json.dumps(digest["recent"], ensure_ascii=False, indent=2)
    older = json.dumps(digest["older"], ensure_ascii=False, indent=2)
    symbols = ", ".join(watchlist_symbols)
    return (
        f"DANE RYNKOWE (sygnały techniczne, 12 miesięcy):\n{signals_table}\n\n"
        f"NAJNOWSZE NAGŁÓWKI:\n{news}\n\n"
        f"TWÓJ DZIENNIK (przeszłość) — liczba wpisów: {digest['total_entries']}:\n"
        f"Ostatnie wpisy (pełne):\n{recent}\n"
        f"Starsze wpisy (skrót):\n{older}\n\n"
        f"ZADANIE: Oceń perspektywy i prognozuj zmianę kursu każdego instrumentu "
        f"na 1 miesiąc: {symbols}. Dla każdego podaj kierunek (up/down/sideways; "
        f"sideways = oczekiwana zmiana w przedziale ±2%), przedział zmiany % "
        f"(range_pct: min/max), pewność 0-100, uzasadnienie i ryzyka. "
        f"Uwzględnij swoją historię i skłonności z dziennika."
    )


def validate_prediction(prediction: dict, watchlist_symbols: list) -> list:
    errors = []
    if prediction.get("horizon") != "1M":
        errors.append("horizon musi być '1M'")
    predicted = {p["symbol"] for p in prediction.get("predictions", [])}
    expected = set(watchlist_symbols)
    missing = expected - predicted
    unknown = predicted - expected
    if missing:
        errors.append(f"brak prognoz dla: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"nieznane symbole: {', '.join(sorted(unknown))}")
    for p in prediction.get("predictions", []):
        if p["range_pct"]["min"] > p["range_pct"]["max"]:
            errors.append(f"{p['symbol']}: range_pct min > max")
        if not 0 <= p["confidence"] <= 100:
            errors.append(f"{p['symbol']}: confidence poza 0-100")
    return errors


def analyze(persona_prompt: str, user_message: str, watchlist_symbols: list, client=None, model=None) -> dict:
    """Validated prediction dict with generated_at; retries once on any failure."""
    client = client or anthropic.Anthropic()
    model = model or default_model()
    last_error = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=16000,
                system=persona_prompt,
                output_config={"format": {"type": "json_schema", "schema": PREDICTION_SCHEMA}},
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.RateLimitError as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
            continue
        except anthropic.APIConnectionError as exc:
            raise AgentError(f"brak połączenia z API: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise AgentError(
                "brak danych uwierzytelniających Claude API — uruchom `ant auth login` "
                "albo ustaw zmienną ANTHROPIC_API_KEY"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AgentError(f"błąd API ({exc.status_code}): {exc.message}") from exc
        try:
            text = "".join(block.text for block in response.content if block.type == "text")
            prediction = json.loads(text)
        except (AttributeError, TypeError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        errors = validate_prediction(prediction, watchlist_symbols)
        if not errors:
            prediction["generated_at"] = datetime.now(timezone.utc).isoformat()
            return prediction
        last_error = AgentError("; ".join(errors))
    raise AgentError(f"prognoza niepoprawna po ponowieniu: {last_error}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_agent.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5 (optional, manual): live smoke of one analyze**

Only if you have Claude API credentials (`ant auth status` reports an active profile, or `ANTHROPIC_API_KEY` is set). Run from the project dir:

```bash
.venv/Scripts/python -c "from agent_gieldowy.agent import analyze; import json; print(json.dumps(analyze('Jesteś ostrożnym analitykiem.', 'Prognozuj PKO.WA na 1 miesiąc.', ['PKO.WA']), ensure_ascii=False, indent=2)[:500])"
```

Expected: a valid prediction JSON (costs a few cents). If credentials are missing, note it and skip — the mock-tested path already covers the contract.

- [ ] **Step 6: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/agent.py projects/agent-gieldowy/tests/test_agent.py
git commit -m "feat(agent-gieldowy): add Claude API agent with structured prediction and validation

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: evaluate — scoring past predictions + reflection

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/evaluate.py`
- Test: `projects/agent-gieldowy/tests/test_evaluate.py`

**Interfaces:**
- Consumes: `journal.read_entries` / `journal.update_entry`, `agent.default_model` / `agent.AgentError`, `config.all_symbols`, CSVs written by the collector (`data/<symbol>.csv`)
- Produces:
  - `evaluate.score_direction(pred_dir: str, actual_pct: float) -> bool` — up = `> 0`, down = `< 0`, sideways = `|actual| ≤ 2.0`.
  - `evaluate.score_range(range_pct: dict, actual_pct: float) -> bool` — `min ≤ actual ≤ max`.
  - `evaluate.score_entry(entry: dict, actual_changes: dict) -> dict` — per symbol `{"scored", "actual_pct", "direction_hit", "range_hit"}`; unscored when no actual data.
  - `evaluate.find_due_entries(entries: list, min_age_days: int = 30) -> list[dict]` — entries with `outcomes is None` and `created_at` older than the cutoff.
  - `evaluate.compute_actual_changes(watchlist: dict, since_date, data_dir) -> dict[str, float]` — pct change (0–100 scale) from the first close at/after `since_date` to the latest close, per symbol with data.
  - `evaluate.reflect(prediction: dict, outcomes: dict, client, model, persona_prompt: str) -> str` — 1–2 sentence Polish reflection (free text, max_tokens=1000).
  - `evaluate.evaluate(entries_path, data_dir, watchlist, client=None, model=None, persona_prompt="") -> int` — processes due entries, writes `outcomes` (+ `reflection` when the LLM call succeeds), returns the number of processed entries. Idempotent. Consumed by cli.py (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/test_evaluate.py`:

```python
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from agent_gieldowy.evaluate import (
    compute_actual_changes,
    evaluate,
    find_due_entries,
    score_direction,
    score_entry,
    score_range,
)
from agent_gieldowy.journal import append_entry, read_entries
from conftest import bdate_range


def iso_days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def entry(age_days=40, symbols=("PKO.WA",)):
    prediction = {
        "horizon": "1M",
        "generated_at": iso_days_ago(age_days),
        "predictions": [
            {"symbol": s, "direction": "up", "range_pct": {"min": -5.0, "max": 8.0}}
            for s in symbols
        ],
        "summary": "s",
        "analysis": "a",
    }
    return {"prediction": prediction}


class FakeMessages:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


class FakeClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)


def test_score_direction_rules():
    assert score_direction("up", 5.0) is True
    assert score_direction("up", -1.0) is False
    assert score_direction("down", -5.0) is True
    assert score_direction("down", 1.0) is False
    assert score_direction("sideways", 1.9) is True
    assert score_direction("sideways", -2.0) is True
    assert score_direction("sideways", 2.1) is False


def test_score_range():
    assert score_range({"min": -5.0, "max": 8.0}, 0.0) is True
    assert score_range({"min": -5.0, "max": 8.0}, 8.0) is True
    assert score_range({"min": -5.0, "max": 8.0}, 8.1) is False


def test_score_entry_marks_missing_actual_as_unscored():
    scored = score_entry(entry(), {"PKO.WA": 3.0})
    assert scored["PKO.WA"]["scored"] is True
    assert scored["PKO.WA"]["direction_hit"] is True
    unscored = score_entry(entry(), {})
    assert unscored["PKO.WA"]["scored"] is False


def test_find_due_entries_filters_by_age_and_state():
    due = entry(age_days=40)
    fresh = entry(age_days=10)
    done = entry(age_days=40)
    done["outcomes"] = {}
    assert find_due_entries([due, fresh, done]) == [due]


def test_compute_actual_changes_reads_csv(tmp_path, watchlist):
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    since = dates[30].strftime("%Y-%m-%d")
    changes = compute_actual_changes(watchlist, since, tmp_path)
    # 100+59 vs 100+30 → +29/130 ≈ +22.3%
    assert changes["PKO.WA"] == pytest.approx(29 / 130 * 100, rel=0.01)


def test_evaluate_processes_due_entries_and_writes_outcomes(tmp_path, watchlist):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    client = FakeClient("Za dużo optymizmu — fundamenty były słabsze.")
    processed = evaluate(entries_path, tmp_path, watchlist, client=client, persona_prompt="p")
    assert processed == 1
    stored = read_entries(entries_path)[0]
    assert stored["outcomes"]["PKO.WA"]["scored"] is True
    assert stored["reflection"] == "Za dużo optymizmu — fundamenty były słabsze."


def test_evaluate_idempotent(tmp_path, watchlist):
    # Review Focus #5: a second run scores nothing new
    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    client = FakeClient("x")
    assert evaluate(entries_path, tmp_path, watchlist, client=client, persona_prompt="p") == 1
    assert evaluate(entries_path, tmp_path, watchlist, client=client, persona_prompt="p") == 0
    assert len(client.messages.calls) == 1  # no second reflection call


def test_evaluate_keeps_outcomes_when_reflection_fails(tmp_path, watchlist):
    from agent_gieldowy.agent import AgentError

    class BoomMessages:
        def create(self, **kwargs):
            raise AgentError("brak połączenia z API: x")

    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    processed = evaluate(
        entries_path, tmp_path, watchlist,
        client=SimpleNamespace(messages=BoomMessages()), persona_prompt="p",
    )
    assert processed == 1
    stored = read_entries(entries_path)[0]
    assert stored["outcomes"]["PKO.WA"]["scored"] is True
    assert stored["reflection"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_evaluate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.evaluate'`

- [ ] **Step 3: Implement evaluate.py**

`src/agent_gieldowy/evaluate.py`:

```python
"""Score predictions older than 30 days against reality; let the agent reflect."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from agent_gieldowy.agent import AgentError, default_model
from agent_gieldowy.config import all_symbols
from agent_gieldowy.journal import read_entries, update_entry


def score_direction(pred_dir: str, actual_pct: float) -> bool:
    if pred_dir == "sideways":
        return abs(actual_pct) <= 2.0
    if pred_dir == "up":
        return actual_pct > 0
    return actual_pct < 0


def score_range(range_pct: dict, actual_pct: float) -> bool:
    return range_pct["min"] <= actual_pct <= range_pct["max"]


def score_entry(entry: dict, actual_changes: dict) -> dict:
    per_symbol = {}
    for p in entry["prediction"]["predictions"]:
        actual = actual_changes.get(p["symbol"])
        if actual is None:
            per_symbol[p["symbol"]] = {"scored": False}
            continue
        per_symbol[p["symbol"]] = {
            "scored": True,
            "actual_pct": round(actual, 2),
            "direction_hit": score_direction(p["direction"], actual),
            "range_hit": score_range(p["range_pct"], actual),
        }
    return per_symbol


def find_due_entries(entries: list, min_age_days: int = 30) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    due = []
    for e in entries:
        if e.get("outcomes") is not None:
            continue
        try:
            created = datetime.fromisoformat(e["created_at"])
        except (KeyError, ValueError):
            continue
        if created <= cutoff:
            due.append(e)
    return due


def compute_actual_changes(watchlist: dict, since_date, data_dir) -> dict:
    """Pct change (0–100 scale) per symbol from first close at/after since_date to latest."""
    since_iso = since_date.strftime("%Y-%m-%d") if hasattr(since_date, "strftime") else since_date
    changes = {}
    for item in all_symbols(watchlist):
        path = Path(data_dir) / f"{item['symbol']}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df = df[df["date"] >= since_iso]
        if len(df) < 2:
            continue
        base = float(df["close"].iloc[0])
        if base == 0:
            continue
        changes[item["symbol"]] = float(df["close"].iloc[-1] / base - 1) * 100
    return changes


def reflect(prediction: dict, outcomes: dict, client, model, persona_prompt: str) -> str:
    import anthropic

    client = client or anthropic.Anthropic()
    model = model or default_model()
    user_message = (
        f"Twoja prognoza z {prediction['generated_at']}:\n"
        f"{prediction['summary']}\n\n"
        f"Rzeczywiste wyniki (zmiana % i trafienia):\n{outcomes}\n\n"
        "Napisz 1-2 zdania refleksji w pierwszej osobie: co przegapiłeś, co zadziałało, "
        "czego to Cię uczy na przyszłość. Odpowiadaj jako Ty, zgodnie ze swoją personą."
    )
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=persona_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def evaluate(entries_path, data_dir, watchlist, client=None, model=None, persona_prompt: str = "") -> int:
    """Score all due entries, append reflections, return entries processed."""
    processed = 0
    for entry in find_due_entries(read_entries(entries_path)):
        since = datetime.fromisoformat(entry["prediction"]["generated_at"])
        actual = compute_actual_changes(watchlist, since, data_dir)
        outcomes = score_entry(entry, actual)
        patch = {"outcomes": outcomes}
        try:
            patch["reflection"] = reflect(entry["prediction"], outcomes, client, model, persona_prompt)
        except (AgentError, Exception) as exc:  # noqa: BLE001 — reflection is best-effort
            patch["reflection"] = None
        update_entry(entries_path, entry["id"], patch)
        processed += 1
    return processed
```

Note for the implementer: the bare `Exception` in the last `except` is deliberate — a failed reflection must never lose the scored outcomes (pinned by `test_evaluate_keeps_outcomes_when_reflection_fails`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_evaluate.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/evaluate.py projects/agent-gieldowy/tests/test_evaluate.py
git commit -m "feat(agent-gieldowy): add prediction scoring and agent reflection

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: report — plotly HTML

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/report.py`
- Test: `projects/agent-gieldowy/tests/test_report.py`

**Interfaces:**
- Consumes: `config.all_symbols`, `signals.compute_signals`, `journal.read_entries`, `persona.load_persona`, CSVs + `data/news.json`
- Produces: `report.render_report(watchlist: dict, data_dir, persona_path, entries_path, out_path) -> str` — writes a self-contained HTML file (first plotly figure embeds the JS library; later ones don't), returns the output path as a string. Sections: header with the verbatim disclaimer, per-instrument chart + signal table (with explicit "Brak danych." for missing files), agent section (persona card + prediction table + analysis; "Brak prognozy" placeholder when no journal entry has a prediction), journal history with the hit counter (`X/Y`), news list. Consumed by cli.py (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:

```python
import json

import pandas as pd
import pytest

from agent_gieldowy.journal import append_entry
from agent_gieldowy.report import render_report
from conftest import bdate_range


PERSONA = """\
name: "Andrzej Malinowski"
age: 55
city: "Kraków"
profession: "analityk TFI"
social_position: "wyższa klasa średnia"
education: "mgr"
life_history: []
biases:
  - "awersja do ryzyka"
temperament: "spokojny"
style: "konkretny"
"""


def prediction():
    return {
        "horizon": "1M",
        "generated_at": "2026-10-01T12:00:00+00:00",
        "predictions": [
            {"symbol": "PKO.WA", "direction": "up", "range_pct": {"min": -5, "max": 8},
             "confidence": 65, "rationale": "r", "risks": ["x"]}
        ],
        "summary": "Ostrożnie pozytywnie.",
        "analysis": "Pełna analiza.",
    }


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    dates = bdate_range(300)
    closes = [100.0 + i for i in range(300)]
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        d / "PKO.WA.csv", index=False
    )
    (d / "news.json").write_text(
        json.dumps([{"title": "Nagłówek testowy", "published": "2026-10-26", "link": "https://x/1"}]),
        encoding="utf-8",
    )
    return d


@pytest.fixture
def persona_path(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA, encoding="utf-8")
    return p


def test_report_contains_disclaimer_chart_signals_and_news(data_dir, persona_path, tmp_path, watchlist):
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, persona_path, tmp_path / "journal" / "entries.jsonl", out)
    html = out.read_text(encoding="utf-8")
    assert "narzędzie szkoleniowe, nie porada inwestycyjna" in html
    assert "PKO.WA" in html
    assert "plotly" in html.lower()  # embedded JS library
    assert "Nagłówek testowy" in html


def test_report_empty_state_no_crash(data_dir, persona_path, tmp_path, watchlist):
    # Review Focus #4: empty journal + a missing symbol file render placeholders
    import os

    os.remove(data_dir / "PKO.WA.csv")
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, persona_path, tmp_path / "journal" / "entries.jsonl", out)
    html = out.read_text(encoding="utf-8")
    assert "Brak danych." in html
    assert "Brak prognozy" in html
    assert "Dziennik pusty." in html


def test_report_renders_agent_section_and_hit_counter(data_dir, persona_path, tmp_path, watchlist):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    stored = append_entry(entries_path, {"prediction": prediction()})
    stored["outcomes"] = {"PKO.WA": {"scored": True, "actual_pct": 3.0, "direction_hit": True, "range_hit": True}}
    stored["reflection"] = "Refleksja testowa."
    lines = [json.dumps(stored, ensure_ascii=False)]
    entries_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, persona_path, entries_path, out)
    html = out.read_text(encoding="utf-8")
    assert "Andrzej Malinowski" in html
    assert "awersja do ryzyka" in html
    assert "Pełna analiza." in html
    assert "Refleksja testowa." in html
    assert "1/1" in html  # hit counter
    assert "Ryzyka" in html  # risks section (§11)
    assert "x" in html  # the predicted risk is rendered
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.report'`

- [ ] **Step 3: Implement report.py**

`src/agent_gieldowy/report.py`:

```python
"""Self-contained plotly HTML report: data, signals, agent, journal, news."""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from agent_gieldowy.agent import fmt
from agent_gieldowy.config import all_symbols
from agent_gieldowy.journal import read_entries
from agent_gieldowy.persona import load_persona
from agent_gieldowy.signals import compute_signals

DISCLAIMER = "narzędzie szkoleniowe, nie porada inwestycyjna"


def _price_figure(df: pd.DataFrame, symbol: str) -> go.Figure:
    dates = pd.to_datetime(df["date"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=df["close"], mode="lines", name=symbol))
    for window in (50, 200):
        if len(df) >= window:
            sma = df["close"].rolling(window).mean()
            fig.add_trace(go.Scatter(x=dates, y=sma, mode="lines", name=f"SMA{window}"))
    fig.update_layout(title=symbol, xaxis_title="Data", yaxis_title="PLN", height=320)
    return fig


def _signals_table(signals: dict) -> str:
    rows = [
        ("Zwrot 1M", fmt(signals["return_1m"], pct=True)),
        ("Zwrot 3M", fmt(signals["return_3m"], pct=True)),
        ("Zwrot 12M", fmt(signals["return_12m"], pct=True)),
        ("Momentum 6M", fmt(signals["momentum_6m"], pct=True)),
        ("Zmienność (roczna)", fmt(signals["annualized_volatility"], pct=True)),
        ("RSI14", fmt(signals["rsi14"])),
        ("SMA50", fmt(signals["sma50"])),
        ("SMA200", fmt(signals["sma200"])),
        ("Max drawdown", fmt(signals["max_drawdown"], pct=True)),
    ]
    body = "".join(f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows)
    return f"<table border='1' cellpadding='4'><tr><th>Wskaźnik</th><th>Wartość</th></tr>{body}</table>"


def _prediction_table(prediction: dict) -> str:
    rows = []
    for p in prediction["predictions"]:
        rows.append(
            f"<tr><td>{p['symbol']}</td><td>{p['direction']}</td>"
            f"<td>{p['range_pct']['min']}% do {p['range_pct']['max']}%</td>"
            f"<td>{p['confidence']}</td><td>{p['rationale']}</td></tr>"
        )
    body = "".join(rows)
    return (
        "<table border='1' cellpadding='4'><tr><th>Symbol</th><th>Kierunek</th>"
        f"<th>Przedział</th><th>Pewność</th><th>Uzasadnienie</th></tr>{body}</table>"
    )


def _hit_counter(entries: list) -> str:
    hits = total = 0
    for e in entries:
        for outcome in (e.get("outcomes") or {}).values():
            if outcome.get("scored"):
                total += 1
                hits += bool(outcome.get("direction_hit"))
    return f"{hits}/{total}"


def _journal_entry_html(entry: dict) -> str:
    pred = entry.get("prediction") or {}
    summary = pred.get("summary", "—")
    outcomes = entry.get("outcomes") or {}
    marks = " ".join(
        f"{sym}: {'✓' if o.get('direction_hit') else '✗' if o.get('scored') else '?'}"
        for sym, o in outcomes.items()
    )
    reflection = f"<p><em>{entry['reflection']}</em></p>" if entry.get("reflection") else ""
    return (
        f"<li>{entry['created_at'][:10]} — {summary} [{marks}]</li>{reflection}"
    )


def render_report(watchlist: dict, data_dir, persona_path, entries_path, out_path) -> str:
    data_dir = Path(data_dir)
    entries = read_entries(entries_path)
    latest = entries[-1] if entries else None
    parts = [
        "<html><head><meta charset='utf-8'><title>Raport agenta giełdowego</title></head><body>",
        "<h1>Raport agenta giełdowego</h1>",
        "<p>Horyzont prognozy: 1 miesiąc.</p>",
        f"<p><strong>Uwaga: {DISCLAIMER}.</strong></p>",
    ]
    first_figure = True
    for item in all_symbols(watchlist):
        symbol = item["symbol"]
        path = data_dir / f"{symbol}.csv"
        parts.append(f"<h2>{symbol}</h2>")
        if not path.exists():
            parts.append("<p>Brak danych.</p>")
            continue
        df = pd.read_csv(path)
        if len(df) < 2:
            parts.append("<p>Brak danych.</p>")
            continue
        fig = _price_figure(df, symbol)
        parts.append(fig.to_html(full_html=False, include_plotlyjs=first_figure))
        first_figure = False
        parts.append(_signals_table(compute_signals(df)))
    parts.append("<h2>Analiza agenta</h2>")
    if latest and latest.get("prediction"):
        persona = load_persona(persona_path)
        parts.append(
            f"<p><strong>{persona['name']}</strong> — {persona['profession']}, "
            f"{persona['city']}. Skłonności: {', '.join(persona['biases'])}.</p>"
        )
        parts.append(_prediction_table(latest["prediction"]))
        parts.append("<h3>Ryzyka</h3><ul>")
        for p in latest["prediction"]["predictions"]:
            risks = "".join(f"<li>{r}</li>" for r in p.get("risks", [])) or "<li>—</li>"
            parts.append(f"<li><strong>{p['symbol']}:</strong><ul>{risks}</ul></li>")
        parts.append("</ul>")
        parts.append(f"<p>{latest['prediction']['analysis']}</p>")
    else:
        parts.append("<p>Brak prognozy — uruchom `agent-gieldowy analyze`.</p>")
    parts.append("<h2>Dziennik agenta</h2>")
    if entries:
        parts.append(f"<p>Trafność kierunku (historyczna): {_hit_counter(entries)}</p><ul>")
        for entry in entries[-5:]:
            parts.append(_journal_entry_html(entry))
        parts.append("</ul>")
    else:
        parts.append("<p>Dziennik pusty.</p>")
    news_path = data_dir / "news.json"
    if news_path.exists():
        parts.append("<h2>Wiadomości</h2><ul>")
        for n in json.loads(news_path.read_text(encoding="utf-8")):
            parts.append(f"<li><a href='{n['link']}'>{n['title']}</a> — {n['published']}</li>")
        parts.append("</ul>")
    parts.append("</body></html>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return str(out_path)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/report.py projects/agent-gieldowy/tests/test_report.py
git commit -m "feat(agent-gieldowy): add plotly HTML report

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 10: cli — subcommands + live smoke tests

**Files:**
- Create: `projects/agent-gieldowy/src/agent_gieldowy/cli.py`
- Test: `projects/agent-gieldowy/tests/test_cli.py`, `projects/agent-gieldowy/tests/test_live.py`

**Interfaces:**
- Consumes: everything above
- Produces: `cli.main(argv=None) -> int` — argparse with subcommands `collect`, `analyze`, `evaluate`, `report`, `run`; returns 0 on success, 1 on `CollectorError`/`AgentError` (message to stderr); `report` opens the file with `webbrowser.open(path.as_uri())`. Entry point `agent-gieldowy` (declared in Task 1's pyproject).

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
from pathlib import Path

import pytest

import agent_gieldowy.cli as cli


@pytest.fixture
def project_files(tmp_path, monkeypatch):
    """Point cli.PROJECT_DIR at a temp tree with watchlist/persona files."""
    (tmp_path / "watchlist.yaml").write_text(
        "stocks:\n  - PKO.WA\nindices: []\nfunds: []\n", encoding="utf-8"
    )
    (tmp_path / "persona.yaml").write_text("name: X\nage: 1\ncity: C\nprofession: P\n"
                                           "social_position: S\neducation: E\nlife_history: []\n"
                                           "biases: []\ntemperament: T\nstyle: S\n", encoding="utf-8")
    monkeypatch.setattr(cli, "PROJECT_DIR", Path(tmp_path))
    return tmp_path


def test_collect_calls_collector(project_files, monkeypatch):
    calls = {}

    def fake_collect(watchlist, data_dir, session=None):
        calls["watchlist"] = watchlist
        calls["data_dir"] = str(data_dir)
        return {"PKO.WA": {"status": "ok", "rows": 1, "appended": 1}}

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 0
    assert calls["watchlist"]["stocks"] == ["PKO.WA"]
    assert calls["data_dir"].endswith("data")


def test_collect_partial_failure_warns_but_exits_0(project_files, monkeypatch, capsys):
    # Review Focus #1: one dead symbol must not halt the pipeline
    def fake_collect(watchlist, data_dir, session=None):
        return {
            "PKO.WA": {"status": "error", "error": "Yahoo has no data for PKO.WA"},
        }

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 0
    assert "Yahoo has no data for PKO.WA" in capsys.readouterr().err


def test_collect_all_failed_exits_1(project_files, monkeypatch, capsys):
    def fake_collect(watchlist, data_dir, session=None):
        return {"PKO.WA": {"status": "error", "error": "Yahoo has no data for PKO.WA"}}

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 1
    assert "Zebrano: 0" in capsys.readouterr().out


def test_analyze_runs_agent_and_appends_journal_entry(project_files, monkeypatch):
    monkeypatch.setattr(cli, "read_entries", lambda p: [])
    monkeypatch.setattr(cli, "build_digest", lambda entries: {"recent": [], "older": [], "total_entries": 0})
    monkeypatch.setattr(cli, "compute_signals", lambda df: {"return_1m": 0.01})
    monkeypatch.setattr(cli, "build_signals_table", lambda s: "PKO.WA: 1M 1.0%")
    monkeypatch.setattr(cli, "load_persona", lambda p: {"name": "X"})
    monkeypatch.setattr(cli, "render_system_prompt", lambda persona: "prompt")
    news_items = [{"title": "t", "published": "d", "link": "l"}]
    monkeypatch.setattr(cli, "load_news_items", lambda p: news_items)
    appended = {}

    def fake_analyze(persona_prompt, user_message, watchlist_symbols, client=None, model=None):
        return {"horizon": "1M", "predictions": [], "summary": "s", "analysis": "a",
                "generated_at": "2026-10-26T00:00:00+00:00"}

    def fake_append(entries_path, entry):
        appended["entry"] = entry
        return {**entry, "id": "x", "created_at": "2026-10-26T00:00:00+00:00"}

    monkeypatch.setattr(cli, "analyze", fake_analyze)
    monkeypatch.setattr(cli, "append_entry", fake_append)
    assert cli.main(["analyze"]) == 0
    assert appended["entry"]["prediction"]["horizon"] == "1M"


def test_analyze_without_data_files_exits_1(project_files, monkeypatch, capsys):
    monkeypatch.setattr(cli, "read_entries", lambda p: [])
    monkeypatch.setattr(cli, "load_news_items", lambda p: [])
    assert cli.main(["analyze"]) == 1
    assert "danych" in capsys.readouterr().err.lower()


def test_report_writes_file_and_opens_browser(project_files, monkeypatch):
    monkeypatch.setattr(cli, "render_report", lambda *a, **k: str(project_files / "report.html"))
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url))
    assert cli.main(["report"]) == 0
    assert opened and opened[0].startswith("file://")


def test_evaluate_delegates(project_files, monkeypatch):
    calls = {}

    def fake_evaluate(entries_path, data_dir, watchlist, client=None, model=None, persona_prompt=""):
        calls["called"] = True
        return 2

    monkeypatch.setattr(cli, "evaluate", fake_evaluate)
    assert cli.main(["evaluate"]) == 0
    assert calls["called"] is True


def test_run_is_collect_then_analyze_then_report(project_files, monkeypatch):
    order = []
    monkeypatch.setattr(cli, "cmd_collect", lambda args: order.append("collect") or 0)
    monkeypatch.setattr(cli, "cmd_analyze", lambda args: order.append("analyze") or 0)
    monkeypatch.setattr(cli, "cmd_report", lambda args: order.append("report") or 0)
    assert cli.main(["run"]) == 0
    assert order == ["collect", "analyze", "report"]


def test_run_stops_when_collect_fails(project_files, monkeypatch):
    order = []
    monkeypatch.setattr(cli, "cmd_collect", lambda args: order.append("collect") or 1)
    monkeypatch.setattr(cli, "cmd_analyze", lambda args: order.append("analyze") or 0)
    monkeypatch.setattr(cli, "cmd_report", lambda args: order.append("report") or 0)
    assert cli.main(["run"]) == 1
    assert order == ["collect"]
```

`tests/test_live.py` (excluded by default via the `live` marker; run manually):

```python
"""Live smoke — manual only: `pytest -m live`. Hits real sources; no API key needed."""

import pandas as pd
import pytest

from agent_gieldowy.collector import fetch_quotes
from agent_gieldowy.report import render_report

pytestmark = pytest.mark.live


def test_live_collect_one_symbol_and_render(tmp_path):
    df = fetch_quotes("PKO.WA", "stock")
    assert len(df) > 200
    assert df["close"].iloc[-1] > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_gieldowy.cli'`

- [ ] **Step 3: Implement cli.py**

`src/agent_gieldowy/cli.py`:

```python
"""argparse CLI: collect / analyze / evaluate / report / run."""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd

from agent_gieldowy.agent import AgentError, analyze, build_signals_table, build_user_message
from agent_gieldowy.collector import CollectorError, collect
from agent_gieldowy.config import all_symbols, load_watchlist
from agent_gieldowy.evaluate import evaluate
from agent_gieldowy.journal import append_entry, build_digest, read_entries
from agent_gieldowy.news import NEWS_FEEDS, fetch_news, save_news
from agent_gieldowy.persona import load_persona, render_system_prompt
from agent_gieldowy.report import render_report
from agent_gieldowy.signals import compute_signals

PROJECT_DIR = Path(__file__).resolve().parent.parent


def _data_dir() -> Path:
    return PROJECT_DIR / "data"


def _entries_path() -> Path:
    return PROJECT_DIR / "journal" / "entries.jsonl"


def _watchlist_path() -> Path:
    return PROJECT_DIR / "watchlist.yaml"


def _persona_path() -> Path:
    return PROJECT_DIR / "persona.yaml"


def _load_news_items(path: Path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def cmd_collect(args) -> int:
    watchlist = load_watchlist(_watchlist_path())
    results = collect(watchlist, _data_dir())
    items = fetch_news(NEWS_FEEDS)
    save_news(items, _data_dir())
    failed = [s for s, r in results.items() if r["status"] == "error"]
    for symbol in failed:
        print(f"Uwaga: {symbol}: {results[symbol]['error']}", file=sys.stderr)
    ok = [s for s, r in results.items() if r["status"] == "ok"]
    print(f"Zebrano: {len(ok)} instrumentów, newsy: {len(items)} nagłówków.")
    # Partial failure is fine (spec §9: one dead source must not kill collect);
    # exit 1 only when nothing at all was collected.
    return 1 if not ok else 0


def _signals_by_symbol(watchlist: dict) -> dict:
    signals = {}
    for item in all_symbols(watchlist):
        path = _data_dir() / f"{item['symbol']}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        if len(df) >= 2:
            signals[item["symbol"]] = compute_signals(df)
    return signals


def cmd_analyze(args) -> int:
    watchlist = load_watchlist(_watchlist_path())
    symbols = [item["symbol"] for item in all_symbols(watchlist)]
    signals = _signals_by_symbol(watchlist)
    if not signals:
        print("Brak danych — najpierw uruchom `agent-gieldowy collect`.", file=sys.stderr)
        return 1
    entries = read_entries(_entries_path())
    digest = build_digest(entries)
    news_items = _load_news_items(_data_dir() / "news.json")
    persona = load_persona(_persona_path())
    user_message = build_user_message(
        build_signals_table(signals), news_items, digest, symbols
    )
    try:
        prediction = analyze(render_system_prompt(persona), user_message, symbols)
    except AgentError as exc:
        print(f"Błąd agenta: {exc}", file=sys.stderr)
        return 1
    append_entry(_entries_path(), {"prediction": prediction})
    print(f"Prognoza zapisana w dzienniku ({prediction['summary']})")
    return 0


def cmd_evaluate(args) -> int:
    persona = load_persona(_persona_path())
    processed = evaluate(
        _entries_path(), _data_dir(), load_watchlist(_watchlist_path()),
        persona_prompt=render_system_prompt(persona),
    )
    print(f"Oceniono wpisów: {processed}.")
    return 0


def cmd_report(args) -> int:
    out = PROJECT_DIR / "report.html"
    path = render_report(
        load_watchlist(_watchlist_path()), _data_dir(), _persona_path(), _entries_path(), out
    )
    print(f"Raport zapisany: {path}")
    webbrowser.open(Path(path).as_uri())
    return 0


def cmd_run(args) -> int:
    for cmd in (cmd_collect, cmd_analyze, cmd_report):
        code = cmd(args)
        if code != 0:
            return code
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="agent-gieldowy", description="Polski pipeline rynkowy + agent z osobowością.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect", help="pobierz dane i newsy")
    sub.add_parser("analyze", help="sygnały + analiza agenta (zapis do dziennika)")
    sub.add_parser("evaluate", help="oceń prognozy starsze niż 30 dni")
    sub.add_parser("report", help="wygeneruj report.html i otwórz w przeglądarce")
    sub.add_parser("run", help="collect → analyze → report")
    args = parser.parse_args(argv)
    handlers = {
        "collect": cmd_collect,
        "analyze": cmd_analyze,
        "evaluate": cmd_evaluate,
        "report": cmd_report,
        "run": cmd_run,
    }
    try:
        return handlers[args.command](args)
    except (CollectorError, AgentError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: PASS (8 tests)

Run: `.venv/Scripts/python -m pytest` — the full suite (live tests excluded by the `addopts` marker filter).
Expected: PASS with **zero failures** (count: 7 signals + 7 collector + 4 news + 5 journal + 2 persona + 11 agent + 9 evaluate + 3 report + 9 cli = 57; live tests are deselected by `-m 'not live'`, not counted).

- [ ] **Step 5: Verify the entry point works end to end with mocked-free commands**

Run: `.venv/Scripts/python -m agent_gieldowy.cli collect`
Expected: prints collection results (real network call to Yahoo/bankier — allowed here, this is the actual tool), exit code 0 or per-symbol warnings to stderr. Then:

Run: `.venv/Scripts/python -m agent_gieldowy.cli report`
Expected: `report.html` created in the project dir and opened in the browser.

- [ ] **Step 6: Commit**

```bash
git add projects/agent-gieldowy/src/agent_gieldowy/cli.py projects/agent-gieldowy/tests/test_cli.py projects/agent-gieldowy/tests/test_live.py
git commit -m "feat(agent-gieldowy): add argparse CLI with run pipeline

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Final Verification (after Task 10)

Run the whole suite once more and check the tool manually:

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m agent_gieldowy.cli run   # needs Claude API credentials for analyze
.venv/Scripts/python -m pytest -m live           # optional; real network only
```

Expected: full suite green (live excluded); `run` collects data, appends a journal entry, and opens the report. If `analyze` fails on missing credentials, `collect` and `report` must still work — that path is exactly what the error handling in Tasks 7 and 10 pins.
