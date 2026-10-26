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
