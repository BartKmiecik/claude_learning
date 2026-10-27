"""Tests for the Polish self-contained HTML report (Task 7)."""

import html as html_mod

from agent_predykcje.report import (averages, badge_html, band_figure, gain_1m,
    horizon_band, render_report, sorted_stocks)


def _stock(symbol, anchor_price, preds, error_ids=()):
    agents = []
    for pid, name, p in preds:
        agents.append({"persona": pid, "display_name": name, "status": "ok",
                       "error": None, "predictions": p, "justification": "uzasadnienie"})
    for pid in error_ids:
        agents.append({"persona": pid, "display_name": pid, "status": "error",
                       "error": "boom", "predictions": None, "justification": None})
    return {"symbol": symbol, "anchor": {"date": "2026-10-27", "price": anchor_price},
            "agents": agents}


def _snapshot(*stocks):
    return {"created_at": "2026-10-27T10:00:00+00:00", "model": "m",
            "stocks": list(stocks)}


def test_averages_ignore_error_agents():
    stock = _stock("PKO.WA", 62.0, [
        ("a", "A", {"1d": 10.0, "1w": 11.0, "1m": 12.0}),
        ("b", "B", {"1d": 12.0, "1w": 13.0, "1m": 14.0}),
    ], error_ids=["c"])
    assert averages(stock) == {"1d": 11.0, "1w": 12.0, "1m": 13.0, "count": 2}
    assert averages(_stock("PKO.WA", 62.0, [], error_ids=["c"])) is None


def test_horizon_band_min_max():
    stock = _stock("PKO.WA", 62.0, [
        ("a", "A", {"1d": 61.0, "1w": 62.0, "1m": 100.0}),
        ("b", "B", {"1d": 63.0, "1w": 65.0, "1m": 104.0}),
    ])
    band = horizon_band(stock)
    assert band["1d"] == (61.0, 63.0)
    assert band["1m"] == (100.0, 104.0)


def test_gain_1m_and_sorted_stocks():
    a = _stock("A.WA", 100.0, [("x", "X", {"1d": 105.0, "1w": 107.0, "1m": 110.0})])
    b = _stock("B.WA", 50.0, [("x", "X", {"1d": 51.0, "1w": 52.0, "1m": 52.0})])
    c = _stock("C.WA", 30.0, [])
    assert gain_1m(a) == 10.0
    assert gain_1m(b) == 4.0
    assert gain_1m(c) is None
    snapshot = _snapshot(a, c, b)  # None-gain stock in the middle: sinks last
    assert [s["symbol"] for s in sorted_stocks(snapshot)] == ["A.WA", "B.WA", "C.WA"]


def test_badge_colors_and_comma_format():
    assert "background" not in badge_html(2.5)  # colored text, not background
    assert "+2,5%" in badge_html(2.5)
    assert "#1a7f37" in badge_html(2.5)
    assert "#c62828" in badge_html(-1.3)
    assert "#6b7280" in badge_html(0.0)  # gray when gain == 0.0


def test_render_failed_agent_row_and_averages(tmp_path):
    snapshot = _snapshot(_stock("PKO.WA", 62.0,
        [("a", "A", {"1d": 62.0, "1w": 62.0, "1m": 62.0})], error_ids=["b"]))
    out = render_report(snapshot, tmp_path / "raport.html")
    text = (tmp_path / "raport.html").read_text(encoding="utf-8")
    assert out == str(tmp_path / "raport.html")
    assert "brak danych" in text and "Średnia" in text and "narzędzie szkoleniowe" in text


def test_render_escapes_html_in_justification(tmp_path):
    evil = "<script>alert(1)</script>"
    stock = _stock("PKO.WA", 62.0,
        [("a", "A", {"1d": 62.0, "1w": 62.0, "1m": 62.0})])
    stock["agents"][0]["justification"] = evil
    out = render_report(_snapshot(stock), tmp_path / "out" / "raport.html")
    text = (tmp_path / "out" / "raport.html").read_text(encoding="utf-8")
    assert "<script>alert" not in text
    assert html_mod.escape(evil) in text


def test_render_header_shows_anchor_date(tmp_path):
    stock = _stock("PKO.WA", 62.0,
        [("a", "A", {"1d": 62.0, "1w": 63.0, "1m": 64.0})])
    stock["anchor"]["date"] = "2026-10-23"
    render_report(_snapshot(stock), tmp_path / "raport.html")
    text = (tmp_path / "raport.html").read_text(encoding="utf-8")
    assert "2026-10-23" in text
    assert text.count("2026-10-27") == 1  # created_at date only near the title


def test_render_missing_data_section(tmp_path):
    snapshot = _snapshot({"symbol": "PZU.WA", "anchor": None, "agents": []})
    out = render_report(snapshot, tmp_path / "raport.html")
    text = (tmp_path / "raport.html").read_text(encoding="utf-8")
    assert "Brak danych." in text
    assert "Plotly.newPlot" not in text  # no figure rendered → no plotly.js
    assert out == str(tmp_path / "raport.html")


def test_band_figure_traces():
    fig = band_figure(_stock("PKO.WA", 62.0, [
        ("a", "A", {"1d": 61.0, "1w": 63.0, "1m": 65.0}),
        ("b", "B", {"1d": 63.0, "1w": 65.0, "1m": 67.0}),
    ]))
    assert len(fig.data) == 2  # band + average line
    band, line = fig.data
    assert band.fill == "toself"
    assert list(band.x) == ["Dziś", "+1 dzień", "+1 tydzień", "+1 miesiąc",
                            "+1 miesiąc", "+1 tydzień", "+1 dzień", "Dziś"]
    assert line.mode == "lines+markers"
    assert line.line.color == "#111" and line.line.width == 3
    assert list(line.y) == [62.0, 62.0, 64.0, 66.0]
    assert fig.layout.height == 320
    assert fig.layout.yaxis.title.text == "PLN"
