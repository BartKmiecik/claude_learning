"""Watchlist configuration loading."""

import yaml


def load_watchlist(path) -> dict:
    """Load watchlist.yaml — dict with sections 'stocks', 'indices', 'funds'."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_symbols(watchlist: dict) -> list:
    """Flatten the watchlist into [{'symbol', 'kind'}], in section order."""
    kind_by_section = {"stocks": "stock", "indices": "index", "funds": "fund"}
    items = []
    for section, kind in kind_by_section.items():
        for symbol in watchlist.get(section, []) or []:
            items.append({"symbol": symbol, "kind": kind})
    return items
