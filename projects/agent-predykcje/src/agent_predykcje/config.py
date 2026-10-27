"""Watchlist configuration loading."""

from pathlib import Path

import yaml


def load_watchlist(path) -> dict:
    """Load watchlist.yaml — dict with sections 'stocks' and 'indices'.

    An empty file (safe_load -> None) or any non-mapping document raises
    yaml.YAMLError, so the CLI reports a corrupt watchlist instead of
    crashing on a later .get() call.
    """
    with open(path, encoding="utf-8") as f:
        watchlist = yaml.safe_load(f)
    if not isinstance(watchlist, dict):
        raise yaml.YAMLError(
            "plik musi zawierać mapę z sekcjami 'stocks' i 'indices'"
        )
    return watchlist


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
