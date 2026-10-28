# agent-predykcje: screening sWIG80 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozszerzyć agent-predykcje o screening techniczny pełnego składu sWIG80: 80 spółek → deterministyczny scoring 8 sygnałów → top 10 → pełna predykcja agentowa (100 zapytań LLM) → raport z rankingiem screena.

**Architecture:** Nowy, czysty moduł `screen.py` liczy 8 sygnałów wzrostowych z ramek (date, close) i wybiera top 10 z deterministycznym tie-breakiem. `config.py` uczy się sekcji `swig80` (dane już zacommittowane na masterze — commit b129d1f). CLI dostaje tryb `--universe` (domyślnie `swig80`); snapshot zyskuje opcjonalną sekcję `screen`, którą raport renderuje pod sekcjami spółek. Skrypt `scripts/refresh_swig80.py` odświeża skład z oficjalnego PDF GPW Benchmark.

**Tech Stack:** Python 3.12, pandas, yaml, pypdf (dev-only), pytest, black — istniejący projekt `projects/agent-predykcje/`.

**Spec:** `docs/superpowers/specs/2026-10-28-agent-predykcje-swig80-design.md`

## Global Constraints

- Praca w świeżym worktree utworzonym z `master` (min. commit `b129d1f` — zawiera sekcję `swig80` w watchliście, indeks kontekstowy `SWIG80.WA` (zweryfikowany na Yahoo) i artefakty recon w `docs/superpowers/recon/swig80-2026-10-28/`).
- venv per worktree: `python -m venv .venv` + `.venv/Scripts/python.exe -m pip install -e ".[dev]"` (katalog `projects/agent-predykcje/`).
- Testy: `.venv/Scripts/python.exe -m pytest` z katalogu projektu (addopts wyklucza `-m live`).
- Black na każdym commicie; jeden commit na task; każdy commit kończy się linią `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- Teksty UI po polsku; polskie komunikaty błędów (bez surowych tracebacków).
- Screening: próg **64 sesji**, **8 sygnałów** (sygnał 8 = close > SMA20 + 2σ), tie-break **3M → 1M → symbol**, pełna deterministyczność.
- Budżet LLM: pełny `analyze` = 10 spółek × 10 person = 100 zapytań; live smoke = 3 spółki przez env `AGENT_PREDYKCJE_LIVE_STOCKS` (30 zapytań).
- Nigdy nie derywować symbolu Yahoo z tickera GPW — wyjątki zapisane wprost w `watchlist.yaml` (ATAL=`1AT.WA`, HUUUGE=`HUG.WA`, MEDINICE=`ICE.WA`, SYN2BIO=`S2B.WA`, CREOTECH=`CRQ.WA`, GREENX=`GRX.WA`).
- Nowa zależność runtime: żadna. `pypdf>=5.0` tylko w dev extras (Task 6).

## Review Focus

1. **RSI dokładnie 50 lub 70** — sygnał `rsi_between_50_70` musi być False na granicach (przedział otwarty); seria płaska (RSI 50) nie może dostać punktu. → Task 2: `test_score_frame_rsi_boundaries`.
2. **Remis w score** — kolejność musi zależeć od zwrotu 3M, potem 1M, potem symbolu; dwa identyczne wejścia dają identyczny wynik. → Task 2: `test_screen_universe_selection_and_order`, `test_screen_universe_tie_break`.
3. **Rama krótsza niż 64 sesje** — spółka wykluczona z powodem, nigdy NaN w tie-breaku. → Task 2: `test_screen_universe_exclusions` (przypadek 63 wierszy).
4. **Snapshot bez sekcji `screen`** (tryb watchlist / stare migawki) — raport renderuje się jak dotychczas, bez tabeli screena. → Task 4: `test_legacy_snapshot_without_screen`.
5. **Wpis `skipped` (NIEWIADOW)** — `collect` nigdy nie pobiera takiego symbolu (Yahoo 404), a screening pokazuje go z powodem. → Task 1: `test_all_symbols_includes_swig80`; Task 2: `test_screen_universe_exclusions`.
6. **Brak lokalnego CSV przy `analyze`** — spółka trafia do screena jako wykluczona z powodem „brak danych lokalnych", nie wywraca runu. → Task 2: `test_screen_universe_exclusions`.

---

### Task 1: Sekcja swig80 w config

**Files:**
- Modify: `src/agent_predykcje/config.py` (funkcje `all_symbols`, nowa `swig80_entries`)
- Test: `tests/test_config.py`
- (Dane `watchlist.yaml` już na masterze — bez zmian.)

**Interfaces:**
- Consumes: `watchlist.yaml` z sekcjami `stocks`, `indices`, `swig80` (wpisy: `{symbol, ticker, name, isin}`; NIEWIADOW: `{symbol: null, skipped: true, reason}`).
- Produces: `all_symbols(watchlist) -> list[dict]` (wpisy `{symbol, kind}`; sekcja `swig80` → kind `"stock"`, pomija wpisy `skipped` lub `symbol: null`); `swig80_entries(watchlist) -> list[dict]` (surowe wpisy sekcji, razem ze `skipped`).

- [ ] **Step 1: Konfiguracja środowiska**

Utwórz worktree z `master` (superpowers:using-git-worktrees), potem w `projects/agent-predykcje/`: `python -m venv .venv` i `.venv/Scripts/python.exe -m pip install -e ".[dev]"`.
Verify: `.venv/Scripts/python.exe -m pytest -q` → 63 passed.

- [ ] **Step 2: Write the failing test**

```python
def test_all_symbols_includes_swig80():
    wl = {"stocks": ["PKO.WA"], "indices": ["WIG20.WA"],
          "swig80": [{"symbol": "CMP.WA"}, {"symbol": None, "skipped": True}]}
    symbols = [i["symbol"] for i in all_symbols(wl)]
    assert "CMP.WA" in symbols
    kinds = {i["symbol"]: i["kind"] for i in all_symbols(wl)}
    assert kinds["CMP.WA"] == "stock"

