"""Normalizer for GDELT raw article data to ArticleSnapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schemas.article import ArticleSnapshot
from schemas.enums import NewsProvider
from utils.datetime_helpers import parse_datetime

from connectors.newsapi_normalizer import infer_category


def normalize_to_snapshot(raw: dict[str, Any]) -> ArticleSnapshot:
    """Convert a normalized GDELT dict to an ArticleSnapshot."""
    pub_dt = parse_datetime(raw.get("published_at", ""))

    headline = raw.get("headline", "untitled")
    return ArticleSnapshot(
        ts=datetime.now(UTC),
        article_id=raw.get("article_id", ""),
        source_name=raw.get("source_name", "unknown"),
        source_url=raw.get("source_url", ""),
        headline=headline,
        body=raw.get("body"),
        category=infer_category(headline),
        provider=NewsProvider.GDELT,
        published_at=pub_dt,
        language="en",
        author=raw.get("author"),
    )


__all__ = ["normalize_to_snapshot"]
