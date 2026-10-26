import json
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import requests


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class FakeSession:
    """Scripted responses, one per get() call, consumed in order.

    A response may be a FakeResponse or a callable(url, params, headers, timeout)
    that raises — callables let tests script network failures.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        response = self.responses.pop(0)
        if callable(response):
            return response(url, params, headers, timeout)
        return response


def yahoo_payload(dates, closes):
    """Minimal Yahoo chart API v8 payload for the given business-day dates and closes."""
    timestamps = [int(pd.Timestamp(d).timestamp()) for d in dates]
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }


def bankier_payload(dates, navs):
    """Minimal bankier fund chart payload: data[0].data = [[epoch_ms, nav], ...]."""
    rows = [
        [int(pd.Timestamp(d).timestamp() * 1000), nav] for d, nav in zip(dates, navs)
    ]
    return {"parameters": {"symbol": "X", "range": "max"}, "data": [{"data": rows}]}


def bdate_range(days):
    return pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=days)


@pytest.fixture
def watchlist():
    return {
        "stocks": ["PKO.WA"],
        "indices": ["WIG20.WA"],
        "funds": ["AGF04"],
    }
