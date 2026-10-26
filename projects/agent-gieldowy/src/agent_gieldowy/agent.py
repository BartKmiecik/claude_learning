"""The agent: one Claude API call, persona in system, structured prediction out.

Model: claude-opus-5-5 by default, overridable via AGENT_GIELDOWY_MODEL.
Structured output via output_config.format (never the deprecated output_format,
never assistant prefill). Invalid or refused responses are retried once, then
reported — an invalid prediction is never silently persisted.
"""

import json
import math
import os
import time
from datetime import datetime, timezone

import anthropic

PREDICTION_SCHEMA = {
    "type": "object",
    "properties": {
        "horizon": {"type": "string", "const": "1M"},
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "direction": {"type": "string", "enum": ["up", "down", "sideways"]},
                    "range_pct": {
                        "type": "object",
                        "properties": {
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                        },
                        "required": ["min", "max"],
                        "additionalProperties": False,
                    },
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string"},
                    "risks": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "symbol",
                    "direction",
                    "range_pct",
                    "confidence",
                    "rationale",
                    "risks",
                ],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
        "analysis": {"type": "string"},
    },
    "required": ["horizon", "predictions", "summary", "analysis"],
    "additionalProperties": False,
}


class AgentError(Exception):
    """User-facing agent failure (Polish message)."""


def default_model() -> str:
    return os.environ.get("AGENT_GIELDOWY_MODEL", "claude-opus-5-5")


def fmt(value, pct: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if pct:
        return f"{value:.1%}"
    return f"{value:.2f}"


def build_signals_table(signals_by_symbol: dict) -> str:
    lines = []
    for symbol, s in signals_by_symbol.items():
        lines.append(
            f"{symbol}: 1M {fmt(s['return_1m'], pct=True)}, 3M {fmt(s['return_3m'], pct=True)}, "
            f"12M {fmt(s['return_12m'], pct=True)}, momentum6M {fmt(s['momentum_6m'], pct=True)}, "
            f"zmienność roczna {fmt(s['annualized_volatility'], pct=True)}, RSI14 {fmt(s['rsi14'])}, "
            f"SMA50 {fmt(s['sma50'])}, SMA200 {fmt(s['sma200'])}, "
            f"maxDD {fmt(s['max_drawdown'], pct=True)}, "
            f"SMA50>SMA200 {s['sma50_above_sma200']}, "
            f"goldenCross {s['golden_cross_recent']}, deathCross {s['death_cross_recent']}"
        )
    return "\n".join(lines)


def build_user_message(
    signals_table: str, news_items: list, digest: dict, watchlist_symbols: list
) -> str:
    news = (
        "\n".join(f"- {n['title']} ({n['published']})" for n in news_items)
        or "- (brak)"
    )
    recent = json.dumps(digest["recent"], ensure_ascii=False, indent=2)
    older = json.dumps(digest["older"], ensure_ascii=False, indent=2)
    symbols = ", ".join(watchlist_symbols)
    return (
        f"DANE RYNKOWE (sygnały techniczne, 12 miesięcy):\n{signals_table}\n\n"
        f"NAJNOWSZE NAGŁÓWKI:\n{news}\n\n"
        f"TWÓJ DZIENNIK (przeszłość) — liczba wpisów: {digest['total_entries']}:\n"
        f"Ostatnie wpisy (pełne):\n{recent}\n"
        f"Starsze wpisy (skrót):\n{older}\n\n"
        f"ZADANIE: Oceń perspektywy i prognozuj zmianę kursu każdego instrumentu "
        f"na 1 miesiąc: {symbols}. Dla każdego podaj kierunek (up/down/sideways; "
        f"sideways = oczekiwana zmiana w przedziale ±2%), przedział zmiany % "
        f"(range_pct: min/max), pewność 0-100, uzasadnienie i ryzyka. "
        f"Uwzględnij swoją historię i skłonności z dziennika."
    )


def validate_prediction(prediction: dict, watchlist_symbols: list) -> list:
    errors = []
    if prediction.get("horizon") != "1M":
        errors.append("horizon musi być '1M'")
    predicted = {p["symbol"] for p in prediction.get("predictions", [])}
    expected = set(watchlist_symbols)
    missing = expected - predicted
    unknown = predicted - expected
    if missing:
        errors.append(f"brak prognoz dla: {', '.join(sorted(missing))}")
    if unknown:
        errors.append(f"nieznane symbole: {', '.join(sorted(unknown))}")
    for p in prediction.get("predictions", []):
        if p["range_pct"]["min"] > p["range_pct"]["max"]:
            errors.append(f"{p['symbol']}: range_pct min > max")
        if not 0 <= p["confidence"] <= 100:
            errors.append(f"{p['symbol']}: confidence poza 0-100")
    return errors


def analyze(
    persona_prompt: str,
    user_message: str,
    watchlist_symbols: list,
    client=None,
    model=None,
) -> dict:
    """Validated prediction dict with generated_at; retries once on any failure."""
    client = client or anthropic.Anthropic()
    model = model or default_model()
    last_error = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=16000,
                system=persona_prompt,
                output_config={
                    "format": {"type": "json_schema", "schema": PREDICTION_SCHEMA}
                },
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.RateLimitError as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
            continue
        except anthropic.APIConnectionError as exc:
            raise AgentError(f"brak połączenia z API: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise AgentError(
                "brak danych uwierzytelniających Claude API — uruchom `ant auth login` "
                "albo ustaw zmienną ANTHROPIC_API_KEY"
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AgentError(f"błąd API ({exc.status_code}): {exc.message}") from exc
        except TypeError as exc:
            # Serialization/type failure inside the client call (an unserializable
            # payload raises TypeError, not JSONDecodeError): treat it like an
            # invalid response and retry, per the brief's note on catching both.
            last_error = exc
            continue
        try:
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            prediction = json.loads(text)
        except (AttributeError, TypeError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        errors = validate_prediction(prediction, watchlist_symbols)
        if not errors:
            prediction["generated_at"] = datetime.now(timezone.utc).isoformat()
            return prediction
        last_error = AgentError("; ".join(errors))
    raise AgentError(f"prognoza niepoprawna po ponowieniu: {last_error}")
