"""Live end-to-end smoke test: real network, real data, 30 real LLM calls.

Excluded from the default suite by ``addopts = "-m 'not live'"`` in
pyproject.toml. Run it manually with:

    .venv/Scripts/python.exe -m pytest -m live
"""

import pytest

from agent_predykcje import cli
from agent_predykcje.pipeline import latest_snapshot, load_snapshot


@pytest.mark.live
def test_full_run_smoke(monkeypatch):
    # `report` opens the generated HTML in a browser; keep the test headless.
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: None)

    assert cli.main(["collect"]) == 0
    assert cli.main(["run"]) == 0

    snapshot_path = latest_snapshot(cli._predictions_dir())
    assert snapshot_path is not None
    snapshot = load_snapshot(snapshot_path)
    assert snapshot["stocks"]
    for stock in snapshot["stocks"]:
        assert stock["anchor"] is not None

    assert cli._report_path().is_file()
