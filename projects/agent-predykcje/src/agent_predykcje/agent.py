"""The agent: one Claude API call per stock, persona in system, structured prediction out.

Model: claude-opus-5-5 by default, overridable via AGENT_PREDYKCJE_MODEL.
Structured output via output_config.format (never the deprecated output_format,
never assistant prefill). Invalid or refused responses are retried once, then
reported — an invalid prediction is never silently persisted.
"""

import json
import math
import os
import time

import anthropic

PREDICTION_SCHEMA = {
    "type": "object",
    "properties": {
        "predictions": {
            "type": "object",
            "properties": {
                "1d": {"type": "number"},
                "1w": {"type": "number"},
                "1m": {"type": "number"},
            },
            "required": ["1d", "1w", "1m"],
            "additionalProperties": False,
        },
        "justification": {"type": "string"},
    },
    "required": ["predictions", "justification"],
    "additionalProperties": False,
}


class AgentError(Exception):
    """User-facing agent failure (Polish message)."""


def default_model() -> str:
    return os.environ.get("AGENT_PREDYKCJE_MODEL", "claude-opus-5-5")


def make_client():
    """Construct the Anthropic client, translating a broken-credentials file
    into the Polish guidance (SDK 2.x raises CredentialsError at construction)."""
    try:
        return anthropic.Anthropic()
    except anthropic.CredentialsError as exc:
        raise AgentError(
            "brak poprawnych danych uwierzytelniających Claude API — uruchom `ant auth login` "
            "albo ustaw zmienną ANTHROPIC_API_KEY"
        ) from exc


def fmt(value, pct: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if pct:
        return f"{value:.1%}"
    return f"{value:.2f}"


def _signals_line(symbol: str, s: dict) -> str:
    return (
        f"{symbol}: 1M {fmt(s['return_1m'], pct=True)}, 3M {fmt(s['return_3m'], pct=True)}, "
        f"12M {fmt(s['return_12m'], pct=True)}, momentum6M {fmt(s['momentum_6m'], pct=True)}, "
        f"zmienność roczna {fmt(s['annualized_volatility'], pct=True)}, RSI14 {fmt(s['rsi14'])}, "
        f"SMA50 {fmt(s['sma50'])}, SMA200 {fmt(s['sma200'])}, "
        f"maxDD {fmt(s['max_drawdown'], pct=True)}, "
        f"SMA50>SMA200 {fmt(s['sma50_above_sma200'])}, "
        f"goldenCross {s['golden_cross_recent']}, deathCross {s['death_cross_recent']}"
    )


def build_user_message(
    symbol: str,
    anchor: dict,
    signals: dict,
    index_signals: dict,
    news_items: list,
    recent_prices: list | None = None,
) -> str:
    """Polish prompt: price history, market data, index context, news, task."""
    index_lines = "\n".join(_signals_line(sym, s) for sym, s in index_signals.items())
    news = (
        "\n".join(f"- {n['title']} ({n['published']})" for n in news_items)
        or "- (brak)"
    )
    history = "\n".join(recent_prices) if recent_prices else "—"
    return (
        f"DANE RYNKOWE:\n"
        f"Symbol: {symbol}\n"
        f"Cena: {fmt(anchor['price'])} zł\n"
        f"Data: {anchor['date']}\n"
        f"{_signals_line(symbol, signals)}\n"
        f"HISTORIA CEN (ostatnie sesje):\n{history}\n\n"
        f"KONTEKST INDEKSÓW:\n{index_lines}\n\n"
        f"NAJNOWSZE NAGŁÓWKI:\n{news}\n\n"
        f"ZADANIE: Przewidź cenę akcji {symbol} w trzech horyzontach: "
        f"1 dzień, 1 tydzień, 1 miesiąc. Zwróć wyłącznie JSON zgodny ze schematem."
    )


def validate_prediction(prediction: dict, anchor_price: float) -> list:
    """Validate a structured prediction against the anchor price.

    Every predicted price must be a number within 50%–150% of the anchor,
    and the justification must be a non-empty string. Returns a list of
    Polish error strings; an empty list means the prediction is valid.
    """
    if not isinstance(prediction, dict):
        return ["odpowiedź nie jest obiektem JSON"]
    predictions = prediction.get("predictions", {})
    if not isinstance(predictions, dict):
        return ["pole 'predictions' musi być obiektem"]
    errors = []
    for horizon in ("1d", "1w", "1m"):
        value = predictions.get(horizon)
        if not isinstance(value, (int, float)):
            errors.append(f"brak prognozy liczbowej dla horyzontu {horizon}")
            continue
        if not 0.5 * anchor_price <= value <= 1.5 * anchor_price:
            errors.append(f"prognoza {horizon} poza zakresem 50–150% ceny bazowej")
    justification = prediction.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        errors.append("brak uzasadnienia")
    return errors


def predict_stock(
    persona_prompt: str,
    user_message: str,
    anchor_price: float,
    client=None,
    model=None,
) -> dict:
    """Validated per-stock prediction; retries once on any recoverable failure."""
    client = client or make_client()
    model = model or default_model()
    last_error = None
    for attempt in range(2):
        try:
            response = client.messages().create(
                model=model,
                max_tokens=16000,
                system=persona_prompt,
                output_config={
                    "format": {"type": "json_schema", "schema": PREDICTION_SCHEMA},
                    "effort": "medium",
                },
                # The pinned betas/fallbacks shape; the non-beta create has no
                # betas/fallbacks kwargs in SDK 2.x, so send the wire form.
                extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                extra_body={"fallbacks": "default"},
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.RateLimitError as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
            continue
        except TypeError as exc:
            # SDK 2.x raises a client-side TypeError (not AuthenticationError)
            # when no credentials resolve — translate to the Polish guidance;
            # any other TypeError is a programming error and must propagate.
            message = str(exc).lower()
            if "authentication" in message or "credentials" in message:
                raise AgentError(
                    "brak danych uwierzytelniających Claude API — uruchom `ant auth login` "
                    "albo ustaw zmienną ANTHROPIC_API_KEY"
                ) from exc
            raise
        except anthropic.APIConnectionError as exc:
            raise AgentError(f"brak połączenia z API: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise AgentError(
                "brak danych uwierzytelniających Claude API — uruchom `ant auth login` "
                "albo ustaw zmienną ANTHROPIC_API_KEY"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AgentError(f"błąd API ({exc.status_code}): {exc.message}") from exc
        if response.stop_reason == "refusal":
            raise AgentError("model odmówił odpowiedzi — pomijam tego agenta")
        try:
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            prediction = json.loads(text)
            errors = validate_prediction(prediction, anchor_price)
        except (AttributeError, TypeError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        if not errors:
            return {
                "predictions": {
                    h: float(prediction["predictions"][h]) for h in ("1d", "1w", "1m")
                },
                "justification": prediction["justification"],
            }
        last_error = AgentError("; ".join(errors))
    raise AgentError(f"prognoza niepoprawna po ponowieniu: {last_error}")
