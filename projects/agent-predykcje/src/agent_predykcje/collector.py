"""Collect 12 months of daily quotes from Yahoo (stocks and indices).

Quotes are normalized to a common (date, close) frame and stored per symbol
in data/<symbol>.csv, incrementally (only new days are appended).
"""

import time
from pathlib import Path

import pandas as pd
import requests

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 10
MAX_RETRIES = 2


class CollectorError(Exception):
    """A data source failed after retries."""


class UnknownSymbolError(CollectorError):
    """The source returned success but no data for this symbol."""


def http_get(url: str, params=None, session=None) -> requests.Response:
    """GET with retries; raises CollectorError after MAX_RETRIES exhausted."""
    sess = session or requests
    last = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = sess.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # noqa: PERF203
            last = exc
            if attempt < MAX_RETRIES:
                time.sleep(1 + attempt)
    raise CollectorError(f"request failed after retries: {url}: {last}")


def _cutoff_iso() -> str:
    return (pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )


def _to_iso_date(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%d")


def fetch_quotes(symbol: str, kind: str, session=None) -> pd.DataFrame:
    """Daily (date, close) frame for the last 365 calendar days, oldest→newest."""
    resp = http_get(
        YAHOO_URL.format(symbol=symbol),
        params={"range": "2y", "interval": "1d"},
        session=session,
    )
    result = (resp.json().get("chart") or {}).get("result")
    if not result:
        raise UnknownSymbolError(f"Yahoo has no data for {symbol}")
    ts = result[0]["timestamp"]
    closes = result[0]["indicators"]["quote"][0]["close"]
    df = pd.DataFrame({"ts": ts, "close": closes})
    df["date"] = _to_iso_date(pd.to_datetime(df["ts"], unit="s", utc=True))
    df = df.dropna(subset=["close"])[["date", "close"]]
    df = df[df["date"] >= _cutoff_iso()].sort_values("date").reset_index(drop=True)
    return df


def save_incremental(symbol: str, new_df: pd.DataFrame, data_dir) -> int:
    """Append rows newer than the last local date; return rows appended."""
    data_dir = Path(data_dir)
    path = data_dir / f"{symbol}.csv"
    old = (
        pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["date", "close"])
    )
    if not old.empty:
        new_df = new_df[new_df["date"] > old["date"].max()]
    if new_df.empty:
        return 0
    merged = pd.concat([old, new_df], ignore_index=True).drop_duplicates(subset="date")
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(path, index=False)
    return len(new_df)


def collect(watchlist: dict, data_dir, session=None) -> dict:
    """Collect every watchlist instrument; one failure never aborts the rest."""
    from agent_predykcje.config import all_symbols

    results = {}
    for item in all_symbols(watchlist):
        try:
            df = fetch_quotes(item["symbol"], item["kind"], session)
            appended = save_incremental(item["symbol"], df, data_dir)
            results[item["symbol"]] = {
                "status": "ok",
                "rows": len(df),
                "appended": appended,
            }
        # one failing symbol never aborts the others (spec §6.1/§9) — malformed payloads surface as ValueError/KeyError/IndexError
        except (CollectorError, ValueError, KeyError, IndexError) as exc:
            results[item["symbol"]] = {"status": "error", "error": str(exc)}
    return results
