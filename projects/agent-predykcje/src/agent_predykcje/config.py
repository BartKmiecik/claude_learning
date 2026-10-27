"""Watchlist configuration loading."""

from pathlib import Path

import yaml


def load_watchlist(path) -> dict:
    """Load watchlist.yaml — dict with sections 'stocks' and 'indices'."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_symbols(watchlist: dict) -> list:
    """Flatten the watchlist into [{'symbol', 'kind'}], in section order."""
    kind_by_section = {"stocks": "stock", "indices": "index"}
    items = []
    for section, kind in kind_by_section.items():
        for symbol in watchlist.get(section, []) or []:
            items.append({"symbol": symbol, "kind": kind})
    return items


def persona_paths(personas_dir) -> list[Path]:
    """Return sorted Path objects for *.yaml files in personas_dir."""
    return sorted(Path(personas_dir).glob("*.yaml"))
