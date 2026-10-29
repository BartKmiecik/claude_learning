"""Polish self-contained HTML report: per-stock band chart and agent table.

Rendered purely from a run snapshot (Task 6 schema) — no CSVs, no news
files, no personas. Every dynamic string is HTML-escaped, and plotly.js
is embedded once, with the first figure.
"""

import html
from pathlib import Path

import plotly.graph_objects as go

DISCLAIMER = "narzędzie szkoleniowe, nie porada inwestycyjna"

_HORIZONS = ("1d", "1w", "1m")
_CATEGORIES = ["Dziś", "+1 dzień", "+1 tydzień", "+1 miesiąc"]
_GREEN = "#1a7f37"
_RED = "#c62828"
_GRAY = "#6b7280"
_SCREEN_HEADERS = (
    "Wybrane",
    "Symbol",
    "Nazwa",
    "Score",
    "SMA20",
    "SMA50",
    "20>50",
    "MACD",
    "RSI",
    "1M",
    "3M",
    "Boll.",
    "Zwrot 1M",
    "Zwrot 3M",
    "Powód",
)
_SCREEN_SIGNALS = (
    "price_above_sma20",
    "price_above_sma50",
    "sma20_above_sma50",
    "macd_above_signal",
    "rsi_between_50_70",
    "return_1m_positive",
    "return_3m_positive",
    "price_above_bollinger_upper",
)


def ok_agents(stock: dict) -> list[dict]:
    """Agents with status "ok" and a predictions dict, in snapshot order."""
    return [
        agent
        for agent in stock["agents"]
        if agent.get("status") == "ok" and agent.get("predictions")
    ]


def averages(stock: dict) -> dict | None:
    """Mean prediction per horizon over ok agents; None when there are none."""
    agents = ok_agents(stock)
    if not agents:
        return None
    result = {
        horizon: sum(agent["predictions"][horizon] for agent in agents) / len(agents)
        for horizon in _HORIZONS
    }
    result["count"] = len(agents)
    return result


def horizon_band(stock: dict) -> dict | None:
    """(min, max) prediction per horizon over ok agents; None when none."""
    agents = ok_agents(stock)
    if not agents:
        return None
    return {
        horizon: (
            min(agent["predictions"][horizon] for agent in agents),
            max(agent["predictions"][horizon] for agent in agents),
        )
        for horizon in _HORIZONS
    }


def gain_1m(stock: dict) -> float | None:
    """One-month average gain over the anchor price, in percent.

    None when the anchor or the averages are missing.
    """
    anchor = stock.get("anchor")
    means = averages(stock)
    if not anchor or means is None:
        return None
    return (means["1m"] - anchor["price"]) / anchor["price"] * 100


def sorted_stocks(snapshot: dict) -> list[dict]:
    """Stocks by one-month gain descending; None-gain stocks last in order."""

    def key(stock):
        gain = gain_1m(stock)
        return (gain is None, -(gain if gain is not None else 0.0))

    return sorted(snapshot["stocks"], key=key)


def badge_html(gain: float) -> str:
    """'średni zysk {+x,x}%' span: green for gains, red for losses, gray for zero."""
    text = f"{gain:+,.1f}".replace(".", ",")
    if gain > 0:
        color = _GREEN
    elif gain < 0:
        color = _RED
    else:
        color = _GRAY
    return f"<span style='color:{color}'>średni zysk {text}%</span>"


def band_figure(stock: dict) -> go.Figure:
    """Horizon band chart: min–max polygon behind the black average line."""
    anchor_price = stock["anchor"]["price"]
    means = averages(stock) or {horizon: anchor_price for horizon in _HORIZONS}
    band = horizon_band(stock) or {
        horizon: (anchor_price, anchor_price) for horizon in _HORIZONS
    }
    mins = [anchor_price] + [band[horizon][0] for horizon in _HORIZONS]
    maxes = [anchor_price] + [band[horizon][1] for horizon in _HORIZONS]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=_CATEGORIES + _CATEGORIES[::-1],
            y=mins + maxes[::-1],
            fill="toself",
            fillcolor="rgba(128, 128, 128, 0.25)",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=_CATEGORIES,
            y=[anchor_price, means["1d"], means["1w"], means["1m"]],
            mode="lines+markers",
            line=dict(color="#111", width=3),
            showlegend=False,
        )
    )
    fig.update_layout(yaxis_title="PLN", height=320)
    return fig


def _price_pl(value: float) -> str:
    """Polish price string: two decimals with a comma."""
    return f"{value:.2f}".replace(".", ",")


