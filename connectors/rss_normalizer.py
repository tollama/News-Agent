"""Normalizer for RSS feed entries to ArticleSnapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from schemas.article import ArticleSnapshot
from schemas.enums import NewsProvider

from connectors.newsapi_normalizer import infer_category


def normalize_to_snapshot(raw: dict[str, Any]) -> ArticleSnapshot:
    """Convert a normalized RSS entry dict to an ArticleSnapshot."""
    published_at = raw.get("published_at", "")
    pub_dt = datetime.now(UTC)
    if isinstance(published_at, str) and published_at:
        try:
            pub_dt = parsedate_to_datetime(published_at)
        except (ValueError, TypeError):
            try:
                pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                pass

    headline = raw.get("headline", "untitled")
    return ArticleSnapshot(
        ts=datetime.now(UTC),
        article_id=raw.get("article_id", ""),
        source_name=raw.get("source_name", "unknown"),
        source_url=raw.get("source_url", ""),
        headline=headline,
        body=raw.get("body"),
        category=infer_category(headline),
        provider=NewsProvider.RSS,
        published_at=pub_dt,
        language="en",
        author=raw.get("author"),
    )


__all__ = ["normalize_to_snapshot"]
