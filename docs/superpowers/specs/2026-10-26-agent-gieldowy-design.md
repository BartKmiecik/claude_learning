# Agent Giełdowy — Design

**Date:** 2026-10-26
**Status:** Approved (design presented in chat; user approved 2026-10-26)

## 1. Purpose

A **training project** (learning-path Project 2 — replaces the planned filesweeper) that practices four skill areas in one coherent build:

1. **Claude API + persona engineering** — an LLM "market analyst" with a simulated personality, life history, social position, and profession, whose analyses are shaped by its own past.
2. **Claude Code process** — subagent-driven execution, worktrees, code review, one commit per task.
3. **Data pipeline** — fetching, incremental caching, and cleaning 12 months of daily prices for Polish stocks (GPW), WIG indices, and TFI investment funds, plus instrument-related news.
4. **Visualizations** — an interactive HTML report (plotly) opened in the browser.

The tool collects daily prices from the last 12 months, runs a persona-driven agent that evaluates the data and predicts one-month stock/index moves, and renders the results as a CLI + HTML report.

## 2. Honest Expectations

- **Forecast accuracy is explicitly NOT a success criterion.** Market prediction is speculative; the report carries a visible disclaimer ("narzędzie szkoleniowe, nie porada inwestycyjna" — training tool, not investment advice).
- Success is measured by the quality of the tool and the process: a working incremental pipeline, an agent whose persona and journal demonstrably shape its analyses, validated structured outputs, and a readable report.

## 3. Success Criteria (training goals)

| Goal | How it is demonstrated |
|---|---|
| Pipeline | Incremental collector with retries and graceful degradation; 12 months of data for the watchlist; unit tests with mocked HTTP |
| Claude API + persona | Agent runs on the Anthropic SDK; persona (personality, history, social position, profession, explicit biases) visibly skews analyses; journal of past predictions + reflections feeds the next analysis |
| Validated output | Structured prediction JSON, schema-validated and sanity-checked before it is persisted |
| Visualizations | Self-contained HTML report (plotly) with charts, signals, agent section, journal history, news links |
| CC process | Subagent-driven execution (implementer + reviewers), worktree isolation, one commit per task |

## 4. Constraints

- **Language/stack:** Python CLI project, repo conventions from Project 1: venv, TDD (pytest), black hook, one commit per task. Lives in `projects/agent-gieldowy/`.
- **Market:** Polish only — GPW stocks, WIG indices, TFI funds.
- **Data sources** (probe-verified 2026-10-26; stooq.pl is bot-gated — even solving its PoW challenge returns "Odmowa dostępu", so it was dropped): Yahoo chart API v8 for GPW stocks/indices (`https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d`, `.WA` symbols, `User-Agent` header required, no key); public bankier.pl API for TFI fund NAVs (`https://api.bankier.pl/quotes/public/bankier-tfi/bankier-fund-chart-data?symbol={symbol}`); RSS (bankier.pl) for news. Yahoo and bankier are unofficial APIs — acceptable for a training project; they may change without notice.
- **Claude API:** official `anthropic` SDK, default model **`claude-opus-5-5`** (config-switchable, e.g. to a cheaper model, without code changes). Auth via the zero-arg client (resolves `ant auth login` profile or `ANTHROPIC_API_KEY`); missing credentials produce a clear instructional error, never a crash dump.
- **Cost:** one `analyze` run = 1 compact LLM call (signals + news + journal digest for ~8 instruments); one `evaluate` reflection = 1 small call. Cents per run at opus-5-5 pricing.
- **Storage:** flat files — `data/<symbol>.csv` + `data/news.json` + `journal/entries.jsonl`. No database (YAGNI: 12 months of daily data ≈ 250 rows per instrument).

## 5. Architecture

```
Yahoo API (stocks/indices) ─┐
bankier API (funds) ────────┼─> [collector] ──> data/*.csv ──> [signals] ──┐
RSS news ───────────────────┘                                             │
                                                       ▼
   journal/entries.jsonl (past) <── [agent: persona + Claude API] ──> prediction JSON
                                                       │
                                        [report] ──> report.html (browser)
```

Modules (each a separate Python module, independently testable):

