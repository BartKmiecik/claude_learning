# Design: agent-predykcje — rozszerzenie o screening sWIG80

**Data:** 2026-10-28
**Status:** do zatwierdzenia (design doc)
**Bazuje na:** agent-predykcje, branch `agent-predykcje` / PR #1 (po merge'u do `master`)

## Intent i dlaczego

Użytkownik chce z jednego rozszerzenia dwóch rzeczy: (1) zobaczyć, jak pipeline predykcyjny zachowuje się w skali całego indeksu (80 spółek), oraz (2) czytać przewidywania dla najciekawszych małych spółek z GPW. Pełna skala (80 spółek × 10 agentów = 800 zapytań LLM) to ~27× obecnego kosztu i czasu (~1,5 h/run), więc projekt wprowadza deterministyczny pre-screening: tanie wskaźniki techniczne wybierają 10 spółek, na które wydajemy budżet LLM (100 zapytań, ~10 min/run).

## Cele

1. Watchlista rozszerza się do pełnego składu sWIG80 (80 spółek), z możliwością odświeżenia z oficjalnego pliku GPW Benchmark.
2. Nowy etap screeningu: deterministyczny scoring wskaźników technicznych dla wszystkich 80 spółek; top 10 przechodzi do predykcji agentowych.
3. Raport otwiera się rankingiem przewidywanego potencjału wzrostu dla top 10 (istniejąca sekcja per spółka), a poniżej pokazuje pełną tabelę screena wszystkich 80 — z wynikami per wskaźnik — żeby było widać, co odpadło i dlaczego.
4. Odporność: spółki bez danych cenowych są pomijane z ostrzeżeniem, nie wywracają runu.

## Nie-cele

- Brak analizy fundamentalnej (decyzja użytkownika).
- Brak predykcji dla wszystkich 80 spółek.
- Brak zmian w zestawie person / formacie predykcji per spółka.
- Brak sygnałów handlowych — format raportu pozostaje edukacyjno-analityczny.

## Anty-cele (porażka, nawet jeśli technicznie działa)

- Run kosztujący >~3 USD lub trwający >~20 min (np. przez przypadkowe skalowanie zapytań LLM poza top 10).
- Screening, którego wyniku nie da się odtworzyć (niedeterministyczny lub zależny od kolejności danych).

## Ograniczenia

