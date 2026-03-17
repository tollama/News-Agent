"""Generic RSS/Atom feed connector."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import feedparser


class RSSConnector:
    """Connector that fetches and parses RSS/Atom feeds."""

    provider_name = "rss"

    def __init__(
        self,
        feed_urls: list[str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._feed_urls = feed_urls or []
        self._timeout = timeout

    async def fetch_articles(
        self,
        *,
        query: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and filter articles from configured RSS feeds."""
        loop = asyncio.get_running_loop()
        all_articles: list[dict[str, Any]] = []

        for url in self._feed_urls:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries:
                article = _normalize_rss_entry(entry, url)
                # Simple keyword filtering
                headline_lower = article.get("headline", "").lower()
                body_lower = (article.get("body") or "").lower()
                if query.lower() in headline_lower or query.lower() in body_lower:
                    all_articles.append(article)

        return all_articles[:limit]


def _normalize_rss_entry(entry: Any, feed_url: str) -> dict[str, Any]:
    """Normalize an RSS feed entry to a flat dict."""
    published = entry.get("published", entry.get("updated", ""))
    return {
        "article_id": entry.get("link", entry.get("id", "")),
        "source_name": entry.get("source", {}).get("title", feed_url),
        "source_url": entry.get("link", ""),
        "headline": entry.get("title", ""),
        "body": entry.get("summary", entry.get("description", "")),
        "author": entry.get("author"),
        "published_at": published,
        "provider": "rss",
    }


__all__ = ["RSSConnector"]