| Module | Responsibility | Depends on |
|---|---|---|
| `collector` | Downloads 12 months of daily quotes — Yahoo (stocks/indices) and bankier.pl (funds) — for every instrument in `watchlist.yaml` → `data/<symbol>.csv`; incremental (appends only new days) | — |
| `news` | Downloads recent RSS headlines (bankier.pl giełda/gospodarka) → `data/news.json` | — |
| `signals` | Pure functions over a DataFrame: 1/3/12-month returns, annualized volatility, momentum, SMA50/200 + golden cross, RSI14, max drawdown | pandas |
| `persona` | Loads `persona.yaml` and renders the system prompt | — |
| `journal` | Append/read/digest of `journal/entries.jsonl` | — |
| `agent` | Claude API call: system = persona, user = signals + news + journal digest; structured output, validated; writes journal entry | anthropic, persona, journal |
| `report` | Renders `report.html` (plotly, self-contained) from data + signals + journal | plotly |

## 6. Components

### 6.1 collector

- Instruments come from `watchlist.yaml` with sections `stocks:`, `indices:`, `funds:` (defaults in §12).
- Stocks/indices: Yahoo chart API v8, `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d` (JSON; `User-Agent` header required; empty `chart.result` = unknown symbol). Symbols carry the `.WA` suffix (`PKO.WA`, `WIG20.WA`, `MWIG40.WA`).
- Funds: bankier public API, `https://api.bankier.pl/quotes/public/bankier-tfi/bankier-fund-chart-data?symbol={symbol}` (JSON: `data[0].data` = list of `[epoch_ms, nav]`). Bankier fund symbols are short codes (e.g. `AGF04` = AGIO Kapitał); more are discoverable at `https://www.bankier.pl/fundusze/notowania/wszystkie`.
- Both normalize to a common DataFrame (`date`, `close`) → `data/<symbol>.csv`; trim to the last 365 calendar days.
- Incremental: compare the last local date with the downloaded data; append only new rows.
- Gaps (suspensions, no session) are simply absent from the frame; signals are computed on the observed dates (`pct_change`/`rolling` tolerate gaps). No forward-fill — fabricating prices adds complexity without value for a training project.

### 6.2 news

- RSS feeds from bankier.pl (giełda, gospodarka); keep the latest ~20 items (title, date, link) in `data/news.json`.
- The agent receives titles + dates only; links go to the report.

### 6.3 signals

Deterministic, pure, no I/O — full unit-test coverage:

- Returns: 1, 3, 12 months
- Annualized volatility (std of daily returns × √252)
- Momentum: 6-month return
- SMA50, SMA200, golden/death cross flag
- RSI14
- Max drawdown (12 months)

### 6.4 persona

`persona.yaml` defines, explicitly and separately:

- **Identity:** name, age, city, **profession (work)**, education, **social position**.
- **Life history:** formative market experiences that shape judgment.
- **Temperament and explicit biases:** listed as first-class fields (e.g., risk aversion, trust in dividend stocks, distrust of growth stories) — visible so the user can see *how* the persona skews analyses and can experiment by editing the file.

Default persona (authored during implementation): a ~55-year-old TFI analyst from Kraków who lived through the 2008 crash and the 2020 covid slump (lost part of his savings), conservative and risk-averse, trusts dividend payers, distrusts growth stocks.

### 6.5 journal (the agent's "past")

`journal/entries.jsonl` — one JSON object per line:

1. **Append on analyze:** timestamp, signal snapshot, prediction JSON, full analysis text.
2. **Read on analyze:** a digest — the last 3 entries in full plus a stored digest of older entries. The digest is deterministic (per entry: date, predicted directions, outcomes if evaluated, stored reflection sentences — no extra LLM call), regenerated after each journal append so token cost does not grow linearly with history.
3. **Evaluate (predictions ≥ 30 calendar days old):** fetch actual prices since the prediction date; score direction hit and range hit; append the outcome to the entry.
4. **Reflection (after scoring):** one small LLM call — old prediction + actual outcome → 1–2 sentences of reflection ("what I missed / what worked"), appended to the entry. The next analysis reads these reflections, so the agent experiences the consequences of its decisions in character (a stubborn analyst may rationalize misses — that is a feature).

### 6.6 agent

