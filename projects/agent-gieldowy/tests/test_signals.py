import math

import numpy as np
import pandas as pd
import pytest

from agent_gieldowy.signals import compute_signals


def frame(closes, dates=None):
    if dates is None:
        dates = pd.bdate_range("2025-01-01", periods=len(closes))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes})


def test_returns_on_rising_series():
    closes = list(range(1, 401))  # 400 rows
    s = compute_signals(frame(closes))
    assert s["return_1m"] > 0
    assert s["return_3m"] > 0
    assert s["return_12m"] > 0
    assert s["momentum_6m"] > 0


def test_returns_on_falling_series():
    closes = list(range(400, 0, -1))
    s = compute_signals(frame(closes))
    assert s["return_1m"] < 0
    assert s["momentum_6m"] < 0


def test_constant_series_has_zero_volatility_and_neutral_rsi():
    s = compute_signals(frame([100.0] * 300))
    assert s["annualized_volatility"] == pytest.approx(0.0)
    assert s["rsi14"] == pytest.approx(50.0)


def test_rising_series_rsi_is_100():
    s = compute_signals(frame([100.0 + i for i in range(300)]))
    assert s["rsi14"] == pytest.approx(100.0)


def test_max_drawdown_from_peak():
    closes = [100.0] * 50 + [50.0] * 50  # drops 50% from the peak
    s = compute_signals(frame(closes))
    assert s["max_drawdown"] == pytest.approx(-0.5)


def test_cross_flags_golden_cross_recent():
    # SMA50 below SMA200 for 200 rows, then a sharp rally crosses it up in the last 5
    closes = [100.0] * 200 + [300.0] * 5
    s = compute_signals(frame(closes))
    assert s["sma50_above_sma200"] is True
    assert s["golden_cross_recent"] is True
    assert s["death_cross_recent"] is False


def test_insufficient_data_returns_nan_and_none():
    s = compute_signals(frame([100.0, 101.0, 102.0]))
    assert math.isnan(s["return_12m"])
    assert math.isnan(s["sma200"])
    assert s["sma50_above_sma200"] is None
    assert s["golden_cross_recent"] is False
