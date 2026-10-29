"""Analysis pipeline: one LLM call per (stock, persona) and the run snapshot.

`run_analysis` orchestrates the 30 calls (10 personas × 3 stocks) in a
thread pool with one shared Anthropic client, and returns a self-contained
snapshot the report renders without touching data or personas again.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from agent_predykcje.agent import (
    AgentError,
    build_user_message,
    default_model,
    make_client,
    predict_stock,
)
from agent_predykcje.config import persona_paths
from agent_predykcje.news import load_news
from agent_predykcje.persona import load_persona, render_system_prompt
from agent_predykcje.signals import compute_signals


def load_price_frame(data_dir, symbol) -> pd.DataFrame:
    """Read data/<symbol>.csv, oldest→newest; FileNotFoundError when missing."""
    path = Path(data_dir) / f"{symbol}.csv"
    frame = pd.read_csv(path)
    return frame.sort_values("date").reset_index(drop=True)


def anchor_of(df: pd.DataFrame) -> dict:
    """Anchor from the last row: its date string and close price."""
    return {"date": str(df["date"].iloc[-1]), "price": float(df["close"].iloc[-1])}


HISTORY_DAYS = 90


def _price_history_lines(df: pd.DataFrame, days: int = HISTORY_DAYS) -> list[str]:
    """Last `days` rows as compact 'YYYY-MM-DD: CENA' lines (comma decimal)."""
    tail = df[["date", "close"]].tail(days)
    lines = []
    for date, close in zip(tail["date"], tail["close"]):
        price = f"{float(close):.2f}".replace(".", ",")
        lines.append(f"{date}: {price}")
    return lines


def run_analysis(
    watchlist,
    data_dir,
    personas_dir,
    client=None,
    model=None,
    max_workers=5,
    stocks: list[str] | None = None,
) -> dict:
    """Run every (stock, persona) prediction and return the run snapshot.

    One shared client across all calls; futures are collected in submission
    order. An AgentError marks that agent's entry with status "error" and
    never aborts the run — any other exception propagates.

    `stocks=None` predicts watchlist["stocks"]; a list predicts exactly
    those symbols (used by the sWIG80 screening selection).
    """
    client = client or make_client()
    model = model or default_model()
    news_items = load_news(data_dir)
    if not isinstance(news_items, list):
        news_items = []

    index_signals = {}
    for symbol in watchlist.get("indices", []) or []:
        try:
            frame = load_price_frame(data_dir, symbol)
        except FileNotFoundError:
            continue
        index_signals[symbol] = compute_signals(frame)

    personas = [(path.stem, load_persona(path)) for path in persona_paths(personas_dir)]

    symbols = stocks if stocks is not None else (watchlist.get("stocks", []) or [])
    stocks = []
    prepared = []  # (stock entry, user message) for stocks with data
    for symbol in symbols:
        try:
            frame = load_price_frame(data_dir, symbol)
        except FileNotFoundError:
            stocks.append({"symbol": symbol, "anchor": None, "agents": []})
            continue
        anchor = anchor_of(frame)
        entry = {"symbol": symbol, "anchor": anchor, "agents": []}
        stocks.append(entry)
        user_message = build_user_message(
            symbol,
            anchor,
            compute_signals(frame),
            index_signals,
            news_items,
            recent_prices=_price_history_lines(frame),
        )
        prepared.append((entry, user_message))

    jobs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for entry, user_message in prepared:
            for persona_id, persona in personas:
                future = executor.submit(
                    predict_stock,
                    persona_prompt=render_system_prompt(persona),
                    user_message=user_message,
                    anchor_price=entry["anchor"]["price"],
                    client=client,
                    model=model,
                )
                jobs.append(
                    (
                        entry,
                        persona_id,
                        persona.get("display_name") or persona_id,
                        future,
                    )
                )
        for entry, persona_id, display_name, future in jobs:
            agent = {"persona": persona_id, "display_name": display_name}
            try:
                result = future.result()
            except AgentError as exc:
                agent.update(
                    {
                        "status": "error",
                        "error": str(exc),
                        "predictions": None,
                        "justification": None,
                    }
                )
            else:
                agent.update(
                    {
                        "status": "ok",
                        "error": None,
                        "predictions": result["predictions"],
                        "justification": result["justification"],
                    }
                )
            entry["agents"].append(agent)

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "stocks": stocks,
    }


def save_snapshot(snapshot, predictions_dir) -> Path:
    """Write predictions-YYYYmmdd-HHMMSS.json (UTF-8, ensure_ascii=False, indent=2)."""
    name = datetime.now().strftime("predictions-%Y%m%d-%H%M%S.json")
    path = Path(predictions_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def load_snapshot(path) -> dict:
    """Read a snapshot JSON file back as a dict.

    A corrupt file raises AgentError with a Polish message, so the CLI
    prints it without a raw traceback.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentError(f"snapshot jest uszkodzony: {path}") from exc


def latest_snapshot(predictions_dir) -> Path | None:
    """Newest predictions-*.json by filename; None when none exist."""
    files = sorted(Path(predictions_dir).glob("predictions-*.json"))
    return files[-1] if files else None
