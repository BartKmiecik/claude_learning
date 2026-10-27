# Agent Predykcje Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ten persona-driven LLM agents each predict GPW stock prices (PKO, PZU, PKN) at +1 day/+1 week/+1 month from price history and news; a single-page HTML report shows per-stock average+min–max band charts and per-agent prediction tables, sections sorted by average +1M gain.

**Architecture:** Standalone Python CLI package `projects/agent-predykcje/` (own venv, no imports from `agent-gieldowy`), copy-adapting Project 2's verified data/LLM patterns. `collect` fetches Yahoo daily quotes + bankier.pl RSS news into `data/`; `analyze` runs 30 LLM calls (10 personas × 3 stocks, thread pool of 5), validates each structured prediction, and saves a self-contained snapshot to `predictions/`; `report` renders the sorted plotly HTML report from the snapshot only and opens it in the browser.

**Tech Stack:** Python ≥3.10, pandas, requests, feedparser, pyyaml, plotly, anthropic SDK (model `claude-opus-5-5` default, structured outputs via `output_config.format`), pytest + black (TDD, one commit per task).

**Spec:** `docs/superpowers/specs/2026-10-27-agent-predykcje-design.md` (approved 2026-10-27). Binding mockups: `docs/superpowers/specs/2026-10-27-agent-predykcje-mockups/` (chart B, layout A, sort metric B).

## Global Constraints

- Copy-adapt source of truth for data/LLM patterns: `projects/agent-gieldowy/src/agent_gieldowy/{collector,news,signals,agent,persona}.py` — copy and adapt, never import; the two packages never depend on each other.
- Package: `agent-predykcje`, layout `src/agent_predykcje/`, console script `agent-predykcje = "agent_predykcje.cli:main"`; deps `pandas>=2.0`, `requests>=2.31`, `feedparser>=6.0`, `pyyaml>=6.0`, `plotly>=5.18`, `anthropic>=2.0`; dev `pytest>=8.0`, `black>=24.0`; own venv at `projects/agent-predykcje/.venv`.
- Data sources: Yahoo chart API v8 `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}` (`.WA` symbols, `User-Agent` header, no key) for daily quotes; RSS feeds `https://www.bankier.pl/rss/wiadomosci.xml` + `https://www.money.pl/rss/main.xml` for news. Watchlist `watchlist.yaml`: stocks `PKO.WA`, `PZU.WA`, `PKN.WA`; indices `WIG20.WA`, `WIG.WA`, `MWIG40.WA` (context data for prompts only, never predicted); no funds.
- Model: default `"claude-opus-5-5"`, overridable via env `AGENT_PREDYKCJE_MODEL` or CLI `--model`. Every call: `max_tokens=16000`, `output_config={"format": {"type": "json_schema", "schema": PREDICTION_SCHEMA}, "effort": "medium"}`, `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`, `system=persona_prompt`. One full run = 30 calls (10 personas × 3 stocks).
- Horizons keyed `1d`, `1w`, `1m` — one prediction per horizon per agent, plus a one-line Polish `justification`, all in one call. Sanity bound: every predicted price must be within **50%–150% of the anchor price**, else the response is invalid.
- Snapshot schema (self-contained; `report` reads only this): `{"created_at": ISO, "model": str, "stocks": [{"symbol", "anchor": {"date", "price"} | None, "agents": [{"persona": id, "display_name", "status": "ok"|"error", "error": str|null, "predictions": {"1d","1w","1m"} | null, "justification": str|null}]}]}` saved to `predictions/predictions-YYYYmmdd-HHMMSS.json`.
- Report: Polish copy; disclaimer `narzędzie szkoleniowe, nie porada inwestycyjna` visible at top; sections sorted by average +1M % gain descending (None-gain stocks last); per-section badge `średni zysk {+x,x}%` — green (`#1a7f37`) if gain > 0, red (`#c62828`) if < 0, gray otherwise; band chart = thick average line + gray min–max band over x = `Dziś, +1 dzień, +1 tydzień, +1 miesiąc`; table rows = 10 agents + `Średnia` row, columns `Agent | +1 dzień | +1 tydzień | +1 miesiąc | Uzasadnienie`; failed agent row shows `brak danych`; a stock with no data renders `Brak danych.`; every dynamic string (justification, news, persona text, symbol) HTML-escaped with `html.escape`.
- Style: code comments/docstrings in English, user-facing strings in Polish (Project 2 convention). TDD: write failing test → run (FAIL) → implement → run (PASS) → commit, one commit per task, `git add` only the task's files.

## Review Focus

