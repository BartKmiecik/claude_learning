"""Live end-to-end smoke test: full fetch plus screening, 30 real LLM calls.

The analyzed stocks are pinned via ``AGENT_PREDYKCJE_LIVE_STOCKS`` to three
symbols (3 stocks x 10 personas = 30 queries), which keeps the LLM budget
under control while still exercising full fetch and sWIG80 screening.

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
    # Pin the analyzed stocks to keep the smoke run at 30 LLM queries.
    monkeypatch.setenv("AGENT_PREDYKCJE_LIVE_STOCKS", "PKO.WA,PZU.WA,PKN.WA")

    assert cli.main(["collect"]) == 0
    assert cli.main(["run"]) == 0

    snapshot_path = latest_snapshot(cli._predictions_dir())
    assert snapshot_path is not None
    snapshot = load_snapshot(snapshot_path)
    assert snapshot["stocks"]
    assert len(snapshot["stocks"]) == 3
    assert snapshot.get("screen")
    for stock in snapshot["stocks"]:
        assert stock["anchor"] is not None

    assert cli._report_path().is_file()
