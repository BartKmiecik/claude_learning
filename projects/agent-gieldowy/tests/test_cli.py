from pathlib import Path

import pytest

import agent_gieldowy.cli as cli


@pytest.fixture
def project_files(tmp_path, monkeypatch):
    """Point cli.PROJECT_DIR at a temp tree with watchlist/persona files."""
    (tmp_path / "watchlist.yaml").write_text(
        "stocks:\n  - PKO.WA\nindices: []\nfunds: []\n", encoding="utf-8"
    )
    (tmp_path / "persona.yaml").write_text(
        "name: X\nage: 1\ncity: C\nprofession: P\n"
        "social_position: S\neducation: E\nlife_history: []\n"
        "biases: []\ntemperament: T\nstyle: S\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "PROJECT_DIR", Path(tmp_path))
    return tmp_path


def test_collect_calls_collector(project_files, monkeypatch):
    calls = {}

    def fake_collect(watchlist, data_dir, session=None):
        calls["watchlist"] = watchlist
        calls["data_dir"] = str(data_dir)
        return {"PKO.WA": {"status": "ok", "rows": 1, "appended": 1}}

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 0
    assert calls["watchlist"]["stocks"] == ["PKO.WA"]
    assert calls["data_dir"].endswith("data")


def test_collect_partial_failure_warns_but_exits_0(project_files, monkeypatch, capsys):
    # Review Focus #1: one dead symbol must not halt the pipeline
    (project_files / "watchlist.yaml").write_text(
        "stocks:\n  - PKO.WA\n  - PZU.WA\nindices: []\nfunds: []\n", encoding="utf-8"
    )

    def fake_collect(watchlist, data_dir, session=None):
        return {
            "PKO.WA": {"status": "error", "error": "Yahoo has no data for PKO.WA"},
            "PZU.WA": {"status": "ok", "rows": 1, "appended": 1},
        }

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 0
    assert "Yahoo has no data for PKO.WA" in capsys.readouterr().err


def test_collect_all_failed_exits_1(project_files, monkeypatch, capsys):
    def fake_collect(watchlist, data_dir, session=None):
        return {"PKO.WA": {"status": "error", "error": "Yahoo has no data for PKO.WA"}}

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "fetch_news", lambda urls, limit=20, session=None: [])
    assert cli.main(["collect"]) == 1
    assert "Zebrano: 0" in capsys.readouterr().out


def test_analyze_runs_agent_and_appends_journal_entry(project_files, monkeypatch):
    (project_files / "data").mkdir(exist_ok=True)
    (project_files / "data" / "PKO.WA.csv").write_text(
        "date,close\n2026-10-01,100.0\n2026-10-02,101.0\n", encoding="utf-8"
    )
    monkeypatch.setattr(cli, "read_entries", lambda p: [])
    monkeypatch.setattr(
        cli,
        "build_digest",
        lambda entries: {"recent": [], "older": [], "total_entries": 0},
    )
    monkeypatch.setattr(cli, "compute_signals", lambda df: {"return_1m": 0.01})
    monkeypatch.setattr(cli, "build_signals_table", lambda s: "PKO.WA: 1M 1.0%")
    monkeypatch.setattr(cli, "load_persona", lambda p: {"name": "X"})
    monkeypatch.setattr(cli, "render_system_prompt", lambda persona: "prompt")
    news_items = [{"title": "t", "published": "d", "link": "l"}]
    monkeypatch.setattr(cli, "load_news_items", lambda p: news_items)
    appended = {}

    def fake_analyze(
        persona_prompt, user_message, watchlist_symbols, client=None, model=None
    ):
        return {
            "horizon": "1M",
            "predictions": [],
            "summary": "s",
            "analysis": "a",
            "generated_at": "2026-10-26T00:00:00+00:00",
        }

    def fake_append(entries_path, entry):
        appended["entry"] = entry
        return {**entry, "id": "x", "created_at": "2026-10-26T00:00:00+00:00"}

    monkeypatch.setattr(cli, "analyze", fake_analyze)
    monkeypatch.setattr(cli, "append_entry", fake_append)
    assert cli.main(["analyze"]) == 0
    assert appended["entry"]["prediction"]["horizon"] == "1M"


def test_analyze_without_data_files_exits_1(project_files, monkeypatch, capsys):
    monkeypatch.setattr(cli, "read_entries", lambda p: [])
    monkeypatch.setattr(cli, "load_news_items", lambda p: [])
    assert cli.main(["analyze"]) == 1
    assert "danych" in capsys.readouterr().err.lower()


def test_report_writes_file_and_opens_browser(project_files, monkeypatch):
    monkeypatch.setattr(
        cli, "render_report", lambda *a, **k: str(project_files / "report.html")
    )
    opened = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url))
    assert cli.main(["report"]) == 0
    assert opened and opened[0].startswith("file://")


def test_evaluate_delegates(project_files, monkeypatch):
    calls = {}

    def fake_evaluate(
        entries_path, data_dir, watchlist, client=None, model=None, persona_prompt=""
    ):
        calls["called"] = True
        return 2

    monkeypatch.setattr(cli, "evaluate", fake_evaluate)
    assert cli.main(["evaluate"]) == 0
    assert calls["called"] is True


def test_run_is_collect_then_analyze_then_report(project_files, monkeypatch):
    order = []
    monkeypatch.setattr(cli, "cmd_collect", lambda args: order.append("collect") or 0)
    monkeypatch.setattr(cli, "cmd_analyze", lambda args: order.append("analyze") or 0)
    monkeypatch.setattr(cli, "cmd_report", lambda args: order.append("report") or 0)
    assert cli.main(["run"]) == 0
    assert order == ["collect", "analyze", "report"]


def test_run_stops_when_collect_fails(project_files, monkeypatch):
    order = []
    monkeypatch.setattr(cli, "cmd_collect", lambda args: order.append("collect") or 1)
    monkeypatch.setattr(cli, "cmd_analyze", lambda args: order.append("analyze") or 0)
    monkeypatch.setattr(cli, "cmd_report", lambda args: order.append("report") or 0)
    assert cli.main(["run"]) == 1
    assert order == ["collect"]
