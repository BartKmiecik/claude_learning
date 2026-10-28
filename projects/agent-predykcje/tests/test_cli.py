"""CLI tests: subcommands, flags, path helpers, and the pinned error handling.

Every failure path must print Polish and return an exit code — never a
raw traceback. Components are monkeypatched through the `cli` module
namespace, so `cli.py` must call them as module-level names.
"""

import json

import pandas as pd

from agent_predykcje import cli
from agent_predykcje.agent import AgentError

CREDENTIALS_MSG = (
    "brak danych uwierzytelniających Claude API — uruchom `ant auth login` "
    "albo ustaw zmienną ANTHROPIC_API_KEY"
)


def _write_watchlist(tmp_path):
    """Write a minimal watchlist.yaml fixture and return its path."""
    path = tmp_path / "watchlist.yaml"
    path.write_text("stocks:\n  - PKO.WA\nindices: []\n", encoding="utf-8")
    return path


def _write_swig80_watchlist(tmp_path):
    """Write a watchlist.yaml with only a swig80 section."""
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        "stocks: []\nindices: []\nswig80:\n"
        "  - symbol: CMP.WA\n    name: Comp S.A.\n",
        encoding="utf-8",
    )
    return path


def _write_personas(tmp_path):
    """Create a personas/ dir with one persona and return its path."""
    personas = tmp_path / "personas"
    personas.mkdir()
    (personas / "a.yaml").write_text(
        "name: Anna Kowalska\ndisplay_name: Analityk A\n", encoding="utf-8"
    )
    return personas


def test_analyze_credentials_error_exit_code(tmp_path, monkeypatch, capsys):
    watchlist = _write_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)
    monkeypatch.setattr(cli, "_predictions_dir", lambda: tmp_path / "predictions")

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        raise AgentError(CREDENTIALS_MSG)

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "ant auth login" in out
    assert "Traceback" not in out


def test_analyze_missing_watchlist_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_watchlist_path", lambda: tmp_path / "watchlist.yaml")
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "watchlist.yaml" in out
    assert "Traceback" not in out


def test_analyze_empty_personas_message(tmp_path, monkeypatch, capsys):
    watchlist = _write_watchlist(tmp_path)
    personas = tmp_path / "personas"
    personas.mkdir()  # exists but empty
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "person" in out.lower()
    assert "Traceback" not in out


def test_report_no_snapshot_message(tmp_path, monkeypatch, capsys):
    predictions = tmp_path / "predictions"
    predictions.mkdir()  # exists but empty
    monkeypatch.setattr(cli, "_predictions_dir", lambda: predictions)
    assert cli.main(["report"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "brak" in out.lower()
    assert "Traceback" not in out


def test_run_flow_uses_components(monkeypatch):
    calls = []

    def recorder(name):
        def cmd(args):
            calls.append(name)
            return 0

        return cmd

    monkeypatch.setattr(cli, "cmd_collect", recorder("collect"))
    monkeypatch.setattr(cli, "cmd_analyze", recorder("analyze"))
    monkeypatch.setattr(cli, "cmd_report", recorder("report"))
    assert cli.main(["run"]) == 0
    assert calls == ["collect", "analyze", "report"]


def test_report_opens_latest_snapshot(tmp_path, monkeypatch):
    snapshot = {
        "created_at": "2026-10-27T00:00:00+00:00",
        "model": "m",
        "stocks": [],
    }
    snap_path = tmp_path / "predictions-20261027-120000.json"
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")

    monkeypatch.setattr(cli, "_predictions_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "_report_path", lambda: tmp_path / "raport.html")
    monkeypatch.setattr(cli, "latest_snapshot", lambda predictions_dir: snap_path)

    rendered = []
    monkeypatch.setattr(
        cli,
        "render_report",
        lambda snap, out_path: rendered.append(snap) or str(out_path),
    )
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url))

    assert cli.main(["report"]) == 0
    assert rendered == [snapshot]
    assert opened


def test_report_uses_snapshot_flag(tmp_path, monkeypatch):
    snapshot = {
        "created_at": "2026-10-27T00:00:00+00:00",
        "model": "m",
        "stocks": [],
    }
    snap_path = tmp_path / "other.json"
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")

    monkeypatch.setattr(cli, "_report_path", lambda: tmp_path / "raport.html")
    rendered = []
    monkeypatch.setattr(
        cli,
        "render_report",
        lambda snap, out_path: rendered.append(snap) or str(out_path),
    )
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: None)

    assert cli.main(["report", "--snapshot", str(snap_path)]) == 0
    assert rendered == [snapshot]


def test_keyboard_interrupt_returns_130(tmp_path, monkeypatch):
    watchlist = _write_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    assert cli.main(["analyze"]) == 130