- Python 3.12; bez nowych ciężkich zależności; do odświeżania składu `pypdf` (zweryfikowany w recon), do pobierania danych istniejący fetcher (urllib/requests).
- Dane cenowe wyłącznie z Yahoo chart API v8. Źródła fundamentów odpadły (bot-gated — zweryfikowane w recon).
- gpwbenchmark.pl blokuje bezpośrednie pobieranie z maszyny deweloperskiej (connection reset); skrypt odświeżania musi wspierać pobranie PDF przez mirror PAP Biznes lub podanie ścieżki do pliku ręcznie.
- Runtime LLM: 100 zapytań, model domyślny `claude-opus-5-5` (override `AGENT_PREDYKCJE_MODEL`), styl SDK 2.x `client.messages.create` (bug live-only już naprawiony w PR #1).
- Konwencje repo: venv, TDD, black hook, jeden commit na task.

## Skład sWIG80 — ustalenia z recon

- Źródło: oficjalny PDF GPW Benchmark `Portfele_WIG20_mWIG40_sWIG80_WIG30_YYYY_MM_DD.pdf` (komunikaty indeksowe). Stan: po korekcie kwartalnej 18.09.2026 (weszli: NIEWIADOW, SYN2BIO; wyszli: ERBUD, WITTCHEN). PDF zawiera też listę rezerwową (8 spółek) — pomijamy ją w składzie aktywnym.
- **Dane składu są już zebrane** — artefakty recon w `docs/superpowers/recon/swig80-2026-10-28/` (staged w starym worktree; przenieść do nowego w tasku 1):
  - `Portfele_WIG20_mWIG40_sWIG80_WIG30_2026_09_03.pdf` — oficjalny PDF (fixture do testów parsera),
  - `rows.json` — 80 wierszy {nr, isin, kod z PDF},
  - `chart_probe.json` — wynik sondowania chart API: per wiersz trafiony symbol Yahoo + nazwa spółki z meta + cena (weryfikacja pokrycia),
  - `mapping.json` — kandydaci z Yahoo search per wiersz.
  - ISIN-y i kody GPW pochodzą z tego PDF-u; symbol Yahoo to wynik sondowania (nie derywacja z tickera GPW — 6 wyjątków udokumentowanych niżej).
- Pokrycie Yahoo: **79/80** spółek ma dane chart API (zweryfikowane per spółka po nazwie). **NIEWIADOW** nie ma notowania na WSE w Yahoo (tylko FRA `071.F`) — pomijany z ostrzeżeniem; wpis zostaje w YAML z polem `skipped: true` i powodem.
- Pułapki symboli Yahoo ≠ ticker GPW (zapisane wprost w watchliście): ATAL=`1AT.WA`, HUUUGE=`HUG.WA`, MEDINICE=`ICE.WA`, SYN2BIO=`S2B.WA`, CREOTECH=`CRQ.WA`, GREENX=`GRX.WA`.

## Przepływ runu (po zmianie)

1. **Skład wszechświata** — `watchlist.yaml` dostaje sekcję `swig80`: 80 wpisów `{gpw_ticker, yahoo_symbol, isin, name}` (statyczny plik w repo; odświeżany skryptem `scripts/refresh_swig80.py` przy rewizjach kwartalnych). Sekcje `stocks:` (3 spółki legacy) i `indices:` zostają — `collect` pobiera sumę wszystkich symboli (stocks + indices + swig80), a `analyze` w trybie swig80 predykuje wyłącznie top 10 ze screena; 3 spółki legacy służą live smoke'owi (przez `AGENT_PREDYKCJE_LIVE_STOCKS`).
2. **Pobranie danych** — istniejący fetcher Yahoo, jeden przebieg po wszystkich symbolach; brak danych → skip + ostrzeżenie.
3. **Screening** (nowy moduł, deterministyczny, zero LLM) — dla każdej spółki z dziennych świec:
   - SMA20, SMA50, MACD(12,26,9), RSI(14), Bollinger(20,2), zwroty 1M i 3M (close vs N sesji wstecz).
   - Score = suma sygnałów wzrostowych (każdy +1, max 8):
     1. close > SMA20
     2. close > SMA50
     3. SMA20 > SMA50
     4. linia MACD > linia sygnału
     5. 50 < RSI(14) < 70
     6. zwrot 1M > 0
     7. zwrot 3M > 0
     8. close > górna wstęga Bollingera (SMA20 + 2σ) — breakout
   - Tie-break: zwrot 3M, potem 1M, potem symbol (alfabetycznie) — pełna deterministyczność.
   - Wymagane ≥64 sesji historii (3M return liczymy z 63 sesji wstecz — przy 60-63 sesjach zwrot 3M byłby NaN, co psułoby tie-break); inaczej spółka wykluczona z powodem.
4. **Wybór top 10** — 10 najwyższych score'ów.
5. **Predykcja** — istniejące 10 person × 3 horyzonty na wybranych 10 spółkach (100 zapytań).
6. **Raport** — istniejący HTML plus:
   - sekcja 1: ranking top 10 po przewidywanym wzroście +1M (istniejące sekcje per spółka, niezmienione),
   - nowa sekcja 2: tabela screena dla wszystkich 80 (ranking, symbol, nazwa, score, pass/fail per wskaźnik, zwroty 1M/3M; top 10 oznaczone; pominięte z powodami).
7. **Live smoke** — `pytest -m live`: pełny fetch + screening (darmowe), predykcje tylko na starym podzbiorze 3 spółek przez env `AGENT_PREDYKCJE_LIVE_STOCKS=PKO.WA,PZU.WA,PKN.WA` (30 zapytań, ~3 min). Pełny run top-10 to normalne wywołanie `analyze`.

## Decyzje użytkownika (zatwierdzone)

- Rozszerzenie do pełnego sWIG80; deterministyczny wybór 10; pełna predykcja tylko na nich.
- Scoring screena dokładnie jak wyżej (8 sygnałów, suma punktów).
- Sygnał 8 (po wykryciu w review, że "górna połowa wstęgi" = SMA20 = duplikat sygnału 1): **close > górna wstęga Bollingera (SMA20 + 2σ)** — decyzja usera z 2026-10-28.
- Raport: ranking przewidywanego wzrostu top 10 na otwarciu; tabela screena dla 80 poniżej.
- Analiza fundamentalna całkowicie pominięta.

## Decyzje moje (do sprawdzenia przy czytaniu)

- Źródło składu: oficjalny PDF GPW Benchmark, zapisany jako statyczny YAML + skrypt odświeżania (uruchamiany ręcznie przy rewizjach; auto-pobranie z mirrora PAP best-effort).
- **Skrypt odświeżania jest wymaganym deliverable** (cel 1): `scripts/refresh_swig80.py` z testami parsera (TDD) opartymi na zacommitowanym fixturze — prawdziwym PDF z `docs/superpowers/recon/swig80-2026-10-28/`. Interfejs: ścieżka do PDF lub `--url` (bez hardkodowania mirrora — adresy PAP się zmieniają; user podaje). Polityka refreshu: dodaje/usuwa wpisy względem PDF, **zachowuje** istniejące `yahoo_symbol` (nigdy nie derywuje symbolu z tickera — 6 znanych wyjątków), nowe wpisy oznacza flagą `needs_symbol_verification` i nie włącza ich do kolekcji dopóki symbol nie zostanie zweryfikowany. `pypdf` jako zależność deweloperska skryptu.
- Niewiadów: pomijany z ostrzeżeniem, bez źródła zastępczego; wpis zostaje w YAML z `skipped: true`.
- Kontekst indeksowy dla person: istniejące 3 indeksy (WIG20, WIG, mWIG40) + dołożenie SWIG80.WA, jeśli dostępny na Yahoo (zweryfikować przy implementacji).
- Nowy moduł `src/agent_predykcje/screen.py` — czyste funkcje, testy jednostkowe (TDD), konwencje repo.
- Watchlista: sekcje `stocks:` i `indices:` zostają (legacy + smoke); `collect` pobiera sumę wszystkich symboli.
- Próg historii podniesiony do 64 sesji (zwrot 3M liczony z 63 sesji wstecz — inaczej NaN w tie-breaku).
- Nowa gałąź po merge'u PR #1, praca w świeżym worktree, jeden commit na task.

## Zostawione builderowi

- Dokładne wzory wskaźników wg standardowych definicji (SMA/MACD/RSI/Bollinger), czyste funkcje nad close/volume.
- Szczegóły layoutu raportu w ramach struktury dwusekcyjnej.
- Macierz testów (scoring, tie-breaki, braki danych, deterministyczność).