def test_swig80_entries_returns_full_section():
    skipped = {"symbol": None, "skipped": True, "reason": "brak notowania"}
    wl = {"swig80": [{"symbol": "CMP.WA"}, skipped]}
    assert swig80_entries(wl) == [{"symbol": "CMP.WA"}, skipped]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q`
Expected: FAIL — `swig80_entries` nie istnieje; `all_symbols` ignoruje `swig80`.

- [ ] **Step 4: Implement in `config.py`**

`all_symbols`: dopisz sekcję `swig80` do pętli (kind `"stock"`, wpis to dict — pomiń gdy `skipped` truthy lub `symbol` jest None). `swig80_entries(watchlist) -> list[dict]`: zwróć `watchlist.get("swig80", []) or []` bez filtrowania. Zaktualizuj docstring `load_watchlist`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_collector.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_predykcje/config.py tests/test_config.py
git commit -m "feat(agent-predykcje): support swig80 section in watchlist config

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 2: Moduł screen.py — wskaźniki, scoring, wybór top 10

**Files:**
- Create: `src/agent_predykcje/screen.py`
- Test: `tests/test_screen.py` (nowy)

**Interfaces:**
- Consumes: ramka `pd.DataFrame` z kolumnami `date`, `close` (oldest→newest), lista wpisów z `config.swig80_entries`.
- Produces:
  - `score_frame(df: pd.DataFrame) -> dict | None` — `None` gdy `len(df) < 64`; inaczej `{"signals": {...8 bool...}, "score": int, "return_1m": float, "return_3m": float}`. Nazwy sygnałów: `price_above_sma20`, `price_above_sma50`, `sma20_above_sma50`, `macd_above_signal`, `rsi_between_50_70`, `return_1m_positive`, `return_3m_positive`, `price_above_bollinger_upper`.
  - `screen_universe(entries: list[dict], frames: dict[str, pd.DataFrame]) -> dict` — `{"rows": [row...], "selected": [symbol...], "skipped": [symbol...]}`. Row: `{"symbol", "name", "score", "signals", "return_1m", "return_3m", "selected": bool, "reason": str | None}`. Kolejność rows: najpierw spółki ze score (sort: score desc, `return_3m` desc, `return_1m` desc, symbol asc), potem wykluczone (sort: symbol asc) z `score=None` i `reason`: wpis `skipped` → `reason` z YAML; brak ramki → `"brak danych lokalnych"`; ramka <64 wierszy → `"za mało sesji (<64)"`. `selected` = pierwsze 10 symboli ze score (jeśli mniej niż 10, wszystkie ze score).

Wzory (standardowe definicje): SMA = `close.rolling(w).mean()`; MACD(12,26,9) na EMA (`ewm(span=...)`); RSI(14) jak `signals._rsi14` (rolling-mean zysków/strat); Bollinger górny = SMA20 + 2·std(20) z `ddof=0`; zwroty: `_returns`-style z 21 i 63 sesji (ostatnia vs N sesji wstecz, NaN gdy za mało danych).

- [ ] **Step 1: Write the failing tests**

```python
def test_score_frame_uptrend():
    # 99 dni rosnących 100..198 + skok ostatniego dnia do 250
    # (liniowy ramp NIE przebija SMA20+2σ — wstęga wymaga outliera);
    # → wszystkie sygnały True oprócz RSI (RSI = 100 przy samych wzrostach)
    df = pd.DataFrame({"date": [...], "close": [...]})
    s = score_frame(df)
    assert s["signals"]["price_above_sma20"] is True
    assert s["signals"]["price_above_sma50"] is True
    assert s["signals"]["sma20_above_sma50"] is True
    assert s["signals"]["macd_above_signal"] is True
    assert s["signals"]["return_1m_positive"] is True
    assert s["signals"]["return_3m_positive"] is True
    assert s["signals"]["price_above_bollinger_upper"] is True
    assert s["signals"]["rsi_between_50_70"] is False  # RSI = 100
    assert s["score"] == 7