def test_analyze_corrupt_watchlist_exit_1(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "watchlist.yaml"
    bad.write_text("stocks: [PKO.WA\n", encoding="utf-8")  # broken YAML flow seq
    monkeypatch.setattr(cli, "_watchlist_path", lambda: bad)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "watchlist.yaml jest uszkodzony" in out
    assert "Traceback" not in out


def test_analyze_empty_watchlist_exit_1(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "watchlist.yaml"
    empty.write_text("", encoding="utf-8")  # valid YAML, safe_load -> None
    monkeypatch.setattr(cli, "_watchlist_path", lambda: empty)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "watchlist.yaml jest uszkodzony" in out
    assert "Traceback" not in out


def test_report_corrupt_snapshot_exit_1(tmp_path, monkeypatch, capsys):
    predictions = tmp_path / "predictions"
    predictions.mkdir()
    snap = predictions / "predictions-20000101-000000.json"
    snap.write_text('{"created_at": "x",', encoding="utf-8")  # truncated JSON
    monkeypatch.setattr(cli, "_predictions_dir", lambda: predictions)
    assert cli.main(["report"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "snapshot jest uszkodzony" in out
    assert "Traceback" not in out


def test_analyze_internal_error_exit_1(tmp_path, monkeypatch, capsys):
    watchlist = _write_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        raise ValueError("programming bug")

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    assert cli.main(["analyze"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "Błąd wewnętrzny: ValueError" in out
    assert "Traceback" not in out


def test_analyze_swig80_default_uses_screen(tmp_path, monkeypatch):
    watchlist = _write_swig80_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)
    monkeypatch.setattr(cli, "_predictions_dir", lambda: tmp_path / "predictions")
    monkeypatch.delenv("AGENT_PREDYKCJE_LIVE_STOCKS", raising=False)

    frame = pd.DataFrame({"date": ["2026-10-27"], "close": [10.0]})
    monkeypatch.setattr(cli, "load_price_frame", lambda data_dir, symbol: frame)
    screen_result = {"rows": [], "selected": ["CMP.WA"], "skipped": []}
    monkeypatch.setattr(cli, "screen_universe", lambda entries, frames: screen_result)

    captured = {}

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        captured["stocks"] = stocks
        return {"created_at": "x", "model": "m", "stocks": []}

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    saved = []
    monkeypatch.setattr(
        cli,
        "save_snapshot",
        lambda snapshot, predictions_dir: saved.append(snapshot)
        or tmp_path / "predictions.json",
    )
    assert cli.main(["analyze"]) == 0
    assert captured["stocks"] == ["CMP.WA"]
    assert saved[0]["screen"] == screen_result


def test_analyze_watchlist_mode_legacy(tmp_path, monkeypatch):
    watchlist = _write_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)
    monkeypatch.setattr(cli, "_predictions_dir", lambda: tmp_path / "predictions")
    monkeypatch.delenv("AGENT_PREDYKCJE_LIVE_STOCKS", raising=False)

    captured = {}

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        captured["stocks"] = stocks
        return {"created_at": "x", "model": "m", "stocks": []}

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    saved = []
    monkeypatch.setattr(
        cli,
        "save_snapshot",
        lambda snapshot, predictions_dir: saved.append(snapshot)
        or tmp_path / "predictions.json",
    )
    assert cli.main(["analyze", "--universe", "watchlist"]) == 0
    assert captured["stocks"] is None
    assert "screen" not in saved[0]


def test_env_override_forces_stocks(tmp_path, monkeypatch):
    watchlist = _write_watchlist(tmp_path)
    personas = _write_personas(tmp_path)
    monkeypatch.setattr(cli, "_watchlist_path", lambda: watchlist)
    monkeypatch.setattr(cli, "_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(cli, "_personas_dir", lambda: personas)
    monkeypatch.setattr(cli, "_predictions_dir", lambda: tmp_path / "predictions")
    monkeypatch.setenv("AGENT_PREDYKCJE_LIVE_STOCKS", "PKO.WA,PZU.WA")

    captured = {}

    def fake_run_analysis(
        watchlist,
        data_dir,
        personas_dir,
        client=None,
        model=None,
        max_workers=5,
        stocks=None,
    ):
        captured["stocks"] = stocks
        return {"created_at": "x", "model": "m", "stocks": []}

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(
        cli,
        "save_snapshot",
        lambda snapshot, predictions_dir: tmp_path / "predictions.json",
    )
    assert cli.main(["analyze"]) == 0
    assert captured["stocks"] == ["PKO.WA", "PZU.WA"]


def test_collect_partial_failure_exit_0(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "load_watchlist",
        lambda path: {"stocks": ["PKO.WA", "PZU.WA"], "indices": []},
    )
    monkeypatch.setattr(
        cli,
        "collect",
        lambda watchlist, data_dir: {
            "PKO.WA": {"status": "ok", "rows": 5, "appended": 5},
            "PZU.WA": {
                "status": "error",
                "error": "request failed after retries: timeout",
            },
        },
    )
    monkeypatch.setattr(
        cli,
        "fetch_news",
        lambda feeds: [
            {"title": "t", "published": "2026-10-27", "link": "https://x"}
        ],
    )
    monkeypatch.setattr(cli, "save_news", lambda items, data_dir: None)
    assert cli.main(["collect"]) == 0
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "Uwaga: błąd pobierania PZU.WA" in out  # Polish copy, not raw error
    assert "request failed after retries" not in out


def test_collect_all_failed_exit_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "load_watchlist",
        lambda path: {"stocks": ["PZU.WA"], "indices": []},
    )
    monkeypatch.setattr(
        cli,
        "collect",
        lambda watchlist, data_dir: {
            "PZU.WA": {
                "status": "error",
                "error": "request failed after retries: timeout",
            }
        },
    )
    monkeypatch.setattr(cli, "fetch_news", lambda feeds: [])
    monkeypatch.setattr(cli, "save_news", lambda items, data_dir: None)
    assert cli.main(["collect"]) == 1
    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "Uwaga: błąd pobierania PZU.WA" in out
    assert "request failed after retries" not in out
