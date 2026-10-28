"""Recent financial headlines from RSS feeds (bankier.pl, money.pl fallback)."""

import json
from pathlib import Path
import time

import feedparser

from agent_predykcje.collector import CollectorError, http_get

NEWS_FEEDS = [
    "https://www.bankier.pl/rss/wiadomosci.xml",
    "https://www.money.pl/rss/main.xml",
]


def fetch_news(feed_urls, limit: int = 20, session=None) -> list:
    """Latest `limit` items across feeds as [{'title', 'published', 'link'}].

    Feeds are merged and sorted newest-first by their published timestamp;
    a failing feed is skipped — one dead feed must not kill collect.
    """
    if limit <= 0:
        return []
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
                    "_published_parsed": entry.get("published_parsed"),
                }
            )
    oldest = time.struct_time((1900, 1, 1, 0, 0, 0, 0, 0, -1))
    items.sort(key=lambda item: item["_published_parsed"] or oldest, reverse=True)
    for item in items:
        item.pop("_published_parsed")
    return items[:limit]


def save_news(items: list, data_dir) -> None:
    path = Path(data_dir) / "news.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_news(data_dir) -> list:
    """Read data/news.json back as a list; [] when missing or unparseable."""
    path = Path(data_dir) / "news.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
