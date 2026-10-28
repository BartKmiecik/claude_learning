"""Deterministyczny screening sWIG80 — 8 sygnałów wzrostowych i wybór top 10.

Czyste funkcje, zero I/O: ramki wchodzą jako pd.DataFrame z kolumnami
(date, close) posortowanymi od najstarszych do najnowszych.
"""

import pandas as pd

MIN_SESSIONS = 64
TOP_N = 10


def _returns(df: pd.DataFrame, periods: int) -> float:
    """Zwrot: ostatnia sesja vs `periods` sesji wstecz; NaN gdy za mało danych."""
    if len(df) <= periods:
        return float("nan")
    base = df["close"].iloc[-(periods + 1)]
    last = df["close"].iloc[-1]
    if base == 0:
        return float("nan")
    return float(last / base - 1)


def _rsi14(df: pd.DataFrame) -> float:
    """RSI(14) z rolling-mean zysków/strat (standardowa definicja)."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()
    if len(avg_loss.dropna()) == 0:
        return float("nan")
    ag, al = float(avg_gain.iloc[-1]), float(avg_loss.iloc[-1])
    if ag == 0 and al == 0:
        return 50.0
    if al == 0:
        return 100.0
    return float(100 - 100 / (1 + ag / al))


def score_frame(df: pd.DataFrame) -> dict | None:
    """Oceń ramkę 8 sygnałami wzrostowymi; None poniżej MIN_SESSIONS sesji.

    Wynik: {"signals": {8 booli}, "score": int, "return_1m": float,
    "return_3m": float}.
    """
    if len(df) < MIN_SESSIONS:
        return None
    close = df["close"]
    last = float(close.iloc[-1])

    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])

    macd = (
        close.ewm(span=12, adjust=False).mean()
        - close.ewm(span=26, adjust=False).mean()
    )
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    rsi = _rsi14(df)

    band = close.rolling(20)
    bollinger_upper = float((band.mean() + 2.0 * band.std(ddof=0)).iloc[-1])

    return_1m = _returns(df, 21)
    return_3m = _returns(df, 63)

    signals = {
        "price_above_sma20": last > sma20,
        "price_above_sma50": last > sma50,
        "sma20_above_sma50": sma20 > sma50,
        "macd_above_signal": bool(macd.iloc[-1] > macd_signal.iloc[-1]),
        "rsi_between_50_70": 50.0 < rsi < 70.0,
        "return_1m_positive": return_1m > 0,
        "return_3m_positive": return_3m > 0,
        "price_above_bollinger_upper": last > bollinger_upper,
    }
    return {
        "signals": signals,
        "score": sum(signals.values()),
        "return_1m": return_1m,
        "return_3m": return_3m,
    }


def _excluded_row(symbol, name, reason) -> dict:
    """Wiersz wykluczony ze screena — score, sygnały i zwroty None."""
    return {
        "symbol": symbol,
        "name": name,
        "score": None,
        "signals": None,
        "return_1m": None,
        "return_3m": None,
        "selected": False,
        "reason": reason,
    }


def _row_sort_key(row: dict) -> tuple:
    """Klucz sortowania: punktowani przed wykluczonymi; dalej score i zwroty
    malejąco, symbol rosnąco."""
    if row["score"] is None:
        return (True, row["symbol"] or "")
    return (False, -row["score"], -row["return_3m"], -row["return_1m"], row["symbol"])


def screen_universe(entries: list[dict], frames: dict[str, pd.DataFrame]) -> dict:
    """Przeprowadź screening sWIG80: oceń wpisy, posortuj i wybierz top 10.

    Wynik:
      "rows"     — wiersze: najpierw punktowane (score desc, zwrot 3M desc,
                   zwrot 1M desc, symbol asc), potem wykluczone (symbol asc)
                   z powodem w "reason" i score None;
      "selected" — symbole pierwszych TOP_N punktowanych wierszy;
      "skipped"  — symbole wierszy wykluczonych (wpisy bez symbolu pominięte).
    """
    rows = []
    for entry in entries:
        symbol = entry.get("symbol")
        name = entry.get("name", "")
        if entry.get("skipped"):
            rows.append(_excluded_row(symbol, name, entry.get("reason")))
            continue
        frame = frames.get(symbol)
        if frame is None:
            rows.append(_excluded_row(symbol, name, "brak danych lokalnych"))
            continue
        result = score_frame(frame)
        if result is None:
            rows.append(_excluded_row(symbol, name, f"za mało sesji (<{MIN_SESSIONS})"))
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "score": result["score"],
                "signals": result["signals"],
                "return_1m": result["return_1m"],
                "return_3m": result["return_3m"],
                "selected": False,
                "reason": None,
            }
        )

    rows.sort(key=_row_sort_key)
    for row in rows[:TOP_N]:
        if row["score"] is not None:
            row["selected"] = True
    selected = [row["symbol"] for row in rows if row["selected"]]
    skipped = [
        row["symbol"]
        for row in rows
        if row["score"] is None and row["symbol"] is not None
    ]
    return {"rows": rows, "selected": selected, "skipped": skipped}