- Single Messages API call via the `anthropic` SDK, model `claude-opus-5-5` by default.
- System prompt = persona; user message = signals table + news titles + journal digest + prediction instructions.
- Structured output via `output_config.format`; response validated against the prediction contract (§8) plus sanity checks.
- Invalid/refused output → one retry, then a clean error; invalid output is never silently persisted.
- The full analysis text is stored with the prediction in the journal.

### 6.7 report

Renders a self-contained `report.html` (plotly, no server). Layout in §11. Renders data + signals always; the agent section appears only when a prediction exists.

## 7. CLI

argparse (stdlib), project entry point `agent-gieldowy`:

| Command | Action |
|---|---|
| `collect` | Fetch quotes + news |
| `analyze` | Compute signals, run the agent, append journal entry |
| `evaluate` | Score predictions ≥ 30 days old, append outcomes + LLM reflections |
| `report` | Render `report.html` and open it in the browser |
| `run` | collect → analyze → report |

## 8. Prediction Contract

Structured output, one-month horizon:

```json
{
  "horizon": "1M",
  "generated_at": "2026-10-26T12:00:00Z",
  "predictions": [
    {
      "symbol": "PKO",
      "direction": "up",
      "range_pct": {"min": -5.0, "max": 8.0},
      "confidence": 65,
      "rationale": "...",
      "risks": ["..."]
    }
  ],
  "summary": "..."
}
```

- `direction`: `up` | `down` | `sideways`; **sideways = expected absolute change ≤ 2%** (defined in the prompt).
- `confidence`: integer 0–100.
- Sanity checks in code: `min <= max`, confidence in range, `symbol` exists in the watchlist, `horizon` == "1M", every watchlist instrument has a prediction.

## 9. Error Handling

- **Data sources (Yahoo / bankier / RSS):** timeout + 2 retries, then a warning and continue with partial data — `collect` never dies because one source failed; the report marks gaps.
- **Claude API:** typed exception chain — `RateLimitError` → retry with backoff; `APIStatusError` / `APIConnectionError` → readable message; missing credentials → instruction (`ant auth login` or `ANTHROPIC_API_KEY`).
- **Agent failure during `analyze`:** non-zero exit with a clear message; signals are already on disk, so a retry refetches nothing. The report renders without the agent section.

## 10. Testing Strategy

TDD per repo convention. **No live API calls in tests.**

- `signals` — full unit tests on known data (pure functions).
- `collector` / `news` — mocked HTTP with fixture responses (incl. failure/partial-data cases).
- `journal` — append / read / digest / scoring.
- `agent` — mocked Anthropic client: verifies prompt assembly (persona + signals + digest) and parsing/rejection of responses (valid, malformed, refused).
- `report` — generation test (sections present, no exceptions).
- Optional live smoke test behind `--live` (manual only).

## 11. Report Layout

1. **Header:** generation date, horizon, disclaimer ("narzędzie szkoleniowe, nie porada inwestycyjna").
2. **Per instrument:** 12-month price chart (line + SMA50/200) + mini signal table (returns, volatility, RSI, drawdown).
3. **Agent section:** persona card (who it is, explicit biases) + analysis + prediction table (direction, range %, confidence) + risks.
4. **Journal:** last N entries + historical hit counter (X/Y directions hit).
5. **News:** titles with links to sources.

## 12. Defaults

- **Watchlist** (editable in `watchlist.yaml`, symbols probe-verified 2026-10-26): indices `WIG20.WA`, `WIG.WA`, `MWIG40.WA`; stocks `PKO.WA`, `PZU.WA`, `PKN.WA`; funds `AGF04` (AGIO Kapitał), `AGF44` (AGIO Akcji PLUS).
- **Persona:** as described in §6.4.

## 13. Open Implementation Points

These are deliberate decision points for the implementation plan, not gaps:

1. **Persona copy** — author the default persona YAML during implementation.
2. **Watchlist contents** — confirm the default instrument list with the user during implementation (defaults in §12 are probe-verified).
3. **Unofficial API risk** — Yahoo and bankier endpoints are unofficial; if one changes, the collector is isolated so only `collector.py` needs a fix (a new source adapter behind the same DataFrame interface).

## 14. Out of Scope

- Strategy backtesting (only the agent's own predictions are evaluated).
- Portfolio/P&L simulation.
- Web server, auth, multi-user.
- Database (CSV + JSONL only).
- Markets other than Polish.
