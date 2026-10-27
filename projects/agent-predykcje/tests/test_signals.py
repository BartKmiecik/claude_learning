import math

import pandas as pd
import pytest

from agent_predykcje.signals import compute_signals


def frame(closes):
    """Build a (date, close) frame sorted oldest -> newest."""
    dates = pd.bdate_range("2025-01-01", periods=len(closes))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": closes})


def test_returns_on_known_series():
    # 30 rows, close rising linearly from 100 to 129. The 1-month lookback is
    # 21 trading days, so the base close is close[8] = 108 and the exact 1M
    # return is 129 / 108 - 1 = 21 / 108.
    s = compute_signals(frame(list(range(100, 130))))
    assert s["return_1m"] == pytest.approx(21 / 108)
    assert math.isnan(s["return_12m"])


def test_rsi14_bounds_and_all_gains_case():
    # 20 rows of strictly rising closes: there are no losses at all, so RSI
    # saturates at 100.
    s = compute_signals(frame([100.0 + i for i in range(20)]))
    assert s["rsi14"] == pytest.approx(100.0)


def test_cross_flags_none_on_short_series():
    # 100 rows is below the 200-row window the SMA cross flags need.
    s = compute_signals(frame([100.0 + i for i in range(100)]))
    assert s["sma50_above_sma200"] is None
    assert s["golden_cross_recent"] is False
    assert s["death_cross_recent"] is False


def test_volatility_and_drawdown():
    # Non-decreasing series with alternating flat/up steps: every close is a
    # running maximum, so the drawdown never dips below zero.
    closes = [100.0 + i // 2 for i in range(40)]
    s = compute_signals(frame(closes))
    assert s["max_drawdown"] == pytest.approx(0.0)
    assert s["annualized_volatility"] >= 0
