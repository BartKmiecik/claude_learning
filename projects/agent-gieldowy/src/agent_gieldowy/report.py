"""Self-contained plotly HTML report: data, signals, agent, journal, news."""

import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from agent_gieldowy.agent import fmt
from agent_gieldowy.config import all_symbols
from agent_gieldowy.journal import read_entries
from agent_gieldowy.persona import load_persona
from agent_gieldowy.signals import compute_signals

DISCLAIMER = "narzędzie szkoleniowe, nie porada inwestycyjna"


def _price_figure(df: pd.DataFrame, symbol: str) -> go.Figure:
    dates = pd.to_datetime(df["date"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=df["close"], mode="lines", name=symbol))
    for window in (50, 200):
        if len(df) >= window:
            sma = df["close"].rolling(window).mean()
            fig.add_trace(go.Scatter(x=dates, y=sma, mode="lines", name=f"SMA{window}"))
    fig.update_layout(title=symbol, xaxis_title="Data", yaxis_title="PLN", height=320)
    return fig


def _signals_table(signals: dict) -> str:
    rows = [
        ("Zwrot 1M", fmt(signals["return_1m"], pct=True)),
        ("Zwrot 3M", fmt(signals["return_3m"], pct=True)),
        ("Zwrot 12M", fmt(signals["return_12m"], pct=True)),
        ("Momentum 6M", fmt(signals["momentum_6m"], pct=True)),
        ("Zmienność (roczna)", fmt(signals["annualized_volatility"], pct=True)),
        ("RSI14", fmt(signals["rsi14"])),
        ("SMA50", fmt(signals["sma50"])),
        ("SMA200", fmt(signals["sma200"])),
        ("Max drawdown", fmt(signals["max_drawdown"], pct=True)),
    ]
    body = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows
    )
    return f"<table border='1' cellpadding='4'><tr><th>Wskaźnik</th><th>Wartość</th></tr>{body}</table>"


def _prediction_table(prediction: dict) -> str:
    rows = []
    for p in prediction["predictions"]:
        rows.append(
            f"<tr><td>{html.escape(p['symbol'])}</td><td>{html.escape(p['direction'])}</td>"
            f"<td>{p['range_pct']['min']}% do {p['range_pct']['max']}%</td>"
            f"<td>{p['confidence']}</td><td>{html.escape(p['rationale'])}</td></tr>"
        )
    body = "".join(rows)
    return (
        "<table border='1' cellpadding='4'><tr><th>Symbol</th><th>Kierunek</th>"
        f"<th>Przedział</th><th>Pewność</th><th>Uzasadnienie</th></tr>{body}</table>"
    )


def _hit_counter(entries: list) -> str:
    hits = total = 0
    for e in entries:
        for outcome in (e.get("outcomes") or {}).values():
            if outcome.get("scored"):
                total += 1
                hits += bool(outcome.get("direction_hit"))
    return f"{hits}/{total}"


def _journal_entry_html(entry: dict) -> str:
    pred = entry.get("prediction") or {}
    summary = html.escape(str(pred.get("summary", "—")))
    outcomes = entry.get("outcomes") or {}
    marks = " ".join(
        f"{html.escape(sym)}: {'✓' if o.get('direction_hit') else '✗' if o.get('scored') else '?'}"
        for sym, o in outcomes.items()
    )
    reflection = (
        f"<p><em>{html.escape(entry['reflection'])}</em></p>"
        if entry.get("reflection")
        else ""
    )
    return f"<li>{entry['created_at'][:10]} — {summary} [{marks}]</li>{reflection}"


def render_report(
    watchlist: dict, data_dir, persona_path, entries_path, out_path
) -> str:
    data_dir = Path(data_dir)
    entries = read_entries(entries_path)
    latest = entries[-1] if entries else None
    parts = [
        "<html><head><meta charset='utf-8'><title>Raport agenta giełdowego</title></head><body>",
        "<h1>Raport agenta giełdowego</h1>",
        "<p>Horyzont prognozy: 1 miesiąc.</p>",
        f"<p><strong>Uwaga: {DISCLAIMER}.</strong></p>",
    ]
    first_figure = True
    for item in all_symbols(watchlist):
        symbol = item["symbol"]
        path = data_dir / f"{symbol}.csv"
        parts.append(f"<h2>{html.escape(symbol)}</h2>")
        if not path.exists():
            parts.append("<p>Brak danych.</p>")
            continue
        df = pd.read_csv(path)
        if len(df) < 2:
            parts.append("<p>Brak danych.</p>")
            continue
        fig = _price_figure(df, symbol)
        parts.append(fig.to_html(full_html=False, include_plotlyjs=first_figure))
        first_figure = False
        parts.append(_signals_table(compute_signals(df)))
    parts.append("<h2>Analiza agenta</h2>")
    if latest and latest.get("prediction"):
        persona = load_persona(persona_path)
        parts.append(
            f"<p><strong>{html.escape(persona['name'])}</strong> — {html.escape(persona['profession'])}, "
            f"{html.escape(persona['city'])}. Skłonności: {', '.join(html.escape(b) for b in persona['biases'])}.</p>"
        )
        parts.append(_prediction_table(latest["prediction"]))
        parts.append("<h3>Ryzyka</h3><ul>")
        for p in latest["prediction"]["predictions"]:
            risks = (
                "".join(f"<li>{html.escape(r)}</li>" for r in p.get("risks", []))
                or "<li>—</li>"
            )
            parts.append(
                f"<li><strong>{html.escape(p['symbol'])}:</strong><ul>{risks}</ul></li>"
            )
        parts.append("</ul>")
        parts.append(f"<p>{html.escape(latest['prediction']['analysis'])}</p>")
    else:
        parts.append("<p>Brak prognozy — uruchom `agent-gieldowy analyze`.</p>")
    parts.append("<h2>Dziennik agenta</h2>")
    if entries:
        parts.append(
            f"<p>Trafność kierunku (historyczna): {_hit_counter(entries)}</p><ul>"
        )
        for entry in entries[-5:]:
            parts.append(_journal_entry_html(entry))
        parts.append("</ul>")
    else:
        parts.append("<p>Dziennik pusty.</p>")
    news_path = data_dir / "news.json"
    if news_path.exists():
        parts.append("<h2>Wiadomości</h2><ul>")
        for n in json.loads(news_path.read_text(encoding="utf-8")):
            parts.append(
                f"<li><a href='{html.escape(n['link'])}'>{html.escape(n['title'])}</a> — {html.escape(n['published'])}</li>"
            )
        parts.append("</ul>")
    parts.append("</body></html>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return str(out_path)