def test_score_frame_downtrend():
    # 100 malejących closes: 199, 198, ..., 100 → wszystkie sygnały False, score 0
    ...

def test_score_frame_insufficient_history():
    assert score_frame(df_63_rows) is None
    assert score_frame(df_64_rows) is not None

def test_score_frame_rsi_boundaries():
    # płaska seria (RSI = 50) → rsi_between_50_70 False
    # seria naprzemienna +4/-2 (ag/al = 2 → RSI = 66,7) → True
    # seria naprzemienna +7/-3 (ag/al = 7/3 → RSI = 70 dokładnie) → False
    ...

def test_screen_universe_selection_and_order():
    # A: score 8, return_3m 0.10; B: score 8, return_3m 0.20; C: score 5
    # → rows[0] = B, rows[1] = A; selected == [B, A]; C nie wybrane

def test_screen_universe_tie_break():
    # A i B: score 8, return_3m równy; A return_1m wyższy → A przed B
    # C i D: score, 3M, 1M identyczne → porządek alfabetyczny symboli

def test_screen_universe_exclusions():
    # wpis skipped → reason z YAML; wpis bez ramki → "brak danych lokalnych";
    # ramka 63 wierszy → "za mało sesji (<64)"; wszystkie na końcu rows,
    # score None, nie w selected

def test_screen_universe_deterministic():
    # dwa wywołania z tymi samymi danymi → identyczne rows i selected
```

Fixtures ramek: funkcja pomocnicza w pliku testowym budująca `pd.DataFrame({"date": [...], "close": [...]})` (daty rosnące, 100 wierszy).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_screen.py -q`
Expected: FAIL — brak modułu `screen`.

- [ ] **Step 3: Implement `screen.py`**

Czyste funkcje, zero I/O, docstring po polsku. `score_frame` liczy wskaźniki i 8 booli; `screen_universe` mapuje wpisy na ramki, sortuje z kluczem `(score is None, -score, -return_3m, -return_1m, symbol)` dla części ze score i `(True, symbol)` dla wykluczonych (docelowo: wykluczone zawsze za punktowanymi), `selected` = symbole 10 pierwszych wierszy ze score.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_predykcje/screen.py tests/test_screen.py
git commit -m "feat(agent-predykcje): add deterministic sWIG80 screen with 8-signal scoring

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 3: CLI — tryb --universe, env override, sekcja screen w snapshotcie

