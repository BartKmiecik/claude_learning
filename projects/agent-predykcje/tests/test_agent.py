from types import SimpleNamespace

import anthropic
import pytest

from agent_predykcje.agent import (
    AgentError,
    build_user_message,
    default_model,
    make_client,
    predict_stock,
    validate_prediction,
    PREDICTION_SCHEMA,
    _signals_line,
)

SIGNALS = {
    "return_1m": 0.10,
    "return_3m": 0.20,
    "return_12m": 0.30,
    "momentum_6m": 0.05,
    "annualized_volatility": 0.25,
    "rsi14": 55.0,
    "sma50": 61.0,
    "sma200": 60.0,
    "max_drawdown": -0.10,
    "sma50_above_sma200": True,
    "golden_cross_recent": False,
    "death_cross_recent": False,
}


class FakeClient:
    """SDK-shaped fake: client.messages is a resource object, not a method."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = self._Messages(self)

    class _Messages:
        def __init__(self, client):
            self.client = client

        def create(self, **kwargs):
            kind = self.client.responses.pop(0)
            if isinstance(kind, Exception):
                raise kind
            return kind


class CapturingClient:
    """FakeClient variant that records the kwargs of the last create() call."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.kwargs = None
        self.messages = self._Messages(self)

    class _Messages:
        def __init__(self, client):
            self.client = client

        def create(self, **kwargs):
            self.client.kwargs = kwargs
            kind = self.client.responses.pop(0)
            if isinstance(kind, Exception):
                raise kind
            return kind


def _ok_response():
    # object with .content = [TextBlock("{\"predictions\":{\"1d\":62.4,\"1w\":63.2,\"1m\":65.1},\"justification\":\"Trend wzrostowy\"}")]
    # and .stop_reason = "end_turn"
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text='{"predictions":{"1d":62.4,"1w":63.2,"1m":65.1},"justification":"Trend wzrostowy"}',
            )
        ],
        stop_reason="end_turn",
    )


def test_predict_stock_returns_validated_dict():
    client = FakeClient([_ok_response()])
    result = predict_stock("prompt", "msg", 62.0, client=client, model="m")
    assert result["predictions"] == {"1d": 62.4, "1w": 63.2, "1m": 65.1}
    assert result["justification"] == "Trend wzrostowy"


def test_predict_stock_invalid_json_retries_then_raises():
    bad = _ok_response()  # content text = "not json"
    bad.content[0].text = "not json"
    client = FakeClient([bad, bad])
    with pytest.raises(AgentError):
        predict_stock("p", "m", 62.0, client=client, model="m")


def test_predict_stock_ratelimit_retries_once():
    # SDK 2.x exception constructors require a real httpx2.Response, so build
    # the instance the Project 2 way (__new__ skips the constructor).
    rate_limit = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    client = FakeClient([rate_limit, _ok_response()])
    result = predict_stock("p", "m", 62.0, client=client, model="m")
    assert result["predictions"]["1m"] == 65.1


def test_validate_prediction_out_of_range():
    pred = {"predictions": {"1d": 62.0, "1w": 63.0, "1m": 100.0}, "justification": "x"}
    errors = validate_prediction(pred, 62.0)
    assert any("1m" in e for e in errors)


def test_validate_prediction_missing_justification():
    pred = {"predictions": {"1d": 62.0, "1w": 63.0, "1m": 64.0}}
    assert validate_prediction(pred, 62.0)  # non-empty error list


def test_refusal_stop_reason_raises():
    resp = _ok_response()
    resp.stop_reason = "refusal"
    client = FakeClient([resp])
    with pytest.raises(AgentError):
        predict_stock("p", "m", 62.0, client=client, model="m")


def test_make_client_credentials_error(monkeypatch):
    def boom():
        raise anthropic.CredentialsError("bad")

    monkeypatch.setattr("agent_predykcje.agent.anthropic.Anthropic", boom)
    with pytest.raises(AgentError, match="ant auth login"):
        make_client()


def test_default_model_env_override(monkeypatch):
    monkeypatch.setenv("AGENT_PREDYKCJE_MODEL", "claude-sonnet-5-5")
    assert default_model() == "claude-sonnet-5-5"


def test_predict_stock_pins_wire_shape():
    """max_tokens, output_config, the beta header and fallbacks must not drift."""
    client = CapturingClient([_ok_response()])
    predict_stock("p", "m", 62.0, client=client, model="m")
    kwargs = client.kwargs
    assert kwargs["max_tokens"] == 16000
    assert kwargs["output_config"]["format"]["type"] == "json_schema"
    assert kwargs["output_config"]["effort"] == "medium"
    assert (
        kwargs["extra_headers"]["anthropic-beta"]
        == "server-side-fallback-2026-07-01"
    )
    assert kwargs["extra_body"] == {"fallbacks": "default"}


def test_predict_stock_typeerror_credentials_translated():
    # SDK 2.x raises a TypeError mentioning authentication when no credentials
    # resolve — must be translated to the Polish `ant auth login` guidance.
    client = FakeClient([TypeError("no authentication credentials provided")])
    with pytest.raises(AgentError, match="ant auth login"):
        predict_stock("p", "m", 62.0, client=client, model="m")


def test_predict_stock_other_typeerror_propagates():
    client = FakeClient([TypeError("unrelated programming bug")])
    with pytest.raises(TypeError):
        predict_stock("p", "m", 62.0, client=client, model="m")


def test_signals_line_renders_none_as_dash():
    # sma50_above_sma200 is None on short series; the Polish prompt must not
    # leak the literal English "None" — it renders as "—" like other NAs.
    line = _signals_line("PKO.WA", dict(SIGNALS, sma50_above_sma200=None))
    assert "None" not in line
    assert "SMA50>SMA200 —" in line


def test_build_user_message_includes_price_history():
    message = build_user_message(
        "PKO.WA",
        {"date": "2026-10-27", "price": 62.0},
        SIGNALS,
        {},
        [],
        recent_prices=["2026-10-23: 61,50", "2026-10-26: 62,00"],
    )
    assert "HISTORIA CEN" in message
    assert "2026-10-23: 61,50" in message
    assert "2026-10-26: 62,00" in message