1. **Missing/broken Claude credentials** — `analyze`/`run` must print the Polish guidance (`ant auth login` or `ANTHROPIC_API_KEY`) and exit 1 without a traceback. Pinned by Task 5 test `test_make_client_credentials_error` and Task 8 test `test_analyze_credentials_error_exit_code`.
2. **One agent call fails mid-run** — the run continues; that agent is saved with `status: "error"`, the report row shows `brak danych`, and averages/band use only successful agents. Pinned by Task 6 test `test_run_analysis_one_agent_error` and Task 7 test `test_render_failed_agent_row_and_averages`.
3. **LLM returns malformed JSON or out-of-range prices** — retried once, then `AgentError`; invalid numbers are never persisted. Pinned by Task 5 tests `test_predict_stock_invalid_json_retries_then_raises` and `test_validate_prediction_out_of_range`.
4. **Run on a day the market was closed** (weekend/holiday) — anchor is the last CSV row's date and price (not today's date); the report header shows that date and gains are computed against it. Pinned by Task 6 test `test_anchor_of_uses_last_row` and Task 7 test `test_render_header_shows_anchor_date`.
5. **HTML in LLM/persona/news text** — escaped in the report, never interpreted as markup. Pinned by Task 7 test `test_render_escapes_html_in_justification`.

---

### Task 1: Project scaffold, watchlist, config

**Files:**
- Create: `projects/agent-predykcje/pyproject.toml`, `projects/agent-predykcje/.gitignore`, `projects/agent-predykcje/watchlist.yaml`, `projects/agent-predykcje/src/agent_predykcje/__init__.py`, `projects/agent-predykcje/src/agent_predykcje/config.py`, `projects/agent-predykcje/tests/__init__.py`, `projects/agent-predykcje/tests/conftest.py`
- Modify: `.claude/settings.json` (black hook covers the new project too)
- Test: `projects/agent-predykcje/tests/test_config.py`

**Interfaces:**
- Produces: `load_watchlist(path) -> dict` (sections `stocks`, `indices`), `all_symbols(watchlist) -> list[dict]` (`{"symbol", "kind"}` — stocks first, then indices), `persona_paths(personas_dir) -> list[Path]` (sorted `*.yaml` stems→paths).

- [ ] **Step 1: Create venv, install package, create project files**

Run:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```
Create `pyproject.toml` — copy `projects/agent-gieldowy/pyproject.toml`, changing `name = "agent-predykcje"`, description to `"Training project: 10 persona-driven LLM agents predicting GPW prices"`, and the script entry to `agent-predykcje = "agent_predykcje.cli:main"`. Create `.gitignore` with `.venv/`, `data/`, `predictions/`, `report/`, `__pycache__/`. Create `watchlist.yaml` (exact contents in Global Constraints). Create `src/agent_predykcje/__init__.py` (empty), `tests/__init__.py` (empty), `tests/conftest.py` (empty).

- [ ] **Step 2: Write the failing tests** — `tests/test_config.py`

```python
import yaml
from agent_predykcje.config import all_symbols, load_watchlist, persona_paths

