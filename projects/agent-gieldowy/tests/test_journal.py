import json
from datetime import datetime

import pytest

from agent_gieldowy.journal import (
    append_entry,
    build_digest,
    read_entries,
    update_entry,
)


@pytest.fixture
def entries_path(tmp_path):
    return tmp_path / "journal" / "entries.jsonl"


def make_entry(prediction=None):
    return {
        "prediction": prediction
        or {
            "horizon": "1M",
            "generated_at": "2026-10-01T12:00:00+00:00",
            "predictions": [
                {
                    "symbol": "PKO.WA",
                    "direction": "up",
                    "range_pct": {"min": -5, "max": 8},
                    "confidence": 65,
                    "rationale": "r",
                    "risks": ["x"],
                }
            ],
            "summary": "s",
            "analysis": "a",
        }
    }


def test_append_adds_id_and_created_at(entries_path):
    stored = append_entry(entries_path, make_entry())
    assert stored["id"]
    assert datetime.fromisoformat(stored["created_at"])
    lines = entries_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == stored


def test_read_missing_file_returns_empty(entries_path):
    assert read_entries(entries_path) == []


def test_append_and_read_roundtrip(entries_path):
    append_entry(entries_path, make_entry())
    append_entry(entries_path, make_entry())
    entries = read_entries(entries_path)
    assert len(entries) == 2
    assert entries[0]["id"] != entries[1]["id"]


def test_update_entry_patches_by_id(entries_path):
    stored = append_entry(entries_path, make_entry())
    update_entry(entries_path, stored["id"], {"reflection": "Byłem zbyt ostrożny."})
    entries = read_entries(entries_path)
    assert entries[0]["reflection"] == "Byłem zbyt ostrożny."
    assert entries[0]["id"] == stored["id"]
    assert len(read_entries(entries_path)) == 1  # no duplicated lines


def test_build_digest_compacts_older_entries(entries_path):
    for i in range(5):
        entry = make_entry()
        entry["prediction"]["predictions"][0]["symbol"] = f"SYM{i}.WA"
        entry["prediction"]["predictions"][0]["direction"] = "down"
        entry["outcomes"] = {"SYM{i}.WA": {"scored": True, "direction_hit": False}}
        entry["reflection"] = f"refleksja {i}"
        append_entry(entries_path, entry)
    digest = build_digest(read_entries(entries_path))
    assert digest["total_entries"] == 5
    assert len(digest["recent"]) == 3
    assert len(digest["older"]) == 2
    older = digest["older"][0]
    assert older["directions"] == {"SYM0.WA": "down"}
    assert older["reflection"] == "refleksja 0"
    assert "prediction" not in older  # compacted away
    assert "analysis" in digest["recent"][0]["prediction"]  # recent entries stay full