**Files:**
- Modify: `src/agent_predykcje/pipeline.py` (sygnatura `run_analysis`), `src/agent_predykcje/cli.py`
- Test: `tests/test_pipeline.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `screen.screen_universe`, `config.swig80_entries`, `pipeline.load_price_frame`.
- Produces: `run_analysis(watchlist, data_dir, personas_dir, client=None, model=None, max_workers=5, stocks: list[str] | None = None) -> dict` — `stocks=None` → dotychczasowe `watchlist["stocks"]`; `stocks=[...]` → predykcje dokładnie dla tych symboli. Snapshot po swig80: `snapshot["screen"]` = wynik `screen_universe` (słownik z Task 2).

- [ ] **Step 1: Write the failing tests (pipeline)**

```python
def test_run_analysis_custom_stocks():
    # fake client jak w istniejących testach test_pipeline.py;
    # watchlist z pustym "stocks", wywołanie z stocks=["PKO.WA"]
    # → snapshot["stocks"] ma 1 wpis z anchor (ramka z tmp data_dir)
```

- [ ] **Step 2: Write the failing tests (cli)**

```python
def test_analyze_swig80_default_uses_screen(monkeypatch):
    # monkeypatch: cli.load_price_frame (zwraca ramkę), cli.screen_universe
    # (zwraca {"rows": [], "selected": ["CMP.WA"], "skipped": []}),
    # cli.run_analysis (capture stocks kwarg; zwraca {"stocks": [], ...})
    # cli.main(["analyze"]) == 0; run_analysis dostał stocks=["CMP.WA"];
    # save_snapshot dostał snapshot z kluczem "screen"

def test_analyze_watchlist_mode_legacy(monkeypatch):
    # monkeypatch cli.run_analysis; cli.main(["analyze", "--universe", "watchlist"])
    # → stocks=None (lub watchlist stocks), snapshot bez "screen"

def test_env_override_forces_stocks(monkeypatch):
    # monkeypatch.setenv("AGENT_PREDYKCJE_LIVE_STOCKS", "PKO.WA,PZU.WA");
    # monkeypatch cli.run_analysis; cli.main(["analyze"]) → stocks == ["PKO.WA", "PZU.WA"]
```

Uwaga: `cmd_analyze` musi importować `load_price_frame` i `screen_universe` do namespace'u `cli`, żeby dało się je monkeypatchować (`from agent_predykcje.pipeline import load_price_frame`, `from agent_predykcje.screen import screen_universe`).

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli.py -q -k "analyze or env"`
Expected: FAIL (brak parametru `stocks`, brak `--universe`).

- [ ] **Step 4: Implement**

`pipeline.run_analysis`: parametr `stocks=None`; pętla po `stocks if stocks is not None else watchlist.get("stocks", [])`. `cli`: dodaj `--universe {swig80,watchlist}` (default `swig80`) do parserów `analyze` i `run`; w `cmd_analyze`: env `AGENT_PREDYKCJE_LIVE_STOCKS` (rozdzielenie po przecinku) nadpisuje listę; tryb `swig80` → ramki z `load_price_frame` (FileNotFoundError → brak wpisu w `frames`), `screen_universe(swig80_entries(watchlist), frames)`, `snapshot["screen"] = result`, `stocks = result["selected"]`; komunikat podsumowania przed zapisem: `print(f"Screening: wybrano {len(result['selected'])} spółek z {len(result['rows'])} pozycji.")`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli.py tests/test_pipeline.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_predykcje/cli.py src/agent_predykcje/pipeline.py tests/test_cli.py tests/test_pipeline.py
git commit -m "feat(agent-predykcje): add --universe mode with sWIG80 screen and live-stock env override

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 4: Raport — tabela screena

**Files:**
- Modify: `src/agent_predykcje/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `snapshot["screen"]` (słownik z Task 2).
- Produces: `_screen_table(screen: dict) -> str` (HTML); `render_report` dopisuje ją po sekcjach spółek, gdy `snapshot.get("screen")` jest truthy.

- [ ] **Step 1: Write the failing tests**

```python
def test_screen_section_renders_when_present():
    # snapshot: 1 spółka + screen z 3 wierszami: wybrany (wszystkie sygnały True),
    # niewybrany (score 3), wykluczony (score None, reason "za mało sesji (<64)")
    # → html zawiera: "<h2>Screening sWIG80", symbol wiersza, "✓", "✗",
    #   reason wykluczonego, "Score", "Powód"

