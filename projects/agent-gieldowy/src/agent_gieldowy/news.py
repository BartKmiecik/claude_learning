"""Recent financial headlines from RSS feeds (bankier.pl, money.pl fallback)."""

import json
from pathlib import Path

import feedparser

from agent_gieldowy.collector import CollectorError, http_get

NEWS_FEEDS = [
    "https://www.bankier.pl/rss/wiadomosci.xml",
    "https://www.money.pl/rss/main.xml",
]


def fetch_news(feed_urls, limit: int = 20, session=None) -> list:
    """Latest `limit` items across feeds as [{'title', 'published', 'link'}].

    A failing feed is skipped — one dead feed must not kill collect.
    """
    items = []
    for url in feed_urls:
        try:
            resp = http_get(url, session=session)
        except CollectorError:
            continue
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            items.append(
                {
                    "title": entry.get("title", ""),
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                }
            )
    return items[-limit:] if len(items) > limit else items


def save_news(items: list, data_dir) -> None:
    path = Path(data_dir) / "news.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
