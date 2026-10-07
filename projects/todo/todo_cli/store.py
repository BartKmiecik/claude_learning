"""Task persistence for the todo CLI: a JSON file, stored in the user's home directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


class StoreError(Exception):
    """Raised when the task file is corrupted or unreadable."""


@dataclass
class Task:
    id: int
    text: str
    done: bool = False
    created_at: str = ""


class TaskStore:
    """All task operations. The JSON file layout is a private implementation detail."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StoreError(f"Task file is corrupted: {self.path}") from exc
        if not isinstance(data, list):
            raise StoreError(f"Task file has an unexpected format: {self.path}")
        for item in data:
            if not isinstance(item, dict) or not {"id", "text"} <= item.keys():
                raise StoreError(f"Task file is corrupted: {self.path}")
        return data

    def _save(self, tasks: list[dict]) -> None:
        # Atomic write: write a temp file, then replace. A crash mid-write
        # can never leave a half-written task file.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, self.path)

    def add(self, text: str) -> Task:
        tasks = self._load()
        next_id = max((t["id"] for t in tasks), default=0) + 1
        task = Task(
            id=next_id,
            text=text,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        tasks.append(asdict(task))
        self._save(tasks)
        return task

    def list(self) -> list[Task]:
        return [Task(**t) for t in self._load()]
