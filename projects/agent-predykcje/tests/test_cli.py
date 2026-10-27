"""CLI tests: subcommands, flags, path helpers, and the pinned error handling.

Every failure path must print Polish and return an exit code — never a
raw traceback. Components are monkeypatched through the `cli` module
namespace, so `cli.py` must call them as module-level names.
"""

import json

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
        watchlist, data_dir, personas_dir, client=None, model=None, max_workers=5
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
        watchlist, data_dir, personas_dir, client=None, model=None, max_workers=5
    ):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_analysis", fake_run_analysis)
    assert cli.main(["analyze"]) == 130
