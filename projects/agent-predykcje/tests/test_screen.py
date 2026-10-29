import pandas as pd
import pytest

from agent_predykcje import screen
from agent_predykcje.screen import score_frame, screen_universe


def frame(closes):
    """Build a (date, close) frame sorted oldest -> newest."""
    dates = pd.bdate_range("2025-01-01", periods=len(closes))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes})


def alternating(start=100.0, up=4.0, down=2.0, n=100):
    """Alternating +up/-down series of closes (n rows)."""
    closes = [start]
    for i in range(n - 1):
        closes.append(closes[-1] + (up if i % 2 == 0 else -down))
    return closes


def test_score_frame_uptrend():
    # 99 dni rosnących 100..198 + skok ostatniego dnia do 250
    # (liniowy ramp NIE przebija SMA20+2σ — wstęga wymaga outliera);
    # → wszystkie sygnały True oprócz RSI (RSI = 100 przy samych wzrostach)
    df = frame(list(range(100, 199)) + [250])
    s = score_frame(df)
    assert s["signals"]["price_above_sma20"] is True
    assert s["signals"]["price_above_sma50"] is True
    assert s["signals"]["sma20_above_sma50"] is True
    assert s["signals"]["macd_above_signal"] is True
    assert s["signals"]["return_1m_positive"] is True
    assert s["signals"]["return_3m_positive"] is True
    assert s["signals"]["price_above_bollinger_upper"] is True
    assert s["signals"]["rsi_between_50_70"] is False  # RSI = 100
    assert s["score"] == 7
    # zwroty: 250 vs 21 i 63 sesji wstecz (close[78] = 178, close[36] = 136)
    assert s["return_1m"] == pytest.approx(250 / 178 - 1)
    assert s["return_3m"] == pytest.approx(250 / 136 - 1)


def test_score_frame_downtrend():
    # 100 malejących closes: 199, 198, ..., 100 → wszystkie sygnały False, score 0
    df = frame(list(range(199, 99, -1)))
    s = score_frame(df)
    assert all(sig is False for sig in s["signals"].values())
    assert s["score"] == 0


def test_score_frame_insufficient_history():
    assert score_frame(frame(list(range(63)))) is None
    assert score_frame(frame(list(range(64)))) is not None


def test_score_frame_rsi_boundaries():
    # płaska seria (RSI = 50) → rsi_between_50_70 False
    flat = frame([100.0] * 100)
    assert score_frame(flat)["signals"]["rsi_between_50_70"] is False
    # seria naprzemienna +4/-2 (ag/al = 2 → RSI = 66,7) → True
    alt_4_2 = frame(alternating(up=4.0, down=2.0))
    assert score_frame(alt_4_2)["signals"]["rsi_between_50_70"] is True
    # seria naprzemienna +7/-3 (ag/al = 7/3 → RSI = 70 dokładnie) → False
    alt_7_3 = frame(alternating(up=7.0, down=3.0))
    assert score_frame(alt_7_3)["signals"]["rsi_between_50_70"] is False


def fake_result(score, return_1m=0.05, return_3m=0.05):
    """Controlled score_frame result — signals irrelevant for sorting tests."""
    return {
        "signals": {},
        "score": score,
        "return_1m": return_1m,
        "return_3m": return_3m,
    }


def test_screen_universe_selection_and_order(monkeypatch):
    # A: score 8, return_3m 0.10; B: score 8, return_3m 0.20; C: score 5
    # → rows[0] = B, rows[1] = A; mniej niż 10 punktowanych → wszyscy wybrani
    frames = {sym: frame(list(range(100, 200))) for sym in ("A.WA", "B.WA", "C.WA")}
    fake = {
        id(frames["A.WA"]): fake_result(8, return_3m=0.10),
        id(frames["B.WA"]): fake_result(8, return_3m=0.20),
        id(frames["C.WA"]): fake_result(5),
    }
    monkeypatch.setattr(screen, "score_frame", lambda df: fake[id(df)])
    entries = [
        {"symbol": sym, "name": f"{sym} S.A."} for sym in ("A.WA", "B.WA", "C.WA")
    ]
    result = screen_universe(entries, frames)
    assert [row["symbol"] for row in result["rows"]] == ["B.WA", "A.WA", "C.WA"]
    assert result["selected"] == ["B.WA", "A.WA", "C.WA"]
    assert result["rows"][0]["selected"] is True
    c_row = result["rows"][2]
    assert c_row["selected"] is True
    assert c_row["score"] == 5
    assert c_row["reason"] is None


def test_screen_universe_top10_cutoff(monkeypatch):
    # 11 punktowanych spółek → selected to pierwsze 10 wg score desc
    symbols = [f"S{i:02d}.WA" for i in range(11)]
    frames = {sym: frame(list(range(100, 200))) for sym in symbols}
    fake = {id(frames[sym]): fake_result(i) for i, sym in enumerate(symbols)}
    monkeypatch.setattr(screen, "score_frame", lambda df: fake[id(df)])
    entries = [{"symbol": sym, "name": f"{sym} S.A."} for sym in symbols]
    result = screen_universe(entries, frames)
    assert result["selected"] == list(reversed(symbols))[:10]
    assert result["rows"][9]["selected"] is True
    assert result["rows"][10]["symbol"] == "S00.WA"
    assert result["rows"][10]["selected"] is False


