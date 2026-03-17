"""Normalizer for NewsAPI.org raw article data to ArticleSnapshot."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schemas.article import ArticleSnapshot
from schemas.enums import NewsCategory, NewsProvider


_CATEGORY_KEYWORDS: dict[NewsCategory, set[str]] = {
    NewsCategory.BUSINESS: {"market", "stock", "economy", "trade", "finance", "bank", "earnings"},
    NewsCategory.TECHNOLOGY: {"tech", "software", "ai", "startup", "cyber", "cloud"},
    NewsCategory.POLITICS: {"election", "congress", "senate", "president", "policy", "vote"},
    NewsCategory.SCIENCE: {"research", "study", "nasa", "climate", "physics"},
    NewsCategory.HEALTH: {"health", "medical", "vaccine", "disease", "fda", "drug"},
    NewsCategory.SPORTS: {"game", "team", "player", "league", "championship", "score"},
    NewsCategory.ENTERTAINMENT: {"movie", "music", "celebrity", "award", "film"},
}


def infer_category(headline: str) -> NewsCategory:
    """Infer article category from headline keywords."""
    lower = headline.lower()
    best_cat = NewsCategory.GENERAL
    best_count = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > best_count:
            best_count = count
            best_cat = cat
    return best_cat


def normalize_to_snapshot(raw: dict[str, Any]) -> ArticleSnapshot:
    """Convert a normalized NewsAPI dict to an ArticleSnapshot."""
    published_at = raw.get("published_at", "")
    if isinstance(published_at, str) and published_at:
        try:
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            pub_dt = datetime.now(UTC)
    else:
        pub_dt = datetime.now(UTC)

    headline = raw.get("headline", "untitled")
    return ArticleSnapshot(
        ts=datetime.now(UTC),
        article_id=raw.get("article_id", ""),
        source_name=raw.get("source_name", "unknown"),
        source_url=raw.get("source_url", ""),
        headline=headline,
        body=raw.get("body"),
        category=infer_category(headline),
        provider=NewsProvider.NEWSAPI,
        published_at=pub_dt,
        language="en",
        author=raw.get("author"),
    )


__all__ = ["infer_category", "normalize_to_snapshot"]
