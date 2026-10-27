# Agent Predykcje — Design

**Date:** 2026-10-27
**Status:** Approved (user approved 2026-10-27)

## 1. Purpose

A **training project** (learning-path Project 3) that builds on `agent-gieldowy`. Instead of one persona-driven analyst, **ten agents with distinct personalities** each analyze the same GPW stocks — 12 months of daily price history plus recent news — and predict the price at three horizons: **+1 day, +1 week, +1 month**.

The tool renders a **single-page HTML report** (plotly, like Project 2): one section per stock, each with a chart of the **average prediction + min–max band** of the ten agents, and below it a table with every agent's three predictions and a **one-line justification**. Sections are sorted by **average predicted gain at +1 month**, descending.

Why: practice multi-agent LLM orchestration, persona diversity, prediction aggregation (average/band), and comparative visualization.

## 2. Honest Expectations

- **Forecast accuracy is explicitly NOT a success criterion.** Market prediction is speculative; the report carries the same visible disclaimer as Project 2 ("narzędzie szkoleniowe, nie porada inwestycyjna" — training tool, not investment advice).
- Success is measured by the quality of the tool and process: ten personas whose distinct temperaments visibly skew predictions (bull ≠ bear), schema-validated structured outputs from all 30 calls, a readable sorted report, and tests.

## 3. Success Criteria

| Goal | How it is demonstrated |
|---|---|
| Pipeline | Reuse Project 2's verified sources: Yahoo chart API v8 for GPW daily quotes (365 days) and bankier.pl RSS for news; incremental CSV cache in `data/` |
| Personas | 10 YAML persona files (name, temperament, biases, style, life history), each rendered into a system prompt, as in `agent-gieldowy/persona.yaml`; personas demonstrably skew predictions |
| Multi-agent | One LLM call per (agent, stock) — 30 calls per run; structured JSON output (3 numeric predictions + one-line justification), schema-validated and sanity-checked; a single failed call degrades gracefully, not fatally |
| Aggregation | Per stock per horizon: average of successful agents + min–max band |
| Report | Self-contained HTML opened in the browser; sections sorted by average +1M predicted % gain; band chart + agent table with justifications; all external text HTML-escaped (lesson from Project 2) |
| CC process | TDD (pytest), subagent-driven execution, one commit per task, code review |

## 4. Constraints