def test_legacy_snapshot_without_screen():
    # snapshot bez "screen" → w html nie ma "Screening sWIG80"

def test_screen_section_escapes_html():
    # name wiersza: "<script>alert(1)</script>" → w html jako &lt;script&gt;
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report.py -q`
Expected: FAIL (brak sekcji screena).

- [ ] **Step 3: Implement**

`_screen_table(screen)`: `<h2>Screening sWIG80 — ranking spółek</h2>` + tabela z nagłówkami: `Wybrane`, `Symbol`, `Nazwa`, `Score`, `SMA20`, `SMA50`, `20>50`, `MACD`, `RSI`, `1M`, `3M`, `Boll.`, `Zwrot 1M`, `Zwrot 3M`, `Powód`. Komórki sygnałów: `✓`/`✗`, wykluczone `—`; zwroty jako `+12,3%` (format `f"{v*100:+.1f}"` z kropką→przecinek); `selected` jako `✓`/puste; wszystko przez `html.escape`. Wiersze w kolejności z `screen["rows"]`. W `render_report`: po pętli sekcji spółek, `if snapshot.get("screen"): parts.append(_screen_table(snapshot["screen"]))`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_report.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_predykcje/report.py tests/test_report.py
git commit -m "feat(agent-predykcje): render sWIG80 screen ranking table in report

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 5: Live smoke — env override i sekcja screen

**Files:**
- Modify: `tests/test_live.py`
- (Bez zmian w kodzie produkcyjnym.)

- [ ] **Step 1: Update the smoke test**

W `test_full_run_smoke`: przed wywołaniami `cli.main` dodaj `monkeypatch.setenv("AGENT_PREDYKCJE_LIVE_STOCKS", "PKO.WA,PZU.WA,PKN.WA")`. Po wczytaniu snapshota dodaj asercje: `assert len(snapshot["stocks"]) == 3` (gwarancja 30 zapytań) i `assert snapshot.get("screen")` (screening policzony i zapisany). Zaktualizuj docstring (smoke = pełny fetch + screening, 30 zapytań LLM).

- [ ] **Step 2: Run the default suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (test_live pozostaje wykluczony — faktyczny smoke do odpalenia ręcznie po merge'u: `.venv/Scripts/python.exe -m pytest -m live`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_live.py
git commit -m "test(agent-predykcje): live smoke pins 3-stock override and screen section

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 6: Skrypt refresh_swig80.py — parser PDF i aktualizacja watchlisty

**Files:**
- Create: `scripts/refresh_swig80.py`, `tests/test_refresh_swig80.py`
- Modify: `pyproject.toml` (dev extras: `pypdf>=5.0`)

**Interfaces:**
- Consumes: PDF GPW Benchmark (fixture: `docs/superpowers/recon/swig80-2026-10-28/Portfele_WIG20_mWIG40_sWIG80_WIG30_2026_09_03.pdf`; w testach ścieżka `Path(__file__).resolve().parents[3] / "docs/superpowers/recon/swig80-2026-10-28/Portfele_WIG20_mWIG40_sWIG80_WIG30_2026_09_03.pdf"`).
- Produces:
  - `parse_portfolio_pdf(pdf_path) -> list[dict]` — 80 wpisów `{isin, kod, name}` (name = token z PDF, best-effort); tylko strony z nagłówkiem zawierającym `sWIG80`; pomija listę rezerwową (wiersze bez kolumny kursu/wagi).
  - `update_entries(parsed: list[dict], existing: list[dict]) -> list[dict]` — match po `isin`: istniejące zachowują `symbol`, `name`, `ticker`; nowe → `{symbol: None, ticker: None, name: kod, isin, needs_symbol_verification: True}`; brakujące w parsed → usunięte. Kolejność wg parsed.
  - `main(argv)` — argparse: `--pdf PATH` | `--url URL` (pobranie urllib do temp), `--watchlist PATH` (default: `watchlist.yaml` obok skryptu, tj. `projects/agent-predykcje/watchlist.yaml`); ładuje YAML, podmienia sekcję `swig80`, zapisuje z zachowaniem nagłówkowego komentarza i sekcji `stocks`/`indices`; polskie błędy, exit 0/1.

- [ ] **Step 1: Dodaj `pypdf>=5.0` do dev extras w pyproject.toml i doinstaluj**

`.venv/Scripts/python.exe -m pip install -e ".[dev]"`.

- [ ] **Step 2: Write the failing tests**

```python
PDF = Path(__file__).resolve().parents[3] / "docs/superpowers/recon/swig80-2026-10-28/Portfele_WIG20_mWIG40_sWIG80_WIG30_2026_09_03.pdf"

