"""Tests for connectors.rss."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

# Mock feedparser before importing the connector (sgmllib may not be available)
_mock_feedparser = MagicMock()
sys.modules.setdefault("feedparser", _mock_feedparser)

import pytest  # noqa: E402

from connectors.rss import RSSConnector  # noqa: E402


def _make_entry(**kwargs) -> SimpleNamespace:
    """Create a mock feed entry with a working .get() method."""
    defaults = {
        "title": "",
        "link": "",
        "summary": "",
        "description": "",
        "published": "",
        "updated": "",
        "id": "",
        "author": None,
        "source": {},
    }
    defaults.update(kwargs)
    entry = SimpleNamespace(**defaults)
    entry.get = lambda k, d="": getattr(entry, k, d)
    return entry


def _make_feed(entries: list) -> SimpleNamespace:
    return SimpleNamespace(entries=entries)


@pytest.mark.asyncio()
async def test_fetch_articles_keyword_match():
    connector = RSSConnector(feed_urls=["https://example.com/feed"])
    feed = _make_feed([
        _make_entry(title="AI breakthrough announced", link="https://example.com/1", summary="Major AI advancement"),
        _make_entry(title="Sports results today", link="https://example.com/2", summary="Football scores"),
    ])
    _mock_feedparser.parse.return_value = feed
    articles = await connector.fetch_articles(query="AI")

    assert len(articles) == 1
    assert articles[0]["headline"] == "AI breakthrough announced"
    assert articles[0]["provider"] == "rss"


@pytest.mark.asyncio()
async def test_fetch_articles_no_match():
    connector = RSSConnector(feed_urls=["https://example.com/feed"])
    feed = _make_feed([
        _make_entry(title="Sports results", link="https://example.com/1", summary="Football"),
    ])
    _mock_feedparser.parse.return_value = feed
    articles = await connector.fetch_articles(query="technology")

    assert articles == []