def test_load_watchlist_reads_stocks_and_indices(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text("stocks:\n  - PKO.WA\n  - PZU.WA\nindices:\n  - WIG.WA\n", encoding="utf-8")
    w = load_watchlist(path)
    assert w["stocks"] == ["PKO.WA", "PZU.WA"]
    assert w["indices"] == ["WIG.WA"]

def test_all_symbols_flattens_in_section_order():
    w = {"stocks": ["PKO.WA"], "indices": ["WIG20.WA", "WIG.WA"]}
    assert all_symbols(w) == [
        {"symbol": "PKO.WA", "kind": "stock"},
        {"symbol": "WIG20.WA", "kind": "index"},
        {"symbol": "WIG.WA", "kind": "index"},
    ]

def test_persona_paths_sorted_yaml(tmp_path):
    (tmp_path / "bear.yaml").write_text("name: X\n", encoding="utf-8")
    (tmp_path / "value.yaml").write_text("name: Y\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore\n", encoding="utf-8")
    paths = persona_paths(tmp_path)
    assert [p.stem for p in paths] == ["bear", "value"]
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.config'`

- [ ] **Step 4: Implement `config.py`**

`load_watchlist(path) -> dict` and `all_symbols(watchlist) -> list[dict]` — copy-adapt from `agent_gieldowy/config.py` (drop the `funds` section from `all_symbols`; kinds `stock`/`index` only). Add `persona_paths(personas_dir) -> list[Path]` returning sorted `Path` objects for `*.yaml` files in `personas_dir`.

- [ ] **Step 5: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Extend the black hook**

In `.claude/settings.json`, replace the hook command with one that runs black in both projects (each with its own venv):
```json
"command": "python -c \"import os, subprocess; [subprocess.run([os.path.join('projects', p, '.venv', 'Scripts', 'python.exe'), '-m', 'black', 'src', 'tests'], cwd=os.path.join('projects', p), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for p in ['agent-gieldowy', 'agent-predykcje']]; raise SystemExit(0)\""
```

- [ ] **Step 7: Commit**

```bash
git add projects/agent-predykcje/pyproject.toml projects/agent-predykcje/.gitignore projects/agent-predykcje/watchlist.yaml projects/agent-predykcje/src projects/agent-predykcje/tests .claude/settings.json
git commit -m "feat(agent-predykcje): scaffold package, watchlist and config"
```

---

### Task 2: Collector and news (copy-adapt from Project 2)

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/collector.py`, `projects/agent-predykcje/src/agent_predykcje/news.py`
- Test: `projects/agent-predykcje/tests/test_collector.py`, `projects/agent-predykcje/tests/test_news.py`

**Interfaces:**
- Produces: `http_get(url, params=None, session=None) -> requests.Response` (retries, raises `CollectorError`), `fetch_quotes(symbol, kind, session=None) -> pd.DataFrame` (daily `(date, close)`, oldest→newest, last 365 calendar days), `collect(watchlist, data_dir) -> dict` (`{symbol: {"status": "ok"|"error", "rows": int}}`, incremental CSV `data/<symbol>.csv`), `CollectorError`, `UnknownSymbolError`; `NEWS_FEEDS` (the two URLs in Global Constraints), `fetch_news(feed_urls, limit=20, session=None) -> list[{"title","published","link"}]` (merged, newest-first; a dead feed is skipped), `save_news(items, data_dir)`, `load_news(data_dir) -> list` (returns `[]` when file missing or unparseable).

- [ ] **Step 1: Write the failing tests**

`tests/test_collector.py` (mocked `requests`):
```python
def test_fetch_quotes_returns_date_close_frame(monkeypatch):
    # mock http_get returning Yahoo-like JSON with 3 daily closes; assert columns,
    # oldest→newest order, and float closes

def test_collect_writes_incremental_csv(tmp_path, monkeypatch):
    # mock http_get; run collect twice with the same watchlist;
    # assert data/PKO.WA.csv exists and rows are not duplicated on the second run

def test_collect_reports_unknown_symbol_error(tmp_path, monkeypatch):
    # mock http_get returning success-but-empty payload; assert result status "error"

def test_http_get_retries_then_raises_collector_error(monkeypatch):
    # mock session.get raising requests.RequestException 3 times;
    # assert CollectorError raised and get called 3 times
```

`tests/test_news.py` (mocked `http_get`):
```python
def test_fetch_news_merges_sorts_limits(monkeypatch):
    # two feeds, out-of-order published dates; assert newest-first order,
    # items capped at limit, and only title/published/link keys

def test_fetch_news_skips_dead_feed(monkeypatch):
    # first feed raises CollectorError; assert items still returned from second

def test_save_and_load_news_roundtrip(tmp_path):
    # save_news then load_news returns the same items; load_news on empty dir returns []
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collector.py tests/test_news.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.collector'`

- [ ] **Step 3: Implement `collector.py` and `news.py`**

Copy `agent_gieldowy/collector.py` and `agent_gieldowy/news.py` verbatim, then adapt: (a) change `from agent_gieldowy.collector import ...` to `from agent_predykcje.collector import ...` in `news.py`; (b) in `collector.py` delete the `fund`/bankier branch — `fetch_quotes` handles only the Yahoo path for `kind` `"stock"`/`"index"`; (c) add `load_news(data_dir) -> list` to `news.py` (reads `data/news.json`; on `OSError`/`json.JSONDecodeError` return `[]`). Keep all names, retry/timeout constants and the `User-Agent` header exactly as in Project 2.

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collector.py tests/test_news.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/collector.py projects/agent-predykcje/src/agent_predykcje/news.py projects/agent-predykcje/tests/test_collector.py projects/agent-predykcje/tests/test_news.py
git commit -m "feat(agent-predykcje): add Yahoo collector and RSS news fetch"
```

---

### Task 3: Technical indicators (copy-adapt `signals.py`)

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/signals.py`
- Test: `projects/agent-predykcje/tests/test_signals.py`

**Interfaces:**
- Produces: `compute_signals(df: pd.DataFrame) -> dict` — flat dict with keys `return_1m`, `return_3m`, `return_6m`, `return_12m`, `annualized_volatility`, `sma50`, `sma200`, `rsi14`, `max_drawdown`, `sma50_above_sma200`, `golden_cross_recent`, `death_cross_recent` (same names and semantics as Project 2; `float("nan")`/`None` when data too short). `TRADING_DAYS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}`.

- [ ] **Step 1: Write the failing tests**

```python
import math
import pandas as pd
from agent_predykcje.signals import compute_signals

def test_returns_on_known_series():
    # 30 rows, close rising linearly from 100 to 129; assert return_1m == 29/100
    # (pytest.approx) and return_12m is NaN (series shorter than 252 days)

def test_rsi14_bounds_and_all_gains_case():
    # 20 rows of strictly rising closes; assert rsi14 == 100.0

def test_cross_flags_none_on_short_series():
    # 100 rows; assert sma50_above_sma200 is None and both cross flags False

def test_volatility_and_drawdown():
    # known alternating series; assert max_drawdown == 0.0 and annualized_volatility >= 0
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.signals'`

- [ ] **Step 3: Implement `signals.py`**

Copy `agent_gieldowy/signals.py` verbatim (pure functions, no imports of other package modules — nothing to adapt). This is exact copy the spec fixes: no design latitude.

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_signals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/signals.py projects/agent-predykcje/tests/test_signals.py
git commit -m "feat(agent-predykcje): add technical indicators (copy-adapted signals)"
```

---

### Task 4: Ten personas (YAML + loader + system prompt)

**Files:**
- Create: `projects/agent-predykcje/personas/{value,technical,momentum,contrarian,macro,news,bull,bear,dividend,quant}.yaml`, `projects/agent-predykcje/src/agent_predykcje/persona.py`
- Test: `projects/agent-predykcje/tests/test_persona.py`

**Interfaces:**
- Produces: `load_persona(path) -> dict`, `render_system_prompt(persona: dict) -> str`. Persona YAML fields: `name` (human name), `display_name` (archetype label shown in the report), `age`, `city`, `profession`, `social_position`, `education`, `life_history` (list), `temperament`, `biases` (list), `style`. The system prompt must end with the task instruction: analyze Polish market, predict the given stock's price at three horizons (1 dzień, 1 tydzień, 1 miesiąc), answer only with JSON matching the schema — and mention the persona's biases must shape the analysis.

- [ ] **Step 1: Write the failing tests**

```python
from agent_predykcje.persona import load_persona, render_system_prompt

def test_all_ten_persona_files_load_with_required_fields():
    # for each stem in the pinned list, load the YAML and assert keys
    # {"name", "display_name", "temperament", "biases", "style"} present,
    # biases is a list of >= 2 non-empty strings, display_name in the pinned
    # archetype set {"Fundamentalista wartościowy", "Analityk techniczny",
    # "Trader momentum", "Kontrarianin", "Makroekonomista", "Analityk newsowy",
    # "Wieczny byk", "Wieczny niedźwiedź", "Rentier dywidendowy", "Statystyk-quant"}

def test_render_system_prompt_contains_persona_and_task():
    # minimal persona dict; assert prompt contains name, temperament text and
    # "1 dzień", "1 tydzień", "1 miesiąc" and mentions JSON schema
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_persona.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.persona'`

- [ ] **Step 3: Implement `persona.py`**

Copy-adapt `agent_gieldowy/persona.py`: keep `load_persona` verbatim; in `render_system_prompt`, add `display_name` support and replace the trailing paragraph (the Project 2 version mentions the journal and a 1-month horizon — neither exists here) with the 3-horizon task instruction from the Interfaces block. Keep the same field defaults.

- [ ] **Step 4: Write the ten persona YAML files**

One file per pinned stem. Each gets the archetype's `display_name` and a distinct profile per the design doc §6.1: value — cautious, dividend-lover, scarred by 2008; technical — charts, support/resistance, RSI; momentum — chases trends, short horizon; contrarian — bets against the crowd; macro — rates/inflation/WIBOR, whole-WIG view; news — lives on headlines; bull — sees upside everywhere; bear — sees risk everywhere; dividend — only dividends and stable cash flows; quant — models, volatility, mean reversion. Written in Polish (like `agent-gieldowy/persona.yaml`), 2–3 `life_history` items and 3–4 `biases` each, distinct `style` lines.

- [ ] **Step 5: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_persona.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add projects/agent-predykcje/personas projects/agent-predykcje/src/agent_predykcje/persona.py projects/agent-predykcje/tests/test_persona.py
git commit -m "feat(agent-predykcje): add ten personas and system-prompt renderer"
```

---

### Task 5: LLM prediction call, schema, validation

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/agent.py`
- Test: `projects/agent-predykcje/tests/test_agent.py`

**Interfaces:**
- Consumes: `load_persona`, `render_system_prompt` (Task 4).
- Produces:
  - `PREDICTION_SCHEMA: dict` — JSON schema object with `predictions` (object with required numeric `1d`/`1w`/`1m`, `additionalProperties: False`) and required string `justification`, root `additionalProperties: False`.
  - `class AgentError(Exception)` — user-facing Polish message.
  - `default_model() -> str` — `os.environ.get("AGENT_PREDYKCJE_MODEL", "claude-opus-5-5")`.
  - `make_client() -> anthropic.Anthropic` — zero-arg client; `anthropic.CredentialsError` → `AgentError("brak poprawnych danych uwierzytelniających Claude API — uruchom `ant auth login` albo ustaw zmienną ANTHROPIC_API_KEY")`.
  - `validate_prediction(prediction: dict, anchor_price: float) -> list[str]` — errors: missing/non-numeric `1d`/`1w`/`1m`; any price not in `[0.5*anchor, 1.5*anchor]`; `justification` missing/empty/not str.
  - `predict_stock(persona_prompt: str, user_message: str, anchor_price: float, client=None, model=None) -> dict` — returns `{"predictions": {"1d": float, "1w": float, "1m": float}, "justification": str}`; retries once on `RateLimitError` (sleep `2 * (attempt + 1)`), malformed/unparseable response, or validation errors; raises `AgentError` on final failure, credentials errors (including the SDK-2.x client-side `TypeError` translation from Project 2), `APIConnectionError`, `AuthenticationError`, `APIStatusError`, and `stop_reason == "refusal"` (`"model odmówił odpowiedzi — pomijam tego agenta"`).
  - `fmt(value, pct: bool = False) -> str` — copy from Project 2 (`—` for None/NaN).
  - `build_user_message(symbol: str, anchor: dict, signals: dict, index_signals: dict, news_items: list) -> str` — Polish sections: `DANE RYNKOWE` (symbol, cena, data, indicators via `fmt`), `KONTEKST INDEKSÓW`, `NAJNOWSZE NAGŁÓWKI` (titles + dates, or `(brak)`), `ZADANIE` (predict the price at 1 dzień / 1 tydzień / 1 miesiąc, return only JSON per the schema).

- [ ] **Step 1: Write the failing tests** — fake client class with a `.messages.create` stub.

```python
import anthropic
import pytest
from agent_predykcje.agent import (AgentError, default_model, make_client,
    predict_stock, validate_prediction, PREDICTION_SCHEMA)

class FakeClient:
    def __init__(self, responses): self.responses = list(responses)
    def messages(self): return self
    def create(self, **kwargs):
        kind = self.responses.pop(0)
        if isinstance(kind, Exception): raise kind
        return kind

def _ok_response():
    # object with .content = [TextBlock("{\"predictions\":{\"1d\":62.4,\"1w\":63.2,\"1m\":65.1},\"justification\":\"Trend wzrostowy\"}")]
    # and .stop_reason = "end_turn"

def test_predict_stock_returns_validated_dict():
    client = FakeClient([_ok_response()])
    result = predict_stock("prompt", "msg", 62.0, client=client, model="m")
    assert result["predictions"] == {"1d": 62.4, "1w": 63.2, "1m": 65.1}
    assert result["justification"] == "Trend wzrostowy"

def test_predict_stock_invalid_json_retries_then_raises():
    bad = _ok_response()  # content text = "not json"
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError):
        predict_stock("p", "m", 62.0, client=client, model="m")

def test_predict_stock_ratelimit_retries_once():
    client = FakeClient([anthropic.RateLimitError("slow", response=None, body=None), _ok_response()])
    result = predict_stock("p", "m", 62.0, client=client, model="m")
    assert result["predictions"]["1m"] == 65.1

def test_validate_prediction_out_of_range():
    pred = {"predictions": {"1d": 62.0, "1w": 63.0, "1m": 100.0}, "justification": "x"}
    errors = validate_prediction(pred, 62.0)
    assert any("1m" in e for e in errors)

def test_validate_prediction_missing_justification():
    pred = {"predictions": {"1d": 62.0, "1w": 63.0, "1m": 64.0}}
    assert validate_prediction(pred, 62.0)  # non-empty error list

def test_refusal_stop_reason_raises():
    resp = _ok_response(); resp.stop_reason = "refusal"
    client = FakeClient([resp])
    with pytest.raises(AgentError):
        predict_stock("p", "m", 62.0, client=client, model="m")

def test_make_client_credentials_error(monkeypatch):
    def boom(): raise anthropic.CredentialsError("bad")
    monkeypatch.setattr("agent_predykcje.agent.anthropic.Anthropic", boom)
    with pytest.raises(AgentError, match="ant auth login"):
        make_client()

def test_default_model_env_override(monkeypatch):
    monkeypatch.setenv("AGENT_PREDYKCJE_MODEL", "claude-sonnet-5-5")
    assert default_model() == "claude-sonnet-5-5"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.agent'`

- [ ] **Step 3: Implement `agent.py`**

Copy-adapt `agent_gieldowy/agent.py`: keep the error-handling chain and `make_client`/`fmt` verbatim; replace `PREDICTION_SCHEMA` with the 3-horizon schema above; `predict_stock` performs **one call for one stock** (no `watchlist_symbols` — validation is per-call via `validate_prediction(prediction, anchor_price)`), with the call shape pinned in Global Constraints (including `effort`, `betas`, `fallbacks`), plus the `stop_reason == "refusal"` check before parsing content; replace `build_user_message` with the signature above (no journal digest — that section does not exist here).

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/agent.py projects/agent-predykcje/tests/test_agent.py
git commit -m "feat(agent-predykcje): add per-stock LLM prediction with schema validation"
```

---

### Task 6: Analysis pipeline and run snapshot

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/pipeline.py`
- Test: `projects/agent-predykcje/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `predict_stock`, `AgentError` (Task 5); `load_persona`, `render_system_prompt` (Task 4); `compute_signals` (Task 3); `load_news` (Task 2).
- Produces:
  - `load_price_frame(data_dir, symbol) -> pd.DataFrame` — reads `data/<symbol>.csv`, oldest→newest; raises `FileNotFoundError` when missing.
  - `anchor_of(df: pd.DataFrame) -> dict` — `{"date": <last row date str>, "price": <last close float>}`.
  - `run_analysis(watchlist, data_dir, personas_dir, client=None, model=None, max_workers=5) -> dict` — the snapshot (Global Constraints schema). Per stock: load frame (missing CSV → `{"symbol", "anchor": None, "agents": []}`); per persona: `predict_stock` (stock agent entry `status: "ok"` with predictions+justification, or `status: "error"` with `str(exc)`). Calls run in a `concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)`; one agent's failure never aborts the run. `created_at` = `datetime.now(timezone.utc).isoformat()`.
  - `save_snapshot(snapshot, predictions_dir) -> Path` — `predictions-YYYYmmdd-HHMMSS.json`, UTF-8, `ensure_ascii=False`, `indent=2`.
  - `load_snapshot(path) -> dict`; `latest_snapshot(predictions_dir) -> Path | None` (newest `predictions-*.json` by filename; `None` when none).

- [ ] **Step 1: Write the failing tests**

```python
import pandas as pd
import pytest
from agent_predykcje.agent import AgentError
from agent_predykcje.pipeline import (anchor_of, latest_snapshot, load_price_frame,
    load_snapshot, run_analysis, save_snapshot)