def test_screen_universe_tie_break(monkeypatch):
    # A i B: score 8, return_3m równy; A return_1m wyższy → A przed B
    # C i D: score, 3M, 1M identyczne → porządek alfabetyczny symboli
    frames = {
        sym: frame(list(range(100, 200))) for sym in ("A.WA", "B.WA", "C.WA", "D.WA")
    }
    fake = {
        id(frames["A.WA"]): fake_result(8, return_1m=0.20, return_3m=0.10),
        id(frames["B.WA"]): fake_result(8, return_1m=0.10, return_3m=0.10),
        id(frames["C.WA"]): fake_result(5),
        id(frames["D.WA"]): fake_result(5),
    }
    monkeypatch.setattr(screen, "score_frame", lambda df: fake[id(df)])
    entries = [
        {"symbol": sym, "name": f"{sym} S.A."}
        for sym in ("A.WA", "B.WA", "C.WA", "D.WA")
    ]
    result = screen_universe(entries, frames)
    assert [row["symbol"] for row in result["rows"]] == ["A.WA", "B.WA", "C.WA", "D.WA"]
    # mniej niż 10 punktowanych → wybrani wszyscy ze score
    assert result["selected"] == ["A.WA", "B.WA", "C.WA", "D.WA"]


def test_screen_universe_exclusions():
    # wpis skipped → reason z YAML; wpis bez ramki → "brak danych lokalnych";
    # ramka 63 wierszy → "za mało sesji (<64)"; wszystkie na końcu rows,
    # score None, nie w selected
    entries = [
        {"symbol": "OK.WA", "name": "OK S.A."},
        {
            "symbol": None,
            "name": "Niewiadow",
            "skipped": True,
            "reason": "brak notowania na Yahoo (GPW)",
        },
        {"symbol": "GONE.WA", "name": "Brak Danych S.A."},
        {"symbol": "SHORT.WA", "name": "Krótka Historia S.A."},
        {
            "symbol": "SKIP.WA",
            "name": "Skip S.A.",
            "skipped": True,
            "reason": "powód z YAML",
        },
    ]
    frames = {
        "OK.WA": frame(list(range(100, 199)) + [250]),
        "SHORT.WA": frame(list(range(63))),
        # ramka jest, ale skipped ma pierwszeństwo
        "SKIP.WA": frame(list(range(100, 200))),
    }
    result = screen_universe(entries, frames)
    # punktowana spółka pierwsza, wykluczone za nią (symbol asc; None najpierw)
    assert [row["symbol"] for row in result["rows"]] == [
        "OK.WA",
        None,
        "GONE.WA",
        "SHORT.WA",
        "SKIP.WA",
    ]
    assert result["selected"] == ["OK.WA"]
    assert result["skipped"] == ["GONE.WA", "SHORT.WA", "SKIP.WA"]
    by_symbol = {row["symbol"]: row for row in result["rows"]}
    assert by_symbol[None]["reason"] == "brak notowania na Yahoo (GPW)"
    assert by_symbol[None]["name"] == "Niewiadow"
    assert by_symbol["GONE.WA"]["reason"] == "brak danych lokalnych"
    assert by_symbol["SHORT.WA"]["reason"] == "za mało sesji (<64)"
    assert by_symbol["SKIP.WA"]["reason"] == "powód z YAML"
    for sym in (None, "GONE.WA", "SHORT.WA", "SKIP.WA"):
        row = by_symbol[sym]
        assert row["score"] is None
        assert row["signals"] is None
        assert row["return_1m"] is None
        assert row["return_3m"] is None
        assert row["selected"] is False
    ok_row = by_symbol["OK.WA"]
    assert ok_row["selected"] is True
    assert ok_row["reason"] is None


def test_screen_universe_deterministic():
    # dwa wywołania z tymi samymi danymi → identyczne rows i selected
    entries = [
        {"symbol": "UP.WA", "name": "Uptrend S.A."},
        {"symbol": "DOWN.WA", "name": "Downtrend S.A."},
        {"symbol": "MISS.WA", "name": "Brak S.A."},
    ]
    frames = {
        "UP.WA": frame(list(range(100, 199)) + [250]),
        "DOWN.WA": frame(list(range(199, 99, -1))),
    }
    first = screen_universe(entries, frames)
    second = screen_universe(entries, frames)
    assert first == second
    assert first["rows"] == second["rows"]
    assert first["selected"] == second["selected"]
    # UP (score 7) i DOWN (score 0) — obaj punktowani, więc wybrani obaj
    assert first["selected"] == ["UP.WA", "DOWN.WA"]
    assert first["rows"][-1]["reason"] == "brak danych lokalnych"
