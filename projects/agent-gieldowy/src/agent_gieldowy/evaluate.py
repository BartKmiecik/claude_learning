"""Score predictions older than 30 days against reality; let the agent reflect."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from agent_gieldowy.agent import AgentError, default_model, make_client
from agent_gieldowy.config import all_symbols
from agent_gieldowy.journal import read_entries, update_entry


def score_direction(pred_dir: str, actual_pct: float) -> bool:
    if pred_dir == "sideways":
        return abs(actual_pct) <= 2.0
    if pred_dir == "up":
        return actual_pct > 0
    return actual_pct < 0


def score_range(range_pct: dict, actual_pct: float) -> bool:
    return range_pct["min"] <= actual_pct <= range_pct["max"]


def score_entry(entry: dict, actual_changes: dict) -> dict:
    per_symbol = {}
    for p in entry["prediction"]["predictions"]:
        actual = actual_changes.get(p["symbol"])
        if actual is None:
            per_symbol[p["symbol"]] = {"scored": False}
            continue
        per_symbol[p["symbol"]] = {
            "scored": True,
            "actual_pct": round(actual, 2),
            "direction_hit": score_direction(p["direction"], actual),
            "range_hit": score_range(p["range_pct"], actual),
        }
    return per_symbol


def find_due_entries(entries: list, min_age_days: int = 30) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    due = []
    for e in entries:
        if e.get("outcomes") is not None:
            continue
        try:
            created = datetime.fromisoformat(e["prediction"]["generated_at"])
        except (KeyError, ValueError):
            continue
        if created <= cutoff:
            due.append(e)
    return due


def compute_actual_changes(watchlist: dict, since_date, data_dir) -> dict:
    """Pct change (0–100 scale) per symbol from first close at/after since_date to latest."""
    since_iso = (
        since_date.strftime("%Y-%m-%d")
        if hasattr(since_date, "strftime")
        else since_date
    )
    changes = {}
    for item in all_symbols(watchlist):
        path = Path(data_dir) / f"{item['symbol']}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df = df[df["date"] >= since_iso]
        if len(df) < 2:
            continue
        base = float(df["close"].iloc[0])
        if base == 0:
            continue
        changes[item["symbol"]] = float(df["close"].iloc[-1] / base - 1) * 100
    return changes


def reflect(
    prediction: dict, outcomes: dict, client, model, persona_prompt: str
) -> str:
    client = client or make_client()
    model = model or default_model()
    user_message = (
        f"Twoja prognoza z {prediction['generated_at']}:\n"
        f"{prediction['summary']}\n\n"
        f"Rzeczywiste wyniki (zmiana % i trafienia):\n{outcomes}\n\n"
        "Napisz 1-2 zdania refleksji w pierwszej osobie: co przegapiłeś, co zadziałało, "
        "czego to Cię uczy na przyszłość. Odpowiadaj jako Ty, zgodnie ze swoją personą."
    )
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=persona_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def evaluate(
    entries_path, data_dir, watchlist, client=None, model=None, persona_prompt: str = ""
) -> int:
    """Score all due entries, append reflections, return entries processed."""
    processed = 0
    for entry in find_due_entries(read_entries(entries_path)):
        since = datetime.fromisoformat(entry["prediction"]["generated_at"])
        actual = compute_actual_changes(watchlist, since, data_dir)
        outcomes = score_entry(entry, actual)
        patch = {"outcomes": outcomes}
        try:
            patch["reflection"] = reflect(
                entry["prediction"], outcomes, client, model, persona_prompt
            )
        except (
            AgentError,
            Exception,
        ) as exc:  # noqa: BLE001 — reflection is best-effort
            patch["reflection"] = None
            print(f"Uwaga: refleksja agenta nie powiodła się: {exc}", file=sys.stderr)
        update_entry(entries_path, entry["id"], patch)
        processed += 1
    return processed
