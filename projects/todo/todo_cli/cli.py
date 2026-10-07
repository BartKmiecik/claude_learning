"""Command-line interface for the todo task manager."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .store import StoreError, TaskStore


def default_store_path() -> Path:
    """Task file location: ~/.todo/tasks.json (created on first write)."""
    return Path.home() / ".todo" / "tasks.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="todo", description="Minimal task manager CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="add a new task")
    add.add_argument("text", help="the task text")

    sub.add_parser("list", help="list all tasks")

    done = sub.add_parser("done", help="mark a task as done")
    done.add_argument("id", type=int, help="task id")

    remove = sub.add_parser("remove", help="remove a task")
    remove.add_argument("id", type=int, help="task id")
    return parser


def main(argv: list[str] | None = None, store_path: Path | None = None) -> int:
    """Run the CLI. argv/store_path are injectable so tests never touch the real store."""
    args = build_parser().parse_args(argv)
    store = TaskStore(store_path or default_store_path())
    try:
        if args.command == "add":
            if not args.text.strip():
                print("Task text cannot be empty", file=sys.stderr)
                return 1
            task = store.add(args.text)
            print(f"#{task.id} added: {task.text}")
        elif args.command == "list":
            for task in store.list():
                mark = "x" if task.done else " "
                print(f"{task.id}. [{mark}] {task.text}")
        elif args.command == "done":
            task = store.done(args.id)
            print(f"#{task.id} completed")
        elif args.command == "remove":
            task = store.remove(args.id)
            print(f"#{task.id} removed")
    except KeyError:
        print(f"No task #{args.id}", file=sys.stderr)
        return 1
    except StoreError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
