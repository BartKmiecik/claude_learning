"""argparse CLI: collect / analyze / report / run.

Wires Tasks 1-7 into one pipeline: `collect` gathers quotes and news,
`analyze` runs the 30 persona-stock LLM calls and saves a snapshot,
`report` renders the Polish HTML report and opens it, `run` chains all
three. Every failure path prints a Polish message and returns an exit
code (1, or 130 for Ctrl-C) — never a raw traceback.
"""

import argparse
import os
import sys
import webbrowser
from pathlib import Path

import yaml

from agent_predykcje.agent import AgentError
from agent_predykcje.collector import CollectorError, collect
from agent_predykcje.config import load_watchlist, persona_paths, swig80_entries
from agent_predykcje.news import NEWS_FEEDS, fetch_news, save_news
from agent_predykcje.pipeline import (
    load_price_frame,
    load_snapshot,
    latest_snapshot,
    run_analysis,
    save_snapshot,
)
from agent_predykcje.report import render_report
from agent_predykcje.screen import screen_universe

PROJECT_DIR = (
    Path(__file__).resolve().parent.parent.parent
)  # src/agent_predykcje/cli.py -> project root


def _watchlist_path() -> Path:
    return PROJECT_DIR / "watchlist.yaml"


def _data_dir() -> Path:
    return PROJECT_DIR / "data"


def _predictions_dir() -> Path:
    return PROJECT_DIR / "predictions"


def _personas_dir() -> Path:
    return PROJECT_DIR / "personas"


def _report_path() -> Path:
    return PROJECT_DIR / "report" / "raport.html"


def cmd_collect(args) -> int:
    watchlist = load_watchlist(_watchlist_path())
    results = collect(watchlist, _data_dir())
    items = fetch_news(NEWS_FEEDS)
    save_news(items, _data_dir())
    failed = [symbol for symbol, r in results.items() if r.get("status") != "ok"]
    for symbol in failed:
        print(f"Uwaga: błąd pobierania {symbol}.", file=sys.stderr)
    ok = [symbol for symbol, r in results.items() if r.get("status") == "ok"]
    print(f"Zebrano: {len(ok)} instrumentów, newsy: {len(items)} nagłówków.")
    # Partial failure is fine — exit 1 only when nothing at all was collected.
    return 1 if not ok else 0


def cmd_analyze(args) -> int:
    watchlist = load_watchlist(_watchlist_path())
    personas = persona_paths(_personas_dir())
    if not personas:
        print(
            "Brak person w katalogu personas/ — dodaj pliki YAML i spróbuj ponownie.",
            file=sys.stderr,
        )
        return 1

    stocks = None
    screen = None
    env_stocks = (os.environ.get("AGENT_PREDYKCJE_LIVE_STOCKS") or "").strip()
    if args.universe == "swig80":
        entries = swig80_entries(watchlist)
        frames = {}
        for entry in entries:
            symbol = entry.get("symbol")
            if not symbol:
                continue
            try:
                frames[symbol] = load_price_frame(_data_dir(), symbol)
            except FileNotFoundError:
                continue
        screen = screen_universe(entries, frames)
        print(
            f"Screening: wybrano {len(screen['selected'])} spółek z "
            f"{len(screen['rows'])} pozycji."
        )
    if env_stocks:
        stocks = [symbol.strip() for symbol in env_stocks.split(",") if symbol.strip()]
    elif screen is not None:
        stocks = screen["selected"]

    snapshot = run_analysis(
        watchlist,
        _data_dir(),
        _personas_dir(),
        model=getattr(args, "model", None),
        stocks=stocks,
    )
    if screen is not None:
        snapshot["screen"] = screen
    total = len(personas)
    for stock in snapshot["stocks"]:
        ok = sum(1 for agent in stock["agents"] if agent.get("status") == "ok")
        print(f"{stock['symbol']}: {ok}/{total} agentów OK")
    path = save_snapshot(snapshot, _predictions_dir())
    print(f"Migawka zapisana: {path}")
    return 0


def cmd_report(args) -> int:
    path = getattr(args, "snapshot", None) or latest_snapshot(_predictions_dir())
    if path is None:
        print(
            "Brak migawki przewidywań — najpierw uruchom `agent-predykcje analyze`.",
            file=sys.stderr,
        )
        return 1
    snapshot = load_snapshot(path)
    out = render_report(snapshot, _report_path())
    print(f"Raport zapisany: {out}")
    webbrowser.open(Path(out).as_uri())
    return 0


def cmd_run(args) -> int:
    for cmd in (cmd_collect, cmd_analyze, cmd_report):
        code = cmd(args)
        if code != 0:
            return code
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent-predykcje",
        description="Dziesięciu agentów LLM przewiduje ceny akcji z GPW.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("collect", help="pobierz notowania i newsy")
    p_analyze = sub.add_parser(
        "analyze", help="uruchom analizę agentów i zapisz migawkę"
    )
    p_analyze.add_argument(
        "--model",
        default=None,
        help="model Claude (domyślnie: zmienna AGENT_PREDYKCJE_MODEL lub claude-opus-5-5)",
    )
    p_analyze.add_argument(
        "--universe",
        choices=["swig80", "watchlist"],
        default="swig80",
        help="uniwersum analizy: swig80 (screening sWIG80) lub watchlist (sekcja 'stocks')",
    )
    p_report = sub.add_parser(
        "report", help="wygeneruj raport HTML i otwórz go w przeglądarce"
    )
    p_report.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="ścieżka migawki JSON (domyślnie: najnowsza w predictions/)",
    )
    p_run = sub.add_parser("run", help="collect + analyze + report")
    p_run.add_argument(
        "--model",
        default=None,
        help="model Claude (domyślnie: zmienna AGENT_PREDYKCJE_MODEL lub claude-opus-5-5)",
    )
    p_run.add_argument(
        "--universe",
        choices=["swig80", "watchlist"],
        default="swig80",
        help="uniwersum analizy: swig80 (screening sWIG80) lub watchlist (sekcja 'stocks')",
    )
    args = parser.parse_args(argv)
    handlers = {
        "collect": cmd_collect,
        "analyze": cmd_analyze,
        "report": cmd_report,
        "run": cmd_run,
    }
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        print("Przerwano.", file=sys.stderr)
        return 130
    except yaml.YAMLError:
        print("watchlist.yaml jest uszkodzony.", file=sys.stderr)
        return 1
    except (CollectorError, AgentError) as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Brak pliku: {exc.filename}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Błąd wewnętrzny: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