def test_anchor_of_uses_last_row(tmp_path):
    df = pd.DataFrame({"date": ["2026-10-23", "2026-10-26", "2026-10-27"],
                       "close": [61.0, 61.5, 62.0]})
    assert anchor_of(df) == {"date": "2026-10-27", "price": 62.0}

def test_run_analysis_one_agent_error(tmp_path, monkeypatch):
    # data/PKO.WA.csv with 30 rows; personas_dir with 2 persona yamls;
    # monkeypatch pipeline.predict_stock: returns ok for persona "a",
    # raises AgentError("boom") for persona "b"
    snapshot = run_analysis({"stocks": ["PKO.WA"], "indices": []}, data_dir, personas_dir,
                            client=object(), model="m", max_workers=2)
    stock = snapshot["stocks"][0]
    assert stock["anchor"] == {"date": <last row date>, "price": <last close>}
    by_id = {a["persona"]: a for a in stock["agents"]}
    assert by_id["a"]["status"] == "ok" and by_id["a"]["predictions"]["1m"] is not None
    assert by_id["b"]["status"] == "error" and by_id["b"]["error"] == "boom"
    assert by_id["b"]["predictions"] is None

def test_run_analysis_missing_csv_yields_empty_stock(tmp_path):
    # no data dir files; assert stock entry with anchor None and agents == []

