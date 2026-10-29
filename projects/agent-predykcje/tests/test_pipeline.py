from datetime import datetime, timedelta

import pandas as pd
import pytest

from agent_predykcje.agent import AgentError
from agent_predykcje.pipeline import (
    _price_history_lines,
    anchor_of,
    latest_snapshot,
    load_price_frame,
    load_snapshot,
    run_analysis,
    save_snapshot,
)


def _write_price_csv(data_dir, symbol, rows=30, start_price=50.0) -> pd.DataFrame:
    """Write data/<symbol>.csv with `rows` consecutive daily closes."""
    data_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-09-16", periods=rows, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": [start_price + i for i in range(rows)],
        }
    )
    frame.to_csv(data_dir / f"{symbol}.csv", index=False)
    return frame


def _write_personas(personas_dir):
    personas_dir.mkdir(parents=True, exist_ok=True)
    (personas_dir / "a.yaml").write_text(
        "name: Anna Kowalska\ndisplay_name: Analityk A\ntemperament: spokojny\n"
        "biases:\n  - ostrożność\nstyle: krótko\n",
        encoding="utf-8",
    )
    (personas_dir / "b.yaml").write_text(
        "name: Bartosz Nowak\ndisplay_name: Analityk B\ntemperament: żywiołowy\n"
        "biases:\n  - entuzjazm\nstyle: konkretnie\n",
        encoding="utf-8",
    )


def _ok_result():
    return {
        "predictions": {"1d": 80.0, "1w": 81.0, "1m": 85.0, "3m": 90.0, "6m": 95.0},
        "justification": "trend wzrostowy",
    }


def test_anchor_of_uses_last_row():
    df = pd.DataFrame(
        {
            "date": ["2026-10-23", "2026-10-26", "2026-10-27"],
            "close": [61.0, 61.5, 62.0],
        }
    )
    assert anchor_of(df) == {"date": "2026-10-27", "price": 62.0}


def test_load_price_frame_sorted_and_missing_raises(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "PKO.WA.csv").write_text(
        "date,close\n2026-10-27,62.0\n2026-10-23,61.0\n2026-10-26,61.5\n",
        encoding="utf-8",
    )
    frame = load_price_frame(data_dir, "PKO.WA")
    assert list(frame["date"]) == ["2026-10-23", "2026-10-26", "2026-10-27"]
    with pytest.raises(FileNotFoundError):
        load_price_frame(data_dir, "PZU.WA")


def test_run_analysis_custom_stocks(tmp_path, monkeypatch):
    """`stocks=[...]` overrides watchlist["stocks"] — predictions exactly
    for the given symbols."""
    frame = _write_price_csv(tmp_path / "data", "PKO.WA")
    personas_dir = tmp_path / "personas"
    _write_personas(personas_dir)

    def fake_predict(
        persona_prompt, user_message, anchor_price, client=None, model=None
    ):
        return _ok_result()

    monkeypatch.setattr("agent_predykcje.pipeline.predict_stock", fake_predict)
    snapshot = run_analysis(
        {"stocks": [], "indices": []},
        tmp_path / "data",
        personas_dir,
        client=object(),
        model="m",
        stocks=["PKO.WA"],
    )
    assert len(snapshot["stocks"]) == 1
    stock = snapshot["stocks"][0]
    assert stock["symbol"] == "PKO.WA"
    assert stock["anchor"] == {
        "date": frame["date"].iloc[-1],
        "price": float(frame["close"].iloc[-1]),
    }
    assert [a["status"] for a in stock["agents"]] == ["ok", "ok"]


def test_run_analysis_one_agent_error(tmp_path, monkeypatch):
    frame = _write_price_csv(tmp_path / "data", "PKO.WA")
    personas_dir = tmp_path / "personas"
    _write_personas(personas_dir)
    shared_client = object()
    calls = []

    def fake_predict(
        persona_prompt, user_message, anchor_price, client=None, model=None
    ):
        calls.append((persona_prompt, client, model))
        if "Anna" in persona_prompt:
            return _ok_result()
        raise AgentError("boom")

    monkeypatch.setattr("agent_predykcje.pipeline.predict_stock", fake_predict)
    snapshot = run_analysis(
        {"stocks": ["PKO.WA"], "indices": []},
        tmp_path / "data",
        personas_dir,
        client=shared_client,
        model="m",
        max_workers=2,
    )

    assert snapshot["model"] == "m"
    assert snapshot["created_at"].endswith("+00:00")
    stock = snapshot["stocks"][0]
    assert stock["symbol"] == "PKO.WA"
    assert stock["anchor"] == {
        "date": frame["date"].iloc[-1],
        "price": float(frame["close"].iloc[-1]),
    }
    by_id = {agent["persona"]: agent for agent in stock["agents"]}
    assert set(by_id) == {"a", "b"}
    ok = by_id["a"]
    assert ok["status"] == "ok"
    assert ok["display_name"] == "Analityk A"
    assert ok["error"] is None
    assert ok["predictions"]["1m"] is not None
    assert ok["predictions"]["6m"] == 95.0
    assert ok["justification"] == "trend wzrostowy"
    failed = by_id["b"]
    assert failed["status"] == "error"
    assert failed["display_name"] == "Analityk B"
    assert failed["error"] == "boom"
    assert failed["predictions"] is None
    assert failed["justification"] is None
    # one shared client for all calls, model passed through
    assert len(calls) == 2
    assert all(client is shared_client and model == "m" for _, client, model in calls)