- **Language/stack:** Python CLI project, repo conventions from Projects 1–2: venv, TDD, black hook, one commit per task. Lives in `projects/agent-predykcje/`.
- **Data sources** (verified in Project 2): Yahoo chart API v8 for GPW stocks/indices (`https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=2y&interval=1d`, `.WA` symbols, `User-Agent` header, no key); bankier.pl RSS for news. Unofficial APIs — acceptable for a training project; may change without notice.
- **Watchlist:** the 3 stocks from `watchlist.yaml` — `PKO.WA`, `PZU.WA`, `PKN.WA`. Indices (`WIG20`, `WIG`, `MWIG40`) are fetched only as context data included in agent prompts; they are not predicted. Funds are excluded entirely.
- **Code reuse:** `agent-predykcje` is a **standalone package with its own venv** (learning-project convention: each project is independent). Verified code from `agent-gieldowy` (collector, news fetching, config, Anthropic error-handling) is **copied and adapted**, never imported — the two projects never depend on each other.
- **Claude API:** official `anthropic` SDK; model config-switchable without code changes (same mechanism as Project 2); auth via zero-arg client (`ant auth login` profile or `ANTHROPIC_API_KEY`); missing credentials produce a clear instructional error, never a crash dump. One full run = **30 compact LLM calls** (10 personas × 3 stocks), so the default model choice matters for cost; the builder may set a cheaper default than Project 2's.
- **Storage:** flat files — `data/<symbol>.csv` (same format as Project 2's collector), `data/news.json`, and a **self-contained run snapshot** `predictions/predictions-<timestamp>.json` recording the analysis date, per-symbol anchor (current) price and its date, and per-agent per-horizon predictions, justifications and success flags. `report` reads the snapshot only — sorting, badges and % gains reproduce the analysis exactly, even after a later `collect`. No database.
- **Report:** self-contained HTML with plotly charts, opened in the browser, matching the approved mockups (section order, badges, band chart, table layout).

## 5. Scope

**In scope (v1):**
- `collect` — daily quotes for stocks + indices, news from bankier.pl RSS (incremental cache)
- `analyze` (working name) — for each stock × each of 10 personas: build prompt from price history, computed technical indicators, index context and news; call the LLM; validate structured output
- `report` — single-page HTML: sections sorted by average +1M predicted % gain; per section: header with symbol, current price, "średni zysk" badge; band chart (average + min–max); table of 10 agents × 3 horizons with one-line justifications + average row; disclaimer
- `run` — collect → analyze → report → open browser (argparse CLI like Project 2)

**Non-goals (v1):**
- Evaluating or journaling past predictions (Project 2 has a journal/evaluate loop; wiring that up here is a possible follow-up)
- Intraday/real-time data, funds, predicting indices
- Any trading advice or buy/sell signals

**Anti-goals:**
- A report that implies the average is a reliable forecast — the disclaimer and neutral styling must prevent this
- A run that fails entirely when one agent call fails — the table marks the failed agent and the average is computed over the successful ones
- Overpromising accuracy in copy or naming

## 6. Decisions Made With the User

1. **Ten personas**, exactly as approved (each rendered from a YAML profile like Project 2's `persona.yaml`):
   1. Fundametalista wartościowy (cautious value investor, dividend-lover, scarred by 2008, distrusts fads)
   2. Analityk techniczny (charts, support/resistance, RSI/MACD, short horizon)
   3. Trader momentum (chases trends, buys strength, quick in-and-out)
   4. Kontrarianin (bets against the crowd, hunts oversold names)
   5. Makroekonomista (rates, inflation, WIBOR, global macro, whole-WIG view)
   6. Analityk newsowy (lives on headlines, quarterly results, company releases)
   7. Wieczny byk (sees upside everywhere)
   8. Wieczny niedźwiedź (sees risk everywhere, expects corrections)
   9. Rentier dywidendowy (dividends and stable cash flows only)
   10. Statystyk-quant (models, moving averages, volatility, mean reversion)
2. **Inputs per agent:** price history (365 days) + news. Computed technical indicators are included as part of the data package (builder's call, needed for the technical/quant personas).
3. **Horizons:** +1 day, +1 week, +1 month — one prediction per horizon per agent, all three in a single LLM call.
4. **Chart form:** the approved option B — thick average line + gray min–max band, not 11 individual lines.
5. **Report layout:** the approved option A — one page, stacked sections; **sorted by average predicted % gain at +1 month, descending** (the approved metric); each section header shows a "średni zysk" badge displaying that same +1-month average gain — **green when positive, red when negative**.
6. **Table under the chart:** rows = 10 agents + average; columns = +1D / +1T / +1M prices; each agent row carries its **one-line justification** (approved).
7. **Scope of instruments:** whole watchlist (3 stocks), whole report at once.
8. **Output:** HTML report opened in the browser, like Project 2.
9. **Approved mockups** from the brainstorming session are captured in `docs/superpowers/specs/2026-10-27-agent-predykcje-mockups/` (chart option B, layout option A, sort-metric options); the report must match them. The mockups show only positive-gain examples; negative gains use the red badge per decision 5.
10. **Curriculum:** this project **replaces the planned "devlog" (custom skill + hooks) as learning-path Project 3**; the devlog project is dropped from the curriculum (approved 2026-10-27).

## 7. Left to the Builder

- Persona YAML details (life histories, biases, writing style) drafted to match the ten approved archetypes
- Prompt design: how price history, indicators, index context and news are packaged per call within a reasonable token budget
- Parallelism of the 30 calls (concurrency, rate-limit handling, retries — reuse Project 2's error-handling patterns)
- Structured-output validation: JSON schema + sanity checks on predicted prices (e.g., reject absurd values, re-prompt or mark failed)
- Graceful degradation: a failed agent call is marked "brak danych" in the table; average and band use successful agents only
- Exact HTML/CSS and plotly styling matching the approved mockups
- Default model for the config (cost-sensitive; 30 calls per run)
