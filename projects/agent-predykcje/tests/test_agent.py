from types import SimpleNamespace

import anthropic
import pytest

from agent_predykcje.agent import (
    AgentError,
    default_model,
    make_client,
    predict_stock,
    validate_prediction,
    PREDICTION_SCHEMA,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def messages(self):
        return self

    def create(self, **kwargs):
        kind = self.responses.pop(0)
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
