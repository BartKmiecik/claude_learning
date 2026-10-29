"""Tests for the standalone sWIG80 watchlist refresh script (scripts/refresh_swig80.py)."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from refresh_swig80 import main, parse_portfolio_pdf, update_entries  # noqa: E402

PDF = (
    Path(__file__).resolve().parents[3]
    / "docs/superpowers/recon/swig80-2026-10-28/Portfele_WIG20_mWIG40_sWIG80_WIG30_2026_09_03.pdf"
)


def test_parse_returns_80_rows():
    rows = parse_portfolio_pdf(PDF)
    assert len(rows) == 80
    isins = {r["isin"] for r in rows}
    assert "US44853H1086" in isins  # HUUUGE
    assert "AU0000198939" in isins  # GREENX
    assert "NL0000686509" in isins  # ASTARTA
    assert "LU0607203980" in isins  # IMCOMPANY


def test_parse_ignores_reserve_list():
    isins = {r["isin"] for r in parse_portfolio_pdf(PDF)}
    assert "PLPSSUS00018" not in isins  # PASSUS z listy rezerwowej
    assert "PLWTCHN00030" not in isins  # WITTCHEN z listy rezerwowej


def test_update_keeps_existing_symbols():
    existing = [
        {"symbol": "X.WA", "name": "X SA", "ticker": "X", "isin": "PLX000000001"}
    ]
    parsed = [{"isin": "PLX000000001", "kod": "X", "name": "X"}]
    result = update_entries(parsed, existing)
    assert result[0]["symbol"] == "X.WA"
    assert result[0]["name"] == "X SA"
    assert result[0]["ticker"] == "X"


def test_update_flags_new_and_drops_removed():
    existing = [
        {"symbol": "X.WA", "name": "X SA", "ticker": "X", "isin": "PLX000000001"},
        {"symbol": "Z.WA", "name": "Z SA", "ticker": "Z", "isin": "PLZ000000002"},
    ]
    parsed = [
        {"isin": "PLY000000003", "kod": "Y", "name": "Y"},
        {"isin": "PLX000000001", "kod": "X", "name": "X"},
    ]
    result = update_entries(parsed, existing)
    # Kolejność wg parsed; Z znika z wyniku.
    assert [e["isin"] for e in result] == ["PLY000000003", "PLX000000001"]
    # Y jest nowe: symbol do weryfikacji, ticker/name z tokenu PDF.
    assert result[0] == {
        "symbol": None,
        "ticker": None,
        "name": "Y",
        "isin": "PLY000000003",
        "needs_symbol_verification": True,
    }
    # X istnieje: zachowany zweryfikowany symbol.
    assert result[1]["symbol"] == "X.WA"


def test_main_writes_watchlist(tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        "# Watchlista agenta predykcji (testowa).\n"
        "stocks:\n"
        "- PKO.WA\n"
        "- PZU.WA\n"
        "indices:\n"
        "- WIG20.WA\n"
        "swig80:\n"
        "- symbol: CMP.WA\n"
        "  ticker: CMP\n"
        "  name: Comp S.A.\n"
        "  isin: PLCMP0000017\n",
        encoding="utf-8",
    )
    rc = main(["--pdf", str(PDF), "--watchlist", str(watchlist)])
    assert rc == 0
    text = watchlist.read_text(encoding="utf-8")
    # Nagłówkowy komentarz zachowany na górze.
    assert text.startswith("# Watchlista agenta predykcji (testowa).")
    reloaded = yaml.safe_load(text)
    # Sekcje stocks/indices bez zmian.
    assert reloaded["stocks"] == ["PKO.WA", "PZU.WA"]
    assert reloaded["indices"] == ["WIG20.WA"]
    # Sekcja swig80 podmieniona na 80 wpisów z PDF.
    assert len(reloaded["swig80"]) == 80
    # Istniejący wpis zachowuje symbol/name; nowe wymagają weryfikacji symbolu.
    kept = [e for e in reloaded["swig80"] if e["isin"] == "PLCMP0000017"]
    assert kept[0]["symbol"] == "CMP.WA"
    assert kept[0]["name"] == "Comp S.A."
    assert all(
        e.get("symbol") is not None or e.get("needs_symbol_verification")
        for e in reloaded["swig80"]
    )