def test_save_load_snapshot_roundtrip(tmp_path):
    snap = {"created_at": "x", "model": "m", "stocks": []}
    path = save_snapshot(snap, tmp_path)
    assert path.name.startswith("predictions-") and path.suffix == ".json"
    assert load_snapshot(path) == snap

def test_latest_snapshot_picks_newest(tmp_path):
    save_snapshot({"created_at": "1", "model": "m", "stocks": []}, tmp_path)
    # save a second snapshot; assert latest_snapshot() == second path;
    # in an empty dir assert latest_snapshot() is None
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.pipeline'`

- [ ] **Step 3: Implement `pipeline.py`**

`run_analysis` builds each stock's data package once (frame → `anchor_of` → `compute_signals`; index frames → `compute_signals` per index; `load_news`), then submits one future per (stock, persona): `render_system_prompt(load_persona(p))` as system, `build_user_message(...)` as user message, `predict_stock(...)` with the shared `client`. Collect futures in submission order; per-future `except AgentError` (and only that — programming errors propagate) records the error entry. Reuse the client across all 30 calls (one client, threads share it).

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/pipeline.py projects/agent-predykcje/tests/test_pipeline.py
git commit -m "feat(agent-predykcje): add 30-call analysis pipeline and run snapshot"
```

---

### Task 7: Report — aggregates, band chart, HTML

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/report.py`
- Test: `projects/agent-predykcje/tests/test_report.py`