def test_parse_returns_80_rows():
    rows = parse_portfolio_pdf(PDF)
    assert len(rows) == 80
    isins = {r["isin"] for r in rows}
    assert "US44853H1086" in isins  # HUUUGE
    assert "AU0000198939" in isins  # GREENX
    assert "NL0000686509" in isins  # ASTARTA
    assert "LU0607203980" in isins  # IMCOMPANY

def test_parse_ignores_reserve_list():
    isins = {r["isin"] for r in parse_portfolio_pdf(PDF)}
    assert "PLPSSUS00018" not in isins  # PASSUS z listy rezerwowej
    assert "PLWTCHN00030" not in isins  # WITTCHEN z listy rezerwowej

def test_update_keeps_existing_symbols():
    # existing: {isin X, symbol "X.WA", name "X SA"}; parsed: {isin X, kod "X"}
    # → wynik zachowuje symbol "X.WA" i name "X SA"

def test_update_flags_new_and_drops_removed():
    # parsed ma nowy isin Y i nie ma Z → Y: needs_symbol_verification True,
    # symbol None; Z znika z wyniku

def test_main_writes_watchlist(tmp_path):
    # --pdf PDF --watchlist tmp/watchlist.yaml (z sekcją stocks i komentarzem)
    # → zapisany YAML ma swig80 z 80 wpisami, stocks bez zmian, komentarz na górze
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_refresh_swig80.py -q`
Expected: FAIL (brak skryptu).

- [ ] **Step 4: Implement `scripts/refresh_swig80.py`**

Parser: `pypdf.PdfReader`, wybór stron po nagłówku `sWIG80`, regex na wiersze `^(\d{1,2})\s+([A-Z]{2}[A-Z0-9]{10})\s+([A-Z0-9.]+)\s+([\d,]+)\s+([\d ]+)\s+(\d+,\d+)` (wiersze rezerwowe nie mają kursu i wagi, więc regex ich nie złapie). Skrypt samodzielny (stdlib + pypdf + yaml), `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_refresh_swig80.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/refresh_swig80.py tests/test_refresh_swig80.py pyproject.toml
git commit -m "feat(agent-predykcje): add sWIG80 watchlist refresh script with PDF parser

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Task 7: README i pełna weryfikacja

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Zaktualizuj README**

Dodaj: tryb `swig80` (domyślny) vs `--universe watchlist`; opis screeningu (8 sygnałów, próg 64 sesji, tie-break, top 10, ~100 zapytań/run); env `AGENT_PREDYKCJE_LIVE_STOCKS` dla smoke; sekcję skryptu `scripts/refresh_swig80.py` (użycie `--pdf`/`--url`, polityka `needs_symbol_verification`); notkę o NIEWIADOW (pominięty, brak notowania Yahoo) i 6 wyjątkach symboli.

- [ ] **Step 2: Pełna weryfikacja**

Run: `.venv/Scripts/python.exe -m pytest -q` → oczekiwane: wszystkie przechodzą (63 dotychczasowe + nowe).
Run: `.venv/Scripts/python.exe -m black --check src tests scripts` → oczekiwane: bez zmian do sformatowania.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(agent-predykcje): document swig80 mode, screening and refresh script

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

### Po implementacji (poza zadaniami)

- Manualny live smoke w worktree: `.venv/Scripts/python.exe -m pytest -m live` (sieć + 30 zapytań, wymaga `ant auth login`/`ANTHROPIC_API_KEY`).
- Pełny run produkcyjny: `.venv/Scripts/python.exe -m agent_predykcje run` (100 zapytań, ~10 min) — decyzja użytkownika.
- Merge do master + push, usunięcie starego worktree `agent-predykcje` (po przeniesieniu design docu — już na masterze).
