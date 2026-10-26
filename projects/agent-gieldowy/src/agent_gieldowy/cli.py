"""argparse CLI: collect / analyze / evaluate / report / run."""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd

from agent_gieldowy.agent import (
    AgentError,
    analyze,
    build_signals_table,
    build_user_message,
)
from agent_gieldowy.collector import CollectorError, collect
from agent_gieldowy.config import all_symbols, load_watchlist
from agent_gieldowy.evaluate import evaluate
from agent_gieldowy.journal import append_entry, build_digest, read_entries
from agent_gieldowy.news import NEWS_FEEDS, fetch_news, save_news
from agent_gieldowy.persona import load_persona, render_system_prompt
from agent_gieldowy.report import render_report
from agent_gieldowy.signals import compute_signals

PROJECT_DIR = (
    Path(__file__).resolve().parent.parent.parent
)  # src/agent_gieldowy/cli.py → project root


def _data_dir() -> Path:
    return PROJECT_DIR / "data"


def _entries_path() -> Path:
    return PROJECT_DIR / "journal" / "entries.jsonl"


def _watchlist_path() -> Path:
    return PROJECT_DIR / "watchlist.yaml"


def _persona_path() -> Path:
    return PROJECT_DIR / "persona.yaml"


def load_news_items(path: Path) -> list:
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
        print(
            "Brak danych — najpierw uruchom `agent-gieldowy collect`.", file=sys.stderr
        )
        return 1
    entries = read_entries(_entries_path())
    digest = build_digest(entries)
    news_items = load_news_items(_data_dir() / "news.json")
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
        _entries_path(),
        _data_dir(),
        load_watchlist(_watchlist_path()),
        persona_prompt=render_system_prompt(persona),
    )
    print(f"Oceniono wpisów: {processed}.")
    return 0


def cmd_report(args) -> int:
    out = PROJECT_DIR / "report.html"
    path = render_report(
        load_watchlist(_watchlist_path()),
        _data_dir(),
        _persona_path(),
        _entries_path(),
        out,
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
    parser = argparse.ArgumentParser(
        prog="agent-gieldowy",
        description="Polski pipeline rynkowy + agent z osobowością.",
    )
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
