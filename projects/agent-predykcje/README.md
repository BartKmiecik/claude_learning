# agent-predykcje

Projekt szkoleniowy: dziesięciu agentów LLM, każdy z inną osobowością,
przewiduje ceny akcji z GPW w trzech horyzontach (1 dzień, 1 tydzień, 1 miesiąc).

## Co robi

- `collect` — pobiera 12 miesięcy notowań z Yahoo Finance oraz nagłówki RSS do `data/`,
- `analyze` — uruchamia 30 wywołań LLM (10 person × 3 spółki z `watchlist.yaml`)
  i zapisuje migawkę wyników do `predictions/`,
- `report` — generuje samodzielny raport HTML `report/raport.html` i otwiera go
  w przeglądarce,
- `run` — wywołuje po kolei `collect`, `analyze` i `report`.

## Dziesięć person

Wieczny niedźwiedź, Wieczny byk, Kontrarianin, Rentier dywidendowy,
Makroekonomista, Trader momentum, Analityk newsowy, Statystyk-quant,
Analityk techniczny, Fundamentalista wartościowy.
Osobowości są edytowalne — wystarczy zmienić pliki w `personas/`.

## Użycie

```
agent-predykcje collect
agent-predykcje analyze [--model MODEL]
agent-predykcje report [--snapshot predictions/predictions-*.json]
agent-predykcje run [--model MODEL]
```

## Dane uwierzytelniające

API Claude wymaga zalogowania: `ant auth login` albo zmienna środowiskowa
`ANTHROPIC_API_KEY`. Model domyślny to `claude-opus-5-5`; można go nadpisać
flagą `--model` lub zmienną `AGENT_PREDYKCJE_MODEL`.

## Koszt

Każde uruchomienie `analyze` to 30 wywołań LLM — planuj budżet API.

## Zastrzeżenie

Narzędzie szkoleniowe — nie jest poradą inwestycyjną.
