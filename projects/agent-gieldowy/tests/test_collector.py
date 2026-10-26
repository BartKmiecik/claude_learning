import pandas as pd
import pytest
import requests

from agent_gieldowy.collector import (
    CollectorError,
    UnknownSymbolError,
    collect,
    fetch_quotes,
    save_incremental,
)
from agent_gieldowy.config import all_symbols, load_watchlist
from conftest import (
    FakeResponse,
    FakeSession,
    bankier_payload,
    bdate_range,
    yahoo_payload,
)


def test_load_watchlist_and_all_symbols(tmp_path, watchlist):
    p = tmp_path / "watchlist.yaml"
    p.write_text(
        "stocks:\n  - PKO.WA\nindices:\n  - WIG20.WA\nfunds:\n  - AGF04\n",
        encoding="utf-8",
    )
    wl = load_watchlist(p)
    assert all_symbols(wl) == [
        {"symbol": "PKO.WA", "kind": "stock"},
        {"symbol": "WIG20.WA", "kind": "index"},
        {"symbol": "AGF04", "kind": "fund"},
    ]


def test_fetch_quotes_stock_trims_to_365_days():
    dates = bdate_range(800)  # ~3 years of business days
    closes = [100.0 + i * 0.1 for i in range(800)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    assert len(df) < 800
    assert (
        df["date"]
        >= (pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
    ).all()
    assert list(df.columns) == ["date", "close"]
    assert df["date"].is_monotonic_increasing


def test_fetch_quotes_fund_parses_bankier_payload():
    dates = bdate_range(400)
    navs = [50.0 + i * 0.05 for i in range(400)]
    session = FakeSession([FakeResponse(bankier_payload(dates, navs))])
    df = fetch_quotes("AGF04", "fund", session)
    assert len(df) < 400  # trimmed to the last 365 calendar days
    assert (
        df["date"]
        >= (pd.Timestamp.now().normalize() - pd.Timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
    ).all()
    assert df["close"].iloc[-1] == pytest.approx(69.95)  # 50.0 + 399*0.05


def test_unknown_symbol_reported_not_fatal(tmp_path, watchlist):
    # Review Focus #1: empty result for one symbol must not abort the others
    session = FakeSession(
        [
            FakeResponse({"chart": {"result": None}}),  # PKO.WA unknown
            FakeResponse(yahoo_payload(bdate_range(400), [100.0] * 400)),  # WIG20.WA ok
            FakeResponse(bankier_payload(bdate_range(400), [50.0] * 400)),  # AGF04 ok
        ]
    )
    results = collect(watchlist, tmp_path / "data", session)
    assert results["PKO.WA"]["status"] == "error"
    assert "PKO.WA" in results["PKO.WA"]["error"]
    assert results["WIG20.WA"]["status"] == "ok"
    assert results["AGF04"]["status"] == "ok"


def test_malformed_payload_reported_not_fatal(tmp_path, watchlist):
    # A malformed payload (unknown/renamed fund shape) must not abort the batch
    session = FakeSession(
        [
            FakeResponse(yahoo_payload(bdate_range(400), [100.0] * 400)),  # PKO.WA ok
            FakeResponse(yahoo_payload(bdate_range(400), [200.0] * 400)),  # WIG20.WA ok
            FakeResponse({"data": []}),  # AGF04 malformed
        ]
    )
    results = collect(watchlist, tmp_path / "data", session)
    assert results["AGF04"]["status"] == "error"
    assert results["PKO.WA"]["status"] == "ok"
    assert results["WIG20.WA"]["status"] == "ok"


def test_incremental_no_duplicates(tmp_path):
    # Review Focus #2: collecting twice on the same day appends nothing new
    dates = bdate_range(400)
    closes = [100.0 + i for i in range(400)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    first = save_incremental("PKO.WA", df, tmp_path)
    second = save_incremental("PKO.WA", df, tmp_path)
    stored = pd.read_csv(tmp_path / "PKO.WA.csv")
    assert first == len(df)
    assert second == 0
    assert not stored["date"].duplicated().any()


def test_incremental_appends_only_new_rows(tmp_path):
    dates = bdate_range(400)
    closes = [100.0 + i for i in range(400)]
    session = FakeSession([FakeResponse(yahoo_payload(dates, closes))])
    df = fetch_quotes("PKO.WA", "stock", session)
    save_incremental("PKO.WA", df, tmp_path)
    new_day = pd.Timestamp(dates[-1]) + pd.Timedelta(days=1)
    new_rows = pd.DataFrame({"date": [new_day.strftime("%Y-%m-%d")], "close": [999.0]})
    appended = save_incremental("PKO.WA", new_rows, tmp_path)
    stored = pd.read_csv(tmp_path / "PKO.WA.csv")
    assert appended == 1
    assert stored.iloc[-1]["close"] == 999.0


def test_retries_then_raises_on_persistent_network_error():
    def boom(url, params=None, headers=None, timeout=None):
        raise requests.RequestException("connection refused")

    session = FakeSession([boom, boom, boom])
    with pytest.raises(CollectorError):
        fetch_quotes("PKO.WA", "stock", session)
    assert len(session.calls) == 3