def test_run_analysis_propagates_unexpected_errors(tmp_path, monkeypatch):
    _write_price_csv(tmp_path / "data", "PKO.WA")
    personas_dir = tmp_path / "personas"
    _write_personas(personas_dir)

    def boom_predict(
        persona_prompt, user_message, anchor_price, client=None, model=None
    ):
        raise ValueError("programming bug")

    monkeypatch.setattr("agent_predykcje.pipeline.predict_stock", boom_predict)
    with pytest.raises(ValueError):
        run_analysis(
            {"stocks": ["PKO.WA"], "indices": []},
            tmp_path / "data",
            personas_dir,
            client=object(),
            model="m",
        )


def test_run_analysis_missing_csv_yields_empty_stock(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    personas_dir = tmp_path / "personas"
    _write_personas(personas_dir)
    snapshot = run_analysis(
        {"stocks": ["PKO.WA"], "indices": []},
        data_dir,
        personas_dir,
        client=object(),
        model="m",
    )
    assert snapshot["stocks"] == [{"symbol": "PKO.WA", "anchor": None, "agents": []}]


def test_run_analysis_skips_missing_index_csv(tmp_path, monkeypatch):
    _write_price_csv(tmp_path / "data", "PKO.WA")
    personas_dir = tmp_path / "personas"
    _write_personas(personas_dir)

    def fake_predict(
        persona_prompt, user_message, anchor_price, client=None, model=None
    ):
        return _ok_result()

    monkeypatch.setattr("agent_predykcje.pipeline.predict_stock", fake_predict)
    snapshot = run_analysis(
        {"stocks": ["PKO.WA"], "indices": ["WIG20.WA"]},
        tmp_path / "data",
        personas_dir,
        client=object(),
        model="m",
    )
    assert [a["status"] for a in snapshot["stocks"][0]["agents"]] == ["ok", "ok"]


def test_save_load_snapshot_roundtrip(tmp_path):
    snap = {
        "created_at": "x",
        "model": "m",
        "stocks": [],
        "notatka": "zażółć gęślą jaźń",
    }
    path = save_snapshot(snap, tmp_path)
    assert path.name.startswith("predictions-") and path.suffix == ".json"
    assert "zażółć" in path.read_text(encoding="utf-8")  # ensure_ascii=False
    assert load_snapshot(path) == snap


def test_latest_snapshot_picks_newest(tmp_path):
    first = save_snapshot({"created_at": "1", "model": "m", "stocks": []}, tmp_path)
    # Derive an older and a newer name from the real timestamp — no fixed
    # dates, so the suite cannot expire (date bomb).
    when = datetime.strptime(first.stem, "predictions-%Y%m%d-%H%M%S")
    older = tmp_path / (when - timedelta(seconds=1)).strftime(
        "predictions-%Y%m%d-%H%M%S.json"
    )
    newest = tmp_path / (when + timedelta(seconds=1)).strftime(
        "predictions-%Y%m%d-%H%M%S.json"
    )
    older.write_text('{"created_at": "2"}', encoding="utf-8")
    newest.write_text('{"created_at": "3"}', encoding="utf-8")
    (tmp_path / "not-a-snapshot.txt").write_text("x", encoding="utf-8")
    assert latest_snapshot(tmp_path) == newest
    empty = tmp_path / "empty"
    empty.mkdir()
    assert latest_snapshot(empty) is None


def test_price_history_lines_tail_90_with_comma(tmp_path):
    frame = _write_price_csv(tmp_path / "data", "PKO.WA", rows=95, start_price=50.0)
    lines = _price_history_lines(frame)
    assert len(lines) == 90
    assert lines[0] == "2026-09-21: 55,00"  # first of the last 90 days
    assert lines[-1] == "2026-12-19: 144,00"  # the newest close
