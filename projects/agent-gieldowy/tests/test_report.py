import json

import pandas as pd
import pytest

from agent_gieldowy.journal import append_entry
from agent_gieldowy.report import render_report
from conftest import bdate_range

PERSONA = """\
name: "Andrzej Malinowski"
age: 55
city: "Kraków"
profession: "analityk TFI"
social_position: "wyższa klasa średnia"
education: "mgr"
life_history: []
biases:
  - "awersja do ryzyka"
temperament: "spokojny"
style: "konkretny"
"""


def prediction():
    return {
        "horizon": "1M",
        "generated_at": "2026-10-01T12:00:00+00:00",
        "predictions": [
            {
                "symbol": "PKO.WA",
                "direction": "up",
                "range_pct": {"min": -5, "max": 8},
                "confidence": 65,
                "rationale": "r",
                "risks": ["x"],
            }
        ],
        "summary": "Ostrożnie pozytywnie.",
        "analysis": "Pełna analiza.",
    }


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    dates = bdate_range(300)
    closes = [100.0 + i for i in range(300)]
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        d / "PKO.WA.csv", index=False
    )
    (d / "news.json").write_text(
        json.dumps(
            [
                {
                    "title": "Nagłówek testowy",
                    "published": "2026-10-26",
                    "link": "https://x/1",
                }
            ]
        ),
        encoding="utf-8",
    )
    return d


@pytest.fixture
def persona_path(tmp_path):
    p = tmp_path / "persona.yaml"
    p.write_text(PERSONA, encoding="utf-8")
    return p


def test_report_contains_disclaimer_chart_signals_and_news(
    data_dir, persona_path, tmp_path, watchlist
):
    out = tmp_path / "report.html"
    render_report(
        watchlist, data_dir, persona_path, tmp_path / "journal" / "entries.jsonl", out
    )
    html = out.read_text(encoding="utf-8")
    assert "narzędzie szkoleniowe, nie porada inwestycyjna" in html
    assert "PKO.WA" in html
    assert "plotly" in html.lower()  # embedded JS library
    assert "Nagłówek testowy" in html


def test_report_empty_state_no_crash(data_dir, persona_path, tmp_path, watchlist):
    # Review Focus #4: empty journal + a missing symbol file render placeholders
    import os

    os.remove(data_dir / "PKO.WA.csv")
    out = tmp_path / "report.html"
    render_report(
        watchlist, data_dir, persona_path, tmp_path / "journal" / "entries.jsonl", out
    )
    html = out.read_text(encoding="utf-8")
    assert "Brak danych." in html
    assert "Brak prognozy" in html
    assert "Dziennik pusty." in html


def test_report_renders_agent_section_and_hit_counter(
    data_dir, persona_path, tmp_path, watchlist
):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    stored = append_entry(entries_path, {"prediction": prediction()})
    stored["outcomes"] = {
        "PKO.WA": {
            "scored": True,
            "actual_pct": 3.0,
            "direction_hit": True,
            "range_hit": True,
        }
    }
    stored["reflection"] = "Refleksja testowa."
    lines = [json.dumps(stored, ensure_ascii=False)]
    entries_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, persona_path, entries_path, out)
    html = out.read_text(encoding="utf-8")
    assert "Andrzej Malinowski" in html
    assert "awersja do ryzyka" in html
    assert "Pełna analiza." in html
    assert "Refleksja testowa." in html
    assert "1/1" in html  # hit counter
    assert "Ryzyka" in html  # risks section (§11)
    assert "x" in html  # the predicted risk is rendered


def test_report_escapes_llm_and_news_text(data_dir, persona_path, tmp_path, watchlist):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    pred = prediction()
    pred["analysis"] = "<script>alert(1)</script>"
    pred["predictions"][0]["rationale"] = "a < b & c"
    stored = append_entry(entries_path, {"prediction": pred})
    entries_path.write_text(
        json.dumps(stored, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (data_dir / "news.json").write_text(
        json.dumps(
            [
                {
                    "title": "<b>Nagłówek</b>",
                    "published": "2026-10-26",
                    "link": "https://x/?a='1'",
                }
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, persona_path, entries_path, out)
    html_out = out.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in html_out
    assert "<script>alert" not in html_out
    assert "&lt;b&gt;Nagłówek&lt;/b&gt;" in html_out


def test_report_missing_persona_renders_placeholder(data_dir, tmp_path, watchlist):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    stored = append_entry(entries_path, {"prediction": prediction()})
    entries_path.write_text(
        json.dumps(stored, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    out = tmp_path / "report.html"
    render_report(watchlist, data_dir, tmp_path / "nieistnieje.yaml", entries_path, out)
    html_out = out.read_text(encoding="utf-8")
    assert "Anonimowy analityk" in html_out
    assert "Pełna analiza." in html_out
