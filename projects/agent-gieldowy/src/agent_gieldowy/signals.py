"""Deterministic technical signals computed from a (date, close) frame. Pure — no I/O."""

import math

import pandas as pd

TRADING_DAYS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}


def _returns(df: pd.DataFrame, periods: int) -> float:
    if len(df) <= periods:
        return float("nan")
    base = df["close"].iloc[-(periods + 1)]
    last = df["close"].iloc[-1]
    if base == 0:
        return float("nan")
    return float(last / base - 1)


def _annualized_volatility(df: pd.DataFrame) -> float:
    daily = df["close"].pct_change().dropna()
    if len(daily) < 2:
        return float("nan")
    return float(daily.std() * (252**0.5))


def _sma(df: pd.DataFrame, window: int) -> float:
    if len(df) < window:
        return float("nan")
    return float(df["close"].rolling(window).mean().iloc[-1])


def _cross_flags(df: pd.DataFrame) -> dict:
    if len(df) < 200:
        return {
            "sma50_above_sma200": None,
            "golden_cross_recent": False,
            "death_cross_recent": False,
        }
    s50 = df["close"].rolling(50).mean()
    s200 = df["close"].rolling(200).mean()
    above_now = bool(s50.iloc[-1] > s200.iloc[-1])
    above_5_days_ago = bool(s50.iloc[-6] > s200.iloc[-6])
    return {
        "sma50_above_sma200": above_now,
        "golden_cross_recent": above_now and not above_5_days_ago,
        "death_cross_recent": not above_now and above_5_days_ago,
    }


def _rsi14(df: pd.DataFrame) -> float:
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


def _max_drawdown(df: pd.DataFrame) -> float:
    return float((df["close"] / df["close"].cummax() - 1).min())


def compute_signals(df: pd.DataFrame) -> dict:
    """Flat dict of signals for a (date, close) frame sorted oldest→newest."""
    signals = {
        "return_1m": _returns(df, TRADING_DAYS["1M"]),
        "return_3m": _returns(df, TRADING_DAYS["3M"]),
        "return_12m": _returns(df, TRADING_DAYS["12M"]),
        "annualized_volatility": _annualized_volatility(df),
        "momentum_6m": _returns(df, TRADING_DAYS["6M"]),
        "sma50": _sma(df, 50),
        "sma200": _sma(df, 200),
        "rsi14": _rsi14(df),
        "max_drawdown": _max_drawdown(df),
    }
    signals.update(_cross_flags(df))
    return signals
