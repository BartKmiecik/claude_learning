import pandas as pd
import pytest
import requests

from agent_predykcje.collector import CollectorError, collect, fetch_quotes, http_get


class FakeResponse:
    """Minimal stand-in for requests.Response carrying a .json() payload."""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def yahoo_payload(dates, closes):
    """Yahoo chart JSON shape: UTC-seconds timestamps plus close prices."""
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [
                        int(pd.Timestamp(d, tz="UTC").timestamp()) for d in dates
                    ],
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }


def recent_dates(n=3):
    """n calendar days ending today, newest first, as ISO strings."""
    today = pd.Timestamp.now().normalize()
    return [(today - pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(n)]


def test_fetch_quotes_returns_date_close_frame(monkeypatch):
    dates = recent_dates(3)  # newest first, like the real Yahoo payload
    closes = [52.5, 53.0, 51.75]
    monkeypatch.setattr(
        "agent_predykcje.collector.http_get",
        lambda url, params=None, session=None: FakeResponse(
            yahoo_payload(dates, closes)
        ),
    )
    df = fetch_quotes("PKO.WA", "stock")
    assert list(df.columns) == ["date", "close"]
    assert df["date"].tolist() == sorted(dates)  # oldest→newest
    assert df["close"].dtype == float
    assert df["close"].tolist() == [51.75, 53.0, 52.5]  # reordered with dates


def test_collect_writes_incremental_csv(tmp_path, monkeypatch):
    dates = recent_dates(3)
    closes = [100.0, 101.0, 102.0]
    monkeypatch.setattr(
        "agent_predykcje.collector.http_get",
        lambda url, params=None, session=None: FakeResponse(
            yahoo_payload(dates, closes)
        ),
    )
    watchlist = {"stocks": ["PKO.WA"]}
    data_dir = tmp_path / "data"
    collect(watchlist, data_dir)
    collect(watchlist, data_dir)  # second run must not duplicate rows
    path = data_dir / "PKO.WA.csv"
    assert path.exists()
    stored = pd.read_csv(path)
    assert not stored["date"].duplicated().any()
    assert len(stored) == 3


def test_collect_reports_unknown_symbol_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agent_predykcje.collector.http_get",
        lambda url, params=None, session=None: FakeResponse(
            {"chart": {"result": None}}
        ),
    )
    results = collect({"stocks": ["PKO.WA"]}, tmp_path / "data")
    assert results["PKO.WA"]["status"] == "error"
    assert "PKO.WA" in results["PKO.WA"]["error"]


def test_http_get_retries_then_raises_collector_error(monkeypatch):
    class BoomSession:
        def __init__(self):
            self.calls = 0

        def get(self, url, params=None, headers=None, timeout=None):
            self.calls += 1
            raise requests.RequestException("connection refused")

    session = BoomSession()
    monkeypatch.setattr("agent_predykcje.collector.time.sleep", lambda s: None)
    with pytest.raises(CollectorError):
        http_get(
            "https://query1.finance.yahoo.com/v8/finance/chart/PKO.WA", session=session
        )
    assert session.calls == 3