**Interfaces:**
- Consumes: snapshot schema (Task 6).
- Produces:
  - `DISCLAIMER = "narzędzie szkoleniowe, nie porada inwestycyjna"`.
  - `ok_agents(stock: dict) -> list[dict]`; `averages(stock) -> dict | None` — `{"1d","1w","1m","count"}` over ok agents, `None` when none.
  - `horizon_band(stock) -> dict | None` — `{"1d": (min, max), "1w": (…), "1m": (…)}` over ok agents.
  - `gain_1m(stock) -> float | None` — `(avg_1m - anchor_price) / anchor_price * 100`, `None` when anchor or averages missing.
  - `sorted_stocks(snapshot) -> list[dict]` — descending `gain_1m`, `None`-gain stocks last in snapshot order.
  - `badge_html(gain: float) -> str` — `średni zysk {+x,x}%` (comma decimal, one decimal, `+` sign), green `#1a7f37` if > 0, red `#c62828` if < 0, gray otherwise.
  - `band_figure(stock) -> go.Figure` — x categories `["Dziś", "+1 dzień", "+1 tydzień", "+1 miesiąc"]`; trace 1 = average line `[anchor, avg_1d, avg_1w, avg_1m]` (black, width 3); trace 2 = min–max band area (gray, low opacity) built from `horizon_band` with the anchor point fixed at both min and max; y-axis `PLN`, height 320.
  - `render_report(snapshot, out_path) -> str` — self-contained HTML (plotly `include_plotlyjs` once), Polish: title `Raport przewidywań GPW`, date from `created_at`, disclaimer paragraph, then one section per stock in `sorted_stocks` order: header `N. SYMBOL · 62,00 zł · 2026-10-27` + `badge_html` (rank N = position); figure (skipped with `Brak danych.` when anchor is None); table with columns `Agent | +1 dzień | +1 tydzień | +1 miesiąc | Uzasadnienie`, rows = agents (display_name; prices `f"{v:.2f}".replace(".", ",")`; `brak danych` ×3 for error agents; justification escaped), final row `Średnia` with averaged prices and empty justification. Every dynamic string passed through `html.escape`. Writes `out_path` (parent created if needed) and returns `str(out_path)`.

