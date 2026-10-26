import json
from types import SimpleNamespace

import anthropic
import pytest

from agent_gieldowy.agent import (
    AgentError,
    PREDICTION_SCHEMA,
    analyze,
    build_signals_table,
    build_user_message,
    default_model,
    fmt,
    validate_prediction,
)


def valid_prediction(symbols=("PKO.WA",)):
    return {
        "horizon": "1M",
        "predictions": [
            {
                "symbol": s,
                "direction": "up",
                "range_pct": {"min": -5.0, "max": 8.0},
                "confidence": 65,
                "rationale": "Stabilne fundamenty.",
                "risks": ["Ryzyko polityczne"],
            }
            for s in symbols
        ],
        "summary": "Ostrożnie pozytywnie.",
        "analysis": "Pełna analiza w duchu persony.",
    }


class FakeMessages:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        text = json.dumps(payload)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    def __init__(self, payloads):
        self.messages = FakeMessages(payloads)


def test_default_model_uses_env(monkeypatch):
    assert default_model() == "claude-opus-5-5"
    monkeypatch.setenv("AGENT_GIELDOWY_MODEL", "claude-haiku-5-5")
    assert default_model() == "claude-haiku-5-5"


def test_fmt_handles_nan_and_percent():
    assert fmt(float("nan")) == "—"
    assert fmt(None) == "—"
    assert fmt(0.0523, pct=True) == "5.2%"
    assert fmt(1.2345) == "1.23"


def test_build_signals_table_renders_every_symbol():
    signals = {
        "PKO.WA": {
            "return_1m": 0.01,
            "return_3m": 0.03,
            "return_12m": 0.12,
            "annualized_volatility": 0.18,
            "momentum_6m": 0.05,
            "sma50": 51.0,
            "sma200": 49.0,
            "rsi14": 55.0,
            "max_drawdown": -0.2,
            "sma50_above_sma200": True,
            "golden_cross_recent": False,
            "death_cross_recent": False,
        }
    }
    table = build_signals_table(signals)
    assert "PKO.WA" in table
    assert "1M 1.0%" in table
    assert "maxDD -20.0%" in table


def test_build_user_message_contains_data_news_digest_and_task():
    digest = {
        "recent": [
            {
                "id": "a",
                "created_at": "2026-10-01T00:00:00+00:00",
                "prediction": valid_prediction(),
            }
        ],
        "older": [],
        "total_entries": 1,
    }
    msg = build_user_message(
        "PKO.WA: 1M 1.0%",
        [
            {
                "title": "Bankier: wzrosty na GPW",
                "published": "2026-10-26",
                "link": "https://x/1",
            }
        ],
        digest,
        ["PKO.WA"],
    )
    assert "PKO.WA: 1M 1.0%" in msg
    assert "Bankier: wzrosty na GPW" in msg
    assert "2026-10-01" in msg
    assert "PKO.WA" in msg
    assert "±2%" in msg  # sideways definition reaches the model


def test_validate_prediction_accepts_valid():
    assert validate_prediction(valid_prediction(["PKO.WA"]), ["PKO.WA"]) == []


def test_analyze_returns_prediction_with_generated_at():
    client = FakeClient([valid_prediction()])
    result = analyze("prompt", "msg", ["PKO.WA"], client=client)
    assert result["horizon"] == "1M"
    assert result["generated_at"].startswith("2026")
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["system"] == "prompt"
    assert call["output_config"]["format"]["schema"] == PREDICTION_SCHEMA
    assert call["max_tokens"] == 16000


def test_analyze_rejects_missing_and_unknown_symbols():
    # Review Focus #3: schema-valid JSON that misses an instrument / invents one
    bad = valid_prediction(["PKO.WA"])  # missing WIG20.WA, plus... make one up:
    bad["predictions"].append(
        {
            "symbol": "FAKE.WA",
            "direction": "up",
            "range_pct": {"min": -1, "max": 1},
            "confidence": 10,
            "rationale": "x",
            "risks": [],
        }
    )
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError) as exc:
        analyze("p", "m", ["PKO.WA", "WIG20.WA"], client=client)
    assert "WIG20.WA" in str(exc.value)
    assert "FAKE.WA" in str(exc.value)
    assert len(client.messages.calls) == 2  # one retry, then give up


def test_analyze_rejects_inverted_range():
    bad = valid_prediction()
    bad["predictions"][0]["range_pct"] = {"min": 8.0, "max": -5.0}
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError):
        analyze("p", "m", ["PKO.WA"], client=client)
    assert len(client.messages.calls) == 2


def test_analyze_retries_after_rate_limit_then_succeeds():
    rate_limit = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    client = FakeClient([rate_limit, valid_prediction()])
    result = analyze("p", "m", ["PKO.WA"], client=client)
    assert result["predictions"][0]["symbol"] == "PKO.WA"
    assert len(client.messages.calls) == 2


def test_analyze_wraps_auth_error_with_instruction():
    auth = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    client = FakeClient([auth, auth])
    with pytest.raises(AgentError) as exc:
        analyze("p", "m", ["PKO.WA"], client=client)
    assert "ant auth login" in str(exc.value)


def test_analyze_parses_garbage_then_retries():
    class Garbage:
        pass

    client = FakeClient([Garbage(), valid_prediction()])
    result = analyze("p", "m", ["PKO.WA"], client=client)
    assert result["predictions"][0]["symbol"] == "PKO.WA"
