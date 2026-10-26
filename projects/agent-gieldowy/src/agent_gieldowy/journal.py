"""JSONL journal — the agent's growing memory of analyses, predictions, outcomes."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_entry(entries_path, entry: dict) -> dict:
    """Add id/created_at, append one JSON line, return the stored entry."""
    stored = {**entry, "id": uuid.uuid4().hex, "created_at": _now_iso()}
    entries_path = Path(entries_path)
    entries_path.parent.mkdir(parents=True, exist_ok=True)
    with open(entries_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stored, ensure_ascii=False) + "\n")
    return stored


def read_entries(entries_path) -> list:
    """Entries oldest→newest; missing file → []."""
    entries_path = Path(entries_path)
    if not entries_path.exists():
        return []
    entries = []
    for line in entries_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def update_entry(entries_path, entry_id: str, patch: dict) -> None:
    """Merge `patch` into the entry with `id == entry_id`; rewrite the file."""
    entries_path = Path(entries_path)
    entries = read_entries(entries_path)
    for entry in entries:
        if entry["id"] == entry_id:
            entry.update(patch)
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    entries_path.write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )


def _compact(entry: dict) -> dict:
    predictions = entry.get("prediction", {}).get("predictions", [])
    return {
        "created_at": entry.get("created_at"),
        "directions": {p["symbol"]: p["direction"] for p in predictions},
        "outcomes": entry.get("outcomes"),
        "reflection": entry.get("reflection"),
    }


def build_digest(entries: list, full_count: int = 3) -> dict:
    """Deterministic digest: last `full_count` entries in full, older ones compacted."""
    recent = entries[-full_count:] if full_count else []
    older = entries[:-full_count] if full_count else list(entries)
    return {
        "recent": recent,
        "older": [_compact(e) for e in older],
        "total_entries": len(entries),
    }
