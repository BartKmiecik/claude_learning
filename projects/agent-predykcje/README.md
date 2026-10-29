# agent-predykcje

Projekt szkoleniowy: dziesięciu agentów LLM, każdy z inną osobowością,
przewiduje ceny akcji z GPW w trzech horyzontach (1 dzień, 1 tydzień, 1 miesiąc).

## Co robi

- `collect` — pobiera 12 miesięcy notowań z Yahoo Finance (spółki i indeksy
  z `watchlist.yaml`, w tym sekcję `swig80`) oraz nagłówki RSS do `data/`,
- `analyze` — domyślnie przeprowadza screening sWIG80 i uruchamia około 100
  wywołań LLM (10 person × 10 wybranych spółek); z `--universe watchlist`
  analizuje spółki z sekcji `stocks` (obecnie 3 spółki, 30 wywołań); wynik
  zapisuje jako migawkę w `predictions/`,
- `report` — generuje samodzielny raport HTML `report/raport.html` i otwiera go
  w przeglądarce; ranking screeningu z migawki trafia do sekcji
  „Screening sWIG80 — ranking spółek”,
- `run` — wywołuje po kolei `collect`, `analyze` i `report`.

## Dziesięć person

Wieczny niedźwiedź, Wieczny byk, Kontrarianin, Rentier dywidendowy,
Makroekonomista, Trader momentum, Analityk newsowy, Statystyk-quant,
Analityk techniczny, Fundamentalista wartościowy.
Osobowości są edytowalne — wystarczy zmienić pliki w `personas/`.

## Użycie

```
agent-predykcje collect
agent-predykcje analyze [--model MODEL] [--universe {swig80,watchlist}]
agent-predykcje report [--snapshot predictions/predictions-*.json]
agent-predykcje run [--model MODEL] [--universe {swig80,watchlist}]
```

## Uniwersum analizy

`analyze` i `run` przyjmują `--universe`:

- `swig80` (domyślnie) — screening sWIG80 wybiera 10 spółek do analizy,
- `watchlist` — analizowane są spółki z sekcji `stocks` w `watchlist.yaml`
  (obecnie 3 spółki, 30 wywołań LLM zamiast około 100).

Screening jest deterministyczny i liczy dla każdej spółki z sekcji `swig80`
8 sygnałów wzrostowych na podstawie notowań z `data/`:

- cena > SMA20,
- cena > SMA50,
- SMA20 > SMA50,
- MACD > linia sygnału,
- RSI(14) między 50 a 70,
- zwrot 1M > 0,
- zwrot 3M > 0,
- cena > górna wstęga Bollingera (SMA20 + 2σ).

Spółki z historią krótszą niż 64 sesje, bez danych lokalnych lub oznaczone
`skipped: true` są pomijane z powodem w rankingu. Sortowanie: liczba sygnałów
malejąco, przy remisie zwrot 3M, potem 1M, na końcu symbol rosnąco (wykluczone
na końcu). Top 10 (a gdy mniej punktowanych — wszystkie) trafia do analizy;
pełny ranking jest zapisywany w migawce i renderowany w raporcie.

### Nadpisanie listy spółek (smoke test)

Zmienna `AGENT_PREDYKCJE_LIVE_STOCKS` (symbole oddzielone przecinkami, spacje
obcinane, puste wpisy pomijane; np. `PKO.WA,PZU.WA`) zastępuje listę spółek
przekazywaną do analizy. Działa w obu trybach; w trybie `swig80` screening
nadal jest liczony i zapisywany w migawce — zmienia się tylko liczba
analizowanych spółek.

## Odświeżanie składu sWIG80

Sekcję `swig80` odświeża skrypt `scripts/refresh_swig80.py`, który parsuje
oficjalny PDF GPW Benchmark (tabelę główną; lista rezerwowa jest pomijana):

```
python scripts/refresh_swig80.py --pdf PORTFEL.pdf
python scripts/refresh_swig80.py --url https://example.com/Portfele.pdf
```

`--pdf` i `--url` wykluczają się wzajemnie (wymagane jest dokładnie jedno);
`--watchlist PATH` wskazuje inny plik (domyślnie `watchlist.yaml` w katalogu
projektu). Skrypt dopasowuje wpisy po ISIN, zachowuje zweryfikowane symbole,
nazwy i flagi istniejących wpisów (np. `skipped`), usuwa wpisy nieobecne
w PDF, a nowym nadaje `symbol: null`, `ticker: null` oraz
`needs_symbol_verification: true`. Nowy wpis trzeba uzupełnić ręcznie —
projekt nigdy nie wylicza symbolu Yahoo z tickera GPW. Pusty wynik parsowania
przerywa działanie z błędem i nie zmienia watchlisty.

Symbole Yahoo są zapisane w watchliście wprost. Sześć spółek ma w Yahoo symbol
inny niż ticker GPW: ATAL=`1AT.WA`, HUUUGE=`HUG.WA`, MEDINICE=`ICE.WA`,
SYN2BIO=`S2B.WA`, CREOTECH=`CRQ.WA`, GREENX=`GRX.WA`.

NIEWIADOW nie ma notowania na GPW w Yahoo Finance — wpis pozostaje w sekcji
`swig80` z `skipped: true` i powodem „brak notowania na Yahoo (GPW)”;
`collect` go nie pobiera, a screening pokazuje jako wykluczony.

## Dane uwierzytelniające

API Claude wymaga zalogowania: `ant auth login` albo zmienna środowiskowa
`ANTHROPIC_API_KEY`. Model domyślny to `claude-opus-5-5`; można go nadpisać
flagą `--model` lub zmienną `AGENT_PREDYKCJE_MODEL`.

## Koszt

Domyślne uruchomienie `analyze` (tryb `swig80`, 10 spółek) to około 100
wywołań LLM; `--universe watchlist` to 30 wywołań. `AGENT_PREDYKCJE_LIVE_STOCKS`
ustala liczbę wywołań do 10 × liczba podanych spółek — planuj budżet API.

## Zastrzeżenie

Narzędzie szkoleniowe — nie jest poradą inwestycyjną.