- [ ] **Step 1: Write the failing tests** — a helper builds a 2-stock snapshot with ok/error agents.

```python
import html as html_mod
from agent_predykcje.report import (averages, badge_html, band_figure, gain_1m,
    horizon_band, render_report, sorted_stocks)

def _stock(symbol, anchor_price, preds, error_ids=()):
    agents = []
    for pid, name, p in preds:
        agents.append({"persona": pid, "display_name": name, "status": "ok",
                       "error": None, "predictions": p, "justification": "uzasadnienie"})
    for pid in error_ids:
        agents.append({"persona": pid, "display_name": pid, "status": "error",
                       "error": "boom", "predictions": None, "justification": None})
    return {"symbol": symbol, "anchor": {"date": "2026-10-27", "price": anchor_price},
            "agents": agents}

def test_averages_ignore_error_agents():
    # 2 ok agents (1d: 10, 12), 1 error; assert averages == {"1d": 11.0, ...} and count == 2

def test_horizon_band_min_max():
    # ok agents 1m: 100, 104; assert horizon_band()["1m"] == (100.0, 104.0)

def test_gain_1m_and_sorted_stocks():
    # stock A: anchor 100, avg 1m 110 → gain 10.0; stock B: anchor 50, avg 1m 52 → 4.0;
    # stock C: no ok agents → gain None; assert sorted order == [A, B, C]

def test_badge_colors_and_comma_format():
    assert "background" not in badge_html(2.5)  # green span text contains "+2,5%"
    assert "#1a7f37" in badge_html(2.5) and "#c62828" in badge_html(-1.3)
    # gray when gain == 0.0

def test_render_failed_agent_row_and_averages(tmp_path):
    snapshot = {"created_at": "2026-10-27T10:00:00+00:00", "model": "m",
                "stocks": [_stock("PKO.WA", 62.0, [("a", "A", {"1d": 62.0, "1w": 62.0, "1m": 62.0})], error_ids=["b"])]}
    out = render_report(snapshot, tmp_path / "raport.html")
    text = (tmp_path / "raport.html").read_text(encoding="utf-8")
    assert "brak danych" in text and "Średnia" in text and "narzędzie szkoleniowe" in text

def test_render_escapes_html_in_justification(tmp_path):
    agent justification = "<script>alert(1)</script>"
    out = render_report(snapshot, tmp_path / "raport.html")
    text = read; assert "<script>alert" not in text and "&lt;script&gt;" in text

def test_render_header_shows_anchor_date(tmp_path):
    # snapshot with anchor date "2026-10-23" (Friday); assert "2026-10-23" appears
    # in the section header and "2026-10-27" (created_at date) only near the title

def test_render_missing_data_section(tmp_path):
    # stock with anchor None; assert "Brak danych." present for that section and
    # render_report still succeeds

def test_band_figure_traces():
    fig = band_figure(_stock("PKO.WA", 62.0, [...]))
    assert len(fig.data) == 2  # band + average line
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.report'`

- [ ] **Step 3: Implement `report.py`**

Follow the Interfaces block; copy `fmt`/escaping conventions from Project 2's `report.py` (`html.escape` on every dynamic value, `fig.to_html(full_html=False, include_plotlyjs=first)` pattern). The band trace uses `go.Scatter(fill="tonexty")` over the min/max series with the anchor point duplicated at index 0 of both series; the average line is a separate `go.Scatter(mode="lines+markers", line=dict(color="#111", width=3))`.

