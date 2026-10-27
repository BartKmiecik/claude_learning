import pytest

from agent_predykcje.collector import CollectorError
from agent_predykcje.news import fetch_news, load_news, save_news

RSS_A = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>a</title>
<item><title>Starszy z A</title><pubDate>Mon, 20 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/a1</link></item>
<item><title>Nowszy z A</title><pubDate>Wed, 22 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/a2</link></item>
</channel></rss>
"""

RSS_B = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>b</title>
<item><title>Najnowszy z B</title><pubDate>Thu, 23 Oct 2026 09:00:00 GMT</pubDate><link>https://example.com/b1</link></item>
</channel></rss>
"""


class FakeResponse:
    """Minimal stand-in for requests.Response carrying raw bytes content."""

    def __init__(self, content):
        self.content = content


def test_fetch_news_merges_sorts_limits(monkeypatch):
    monkeypatch.setattr(
        "agent_predykcje.news.http_get",
        lambda url, session=None: FakeResponse(RSS_B if "b" in url else RSS_A),
    )
    items = fetch_news(["https://a.example/rss", "https://b.example/rss"], limit=2)
    assert [item["title"] for item in items] == ["Najnowszy z B", "Nowszy z A"]
    assert all(set(item) == {"title", "published", "link"} for item in items)


def test_fetch_news_skips_dead_feed(monkeypatch):
    def responses(url, session=None):
        if "dead" in url:
            raise CollectorError("dead feed")
        return FakeResponse(RSS_A)

    monkeypatch.setattr("agent_predykcje.news.http_get", responses)
    items = fetch_news(
        ["https://dead.example/rss", "https://live.example/rss"], limit=10
    )
    assert len(items) == 2  # only the live feed contributed


def test_save_and_load_news_roundtrip(tmp_path):
    items = [
        {
            "title": "Nagłówek",
            "published": "Thu, 23 Oct 2026 09:00:00 GMT",
            "link": "https://example.com/1",
        }
    ]
    save_news(items, tmp_path)
    assert load_news(tmp_path) == items
    assert load_news(tmp_path / "empty") == []  # missing file
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "news.json").write_text("{nie-json", encoding="utf-8")
    assert load_news(broken) == []  # unparseable file