def _agents_table(stock: dict) -> str:
    rows = []
    for agent in stock["agents"]:
        name = html.escape(agent["display_name"])
        if agent.get("status") == "ok" and agent.get("predictions"):
            cells = "".join(
                f"<td>{_price_pl(agent['predictions'][horizon])}</td>"
                for horizon in _HORIZONS
            )
            justification = html.escape(agent["justification"] or "")
        else:
            cells = "<td>brak danych</td>" * 3
            justification = "—"
        rows.append(f"<tr><td>{name}</td>{cells}<td>{justification}</td></tr>")
    means = averages(stock)
    if means is not None:
        avg_cells = "".join(
            f"<td>{_price_pl(means[horizon])}</td>" for horizon in _HORIZONS
        )
    else:
        avg_cells = "<td>brak danych</td>" * 3
    rows.append(f"<tr><td>Średnia</td>{avg_cells}<td></td></tr>")
    head = (
        "<tr><th>Agent</th><th>+1 dzień</th><th>+1 tydzień</th>"
        "<th>+1 miesiąc</th><th>Uzasadnienie</th></tr>"
    )
    return f"<table border='1' cellpadding='4'>{head}{''.join(rows)}</table>"


def _percent_pl(ratio: float) -> str:
    """Polish percent string: signed, one decimal, with a comma."""
    return f"{ratio * 100:+.1f}%".replace(".", ",")


def _screen_table(screen: dict) -> str:
    """HTML ranking table for the sWIG80 screening result."""
    head = "".join(f"<th>{html.escape(name)}</th>" for name in _SCREEN_HEADERS)
    rows = []
    for row in screen["rows"]:
        cells = [
            "<td>✓</td>" if row["selected"] else "<td></td>",
            f"<td>{html.escape(row['symbol'] or '')}</td>",
            f"<td>{html.escape(row['name'] or '')}</td>",
        ]
        signals = row["signals"]
        if signals is None:
            cells.append("<td>—</td>")  # Score
            cells.extend(["<td>—</td>"] * len(_SCREEN_SIGNALS))
            cells.extend(["<td>—</td>", "<td>—</td>"])  # Zwrot 1M, Zwrot 3M
        else:
            cells.append(f"<td>{row['score']}</td>")
            cells.extend(
                "<td>✓</td>" if signals[key] else "<td>✗</td>"
                for key in _SCREEN_SIGNALS
            )
            cells.append(f"<td>{_percent_pl(row['return_1m'])}</td>")
            cells.append(f"<td>{_percent_pl(row['return_3m'])}</td>")
        cells.append(f"<td>{html.escape(row['reason'] or '')}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    table = (
        f"<table border='1' cellpadding='4'><tr>{head}</tr>" f"{''.join(rows)}</table>"
    )
    return "\n".join(["<h2>Screening sWIG80 — ranking spółek</h2>", table])


def _stock_section(stock: dict, rank: int, include_plotlyjs: bool) -> str:
    symbol = html.escape(stock["symbol"])
    anchor = stock.get("anchor")
    if not anchor:
        return f"<h2>{rank}. {symbol}</h2><p>Brak danych.</p>"
    header = (
        f"<h2>{rank}. {symbol} · {_price_pl(anchor['price'])} zł · "
        f"{html.escape(anchor['date'])}</h2>"
    )
    gain = gain_1m(stock)
    if gain is not None:
        header += badge_html(gain)
    figure_html = band_figure(stock).to_html(
        full_html=False, include_plotlyjs=include_plotlyjs
    )
    return "\n".join([header, figure_html, _agents_table(stock)])


def render_report(snapshot: dict, out_path) -> str:
    """Write the self-contained Polish report and return the path as a string."""
    date = html.escape(str(snapshot["created_at"])[:10])
    parts = [
        "<html><head><meta charset='utf-8'>"
        "<title>Raport przewidywań GPW</title></head><body>",
        "<h1>Raport przewidywań GPW</h1>",
        f"<p>Data: {date}</p>",
        f"<p><strong>Uwaga: {DISCLAIMER}.</strong></p>",
    ]
    first_figure = True
    for rank, stock in enumerate(sorted_stocks(snapshot), start=1):
        parts.append(_stock_section(stock, rank, include_plotlyjs=first_figure))
        if stock.get("anchor"):
            first_figure = False
    if snapshot.get("screen"):
        parts.append(_screen_table(snapshot["screen"]))
    parts.append("</body></html>")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return str(out_path)
