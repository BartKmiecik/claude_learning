import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from agent_gieldowy.evaluate import (
    compute_actual_changes,
    evaluate,
    find_due_entries,
    score_direction,
    score_entry,
    score_range,
)
from agent_gieldowy.journal import append_entry, read_entries
from conftest import bdate_range


def iso_days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def entry(age_days=40, symbols=("PKO.WA",)):
    prediction = {
        "horizon": "1M",
        "generated_at": iso_days_ago(age_days),
        "predictions": [
            {"symbol": s, "direction": "up", "range_pct": {"min": -5.0, "max": 8.0}}
            for s in symbols
        ],
        "summary": "s",
        "analysis": "a",
    }
    return {"prediction": prediction}


class FakeMessages:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


class FakeClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)


def test_score_direction_rules():
    assert score_direction("up", 5.0) is True
    assert score_direction("up", -1.0) is False
    assert score_direction("down", -5.0) is True
    assert score_direction("down", 1.0) is False
    assert score_direction("sideways", 1.9) is True
    assert score_direction("sideways", -2.0) is True
    assert score_direction("sideways", 2.1) is False


def test_score_range():
    assert score_range({"min": -5.0, "max": 8.0}, 0.0) is True
    assert score_range({"min": -5.0, "max": 8.0}, 8.0) is True
    assert score_range({"min": -5.0, "max": 8.0}, 8.1) is False


def test_score_entry_marks_missing_actual_as_unscored():
    scored = score_entry(entry(), {"PKO.WA": 3.0})
    assert scored["PKO.WA"]["scored"] is True
    assert scored["PKO.WA"]["direction_hit"] is True
    unscored = score_entry(entry(), {})
    assert unscored["PKO.WA"]["scored"] is False


def test_find_due_entries_filters_by_age_and_state():
    due = entry(age_days=40)
    fresh = entry(age_days=10)
    done = entry(age_days=40)
    done["outcomes"] = {}
    assert find_due_entries([due, fresh, done]) == [due]


def test_compute_actual_changes_reads_csv(tmp_path, watchlist):
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    since = dates[30].strftime("%Y-%m-%d")
    changes = compute_actual_changes(watchlist, since, tmp_path)
    # 100+59 vs 100+30 → +29/130 ≈ +22.3%
    assert changes["PKO.WA"] == pytest.approx(29 / 130 * 100, rel=0.01)


def test_evaluate_processes_due_entries_and_writes_outcomes(tmp_path, watchlist):
    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    client = FakeClient("Za dużo optymizmu — fundamenty były słabsze.")
    processed = evaluate(
        entries_path, tmp_path, watchlist, client=client, persona_prompt="p"
    )
    assert processed == 1
    stored = read_entries(entries_path)[0]
    assert stored["outcomes"]["PKO.WA"]["scored"] is True
    assert stored["reflection"] == "Za dużo optymizmu — fundamenty były słabsze."


def test_evaluate_idempotent(tmp_path, watchlist):
    # Review Focus #5: a second run scores nothing new
    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    client = FakeClient("x")
    assert (
        evaluate(entries_path, tmp_path, watchlist, client=client, persona_prompt="p")
        == 1
    )
    assert (
        evaluate(entries_path, tmp_path, watchlist, client=client, persona_prompt="p")
        == 0
    )
    assert len(client.messages.calls) == 1  # no second reflection call


def test_evaluate_keeps_outcomes_when_reflection_fails(tmp_path, watchlist):
    from agent_gieldowy.agent import AgentError

    class BoomMessages:
        def create(self, **kwargs):
            raise AgentError("brak połączenia z API: x")

    entries_path = tmp_path / "journal" / "entries.jsonl"
    append_entry(entries_path, entry(age_days=40))
    dates = bdate_range(60)
    closes = [100.0 + i for i in range(60)]
    import pandas as pd

    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes}).to_csv(
        tmp_path / "PKO.WA.csv", index=False
    )
    processed = evaluate(
        entries_path,
        tmp_path,
        watchlist,
        client=SimpleNamespace(messages=BoomMessages()),
        persona_prompt="p",
    )
    assert processed == 1
    stored = read_entries(entries_path)[0]
    assert stored["outcomes"]["PKO.WA"]["scored"] is True
    assert stored["reflection"] is None