- [ ] **Step 4: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/report.py projects/agent-predykcje/tests/test_report.py
git commit -m "feat(agent-predykcje): add sorted HTML report with band charts and agent tables"
```

---

### Task 8: CLI (`collect` / `analyze` / `report` / `run`), README

**Files:**
- Create: `projects/agent-predykcje/src/agent_predykcje/cli.py`, `projects/agent-predykcje/README.md`
- Test: `projects/agent-predykcje/tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: `main(argv=None) -> int` — argparse; subcommands `collect`, `analyze`, `report`, `run`; flags `--model` (analyze, run) and `--snapshot PATH` (report). Path helpers (module-level functions, monkeypatchable in tests): `PROJECT_DIR` (`src/agent_predykcje/cli.py` → project root, like Project 2), `_watchlist_path()`, `_data_dir()`, `_predictions_dir()`, `_personas_dir()`, `_report_path()` (`report/raport.html`). `analyze` prints per stock `SYMBOL: N/10 agentów OK` and the snapshot path; `report` renders the latest snapshot (or `--snapshot`) and opens it with `webbrowser.open`; `run` = collect + analyze + report. `AgentError`/`CollectorError` → print Polish message, return 1; missing `watchlist.yaml` or empty `personas/` → clear Polish message, return 1 — **never a raw traceback** (Project 2 follow-up M9).

- [ ] **Step 1: Write the failing tests**

```python
from agent_predykcje import cli

def test_analyze_credentials_error_exit_code(tmp_path, monkeypatch, capsys):
    # monkeypatch cli.run_analysis to raise AgentError("brak danych uwierzytelniających…")
    # monkeypatch cli._watchlist_path etc. to tmp_path fixtures (watchlist.yaml + personas/)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "ant auth login" in out
    assert "Traceback" not in out

def test_analyze_missing_watchlist_message(tmp_path, monkeypatch, capsys):
    # no watchlist.yaml; assert return 1 and "watchlist.yaml" in output, no traceback

def test_report_no_snapshot_message(tmp_path, monkeypatch, capsys):
    # empty predictions dir; assert return 1 and Polish "brak" message, no traceback

def test_run_flow_uses_components(monkeypatch, tmp_path):
    # monkeypatch cmd_collect/cmd_analyze/cmd_report with recorders; main(["run"]) == 0
    # and all three called in order

def test_report_opens_latest_snapshot(tmp_path, monkeypatch):
    # monkeypatch render_report + webbrowser.open + latest_snapshot;
    # assert render_report called with the latest snapshot dict
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_predykcje.cli'`

- [ ] **Step 3: Implement `cli.py`**

Copy-adapt the argparse structure from `agent_gieldowy/cli.py` (subcommand dispatch, `webbrowser.open`, path helpers) with the four subcommands above and the pinned error handling. Wrap each `cmd_*` body so `AgentError`/`CollectorError`/`FileNotFoundError` become printed Polish messages with exit code 1; `KeyboardInterrupt` returns 130.

- [ ] **Step 4: Write `README.md`**

Polish, ~30 lines: what it does, the 10 personas, usage examples (`agent-predykcje collect`, `analyze`, `report`, `run`, `--model`), credentials note (`ant auth login` or `ANTHROPIC_API_KEY`), cost note (30 LLM calls per run), disclaimer.

- [ ] **Step 5: Run tests, verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python -m pytest tests -v`
Expected: PASS (all tasks' tests together)

- [ ] **Step 7: Commit**

```bash
git add projects/agent-predykcje/src/agent_predykcje/cli.py projects/agent-predykcje/README.md projects/agent-predykcje/tests/test_cli.py
git commit -m "feat(agent-predykcje): add CLI pipeline, error handling and README"
```

---

### Task 9: Live smoke (manual, marked `live`)

**Files:**
- Create: `projects/agent-predykcje/tests/test_live.py`

**Interfaces:**
- Consumes: the whole CLI.

- [ ] **Step 1: Write `test_live.py`**

`@pytest.mark.live` — one test: `main(["collect"])` then `main(["run"])` (skips `report`'s browser by monkeypatching `webbrowser.open`), asserts a snapshot file exists under `predictions/`, every stock has an anchor, and `raport.html` exists. Marked `live` so it is excluded by default (`addopts = "-m 'not live'"`, marker already configured in `pyproject.toml` from Task 1).

- [ ] **Step 2: Commit**

```bash
git add projects/agent-predykcje/tests/test_live.py
git commit -m "test(agent-predykcje): add live end-to-end smoke test"
```

---

### Task 10: Final review fixes and docs sync

**Files:**
- Modify: files flagged by whole-branch code review; `docs/superpowers/specs/2026-10-27-agent-predykcje-design.md` (status line only if anything drifted)

**Interfaces:**
- None new.

- [ ] **Step 1: Request whole-branch code review** (superpowers:requesting-code-review) and apply accepted fixes, one commit per fix wave.
- [ ] **Step 2: Run the full suite** — `.venv/Scripts/python -m pytest tests -v` — and confirm PASS.
- [ ] **Step 3: Commit any remaining fixes**, then follow superpowers:finishing-a-development-branch to merge.
