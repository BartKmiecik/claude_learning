"""Live smoke — manual only: `pytest -m live`. Hits real sources; no API key needed."""

import pandas as pd
import pytest

from agent_gieldowy.collector import fetch_quotes
from agent_gieldowy.report import render_report

pytestmark = pytest.mark.live


def test_live_collect_one_symbol_and_render(tmp_path):
    df = fetch_quotes("PKO.WA", "stock")
    assert len(df) > 200
    assert df["close"].iloc[-1] > 0
