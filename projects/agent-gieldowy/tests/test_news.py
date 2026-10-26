import json

import pytest

from agent_gieldowy.news import NEWS_FEEDS, fetch_news, save_news
from conftest import FakeResponse, FakeSession

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title>
<item><title>Pierwszy nagłówek</title><pubDate>Mon, 20 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/1</link></item>
<item><title>Drugi nagłówek</title><pubDate>Tue, 21 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/2</link></item>
<item><title>Trzeci nagłówek</title><pubDate>Wed, 22 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/3</link></item>
</channel></rss>
"""


def test_fetch_news_parses_items_and_applies_limit():
    session = FakeSession([FakeResponse(text=RSS_XML)])
    items = fetch_news(["https://feed.example/rss"], limit=2, session=session)
    assert len(items) == 2
    assert items[0]["title"] == "Drugi nagłówek"  # latest `limit` items win
    assert items[0]["link"] == "https://example.com/2"


def test_fetch_news_skips_dead_feed():
    def boom(url, params=None, headers=None, timeout=None):
        from agent_gieldowy.collector import CollectorError

        raise CollectorError("dead feed")

    session = FakeSession([boom, FakeResponse(text=RSS_XML)])
    items = fetch_news(
        ["https://dead.example/rss", "https://live.example/rss"],
        limit=10,
        session=session,
    )
    assert len(items) == 3  # only the live feed contributed


def test_save_news_writes_json(tmp_path):
    items = [{"title": "X", "published": "2026-10-26", "link": "https://example.com/x"}]
    save_news(items, tmp_path)
    loaded = json.loads((tmp_path / "news.json").read_text(encoding="utf-8"))
    assert loaded == items


def test_news_feeds_are_configured():
    assert len(NEWS_FEEDS) >= 1
    assert all(u.startswith("https://") for u in NEWS_FEEDS)
