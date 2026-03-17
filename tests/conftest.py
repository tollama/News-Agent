"""Shared test fixtures for News Agent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest


@pytest.fixture()
def sample_newsapi_article() -> dict[str, Any]:
    """A normalized NewsAPI article dict."""
    return {
        "article_id": "https://example.com/article/123",
        "source_name": "Reuters",
        "source_url": "https://example.com/article/123",
        "headline": "Federal Reserve raises interest rates amid inflation concerns",
        "body": "The Federal Reserve announced a rate hike of 25 basis points.",
        "author": "Jane Reporter",
        "published_at": "2025-01-15T14:30:00Z",
        "provider": "newsapi",
    }


@pytest.fixture()
def sample_articles() -> list[dict[str, Any]]:
    """A list of normalized articles for feature testing."""
    return [
        {
            "article_id": "a1",
            "source_name": "Reuters",
            "source_url": "https://reuters.com/a1",
            "headline": "Federal Reserve raises interest rates",
            "body": "The Fed raised rates by 25 basis points.",
            "published_at": datetime(2025, 1, 15, 14, 0, tzinfo=UTC).isoformat(),
            "provider": "newsapi",
        },
        {
            "article_id": "a2",
            "source_name": "Bloomberg",
            "source_url": "https://bloomberg.com/a2",
            "headline": "Fed hikes interest rates to combat inflation",
            "body": "Bloomberg reports the Federal Reserve increased rates.",
            "published_at": datetime(2025, 1, 15, 14, 5, tzinfo=UTC).isoformat(),
            "provider": "newsapi",
        },
        {
            "article_id": "a3",
            "source_name": "TechBlog",
            "source_url": "https://techblog.com/a3",
            "headline": "New AI model released by startup",
            "body": "A tech startup released a new AI model today.",
            "published_at": datetime(2025, 1, 15, 15, 0, tzinfo=UTC).isoformat(),
            "provider": "newsapi",
        },
    ]


@pytest.fixture()
def sample_news_signal_data() -> dict[str, Any]:
    """A NewsSignal-compatible dict."""
    return {
        "story_id": "https://example.com/article/123",
        "headline": "Federal Reserve raises interest rates",
        "source_name": "Reuters",
        "published_at": datetime(2025, 1, 15, 14, 0, tzinfo=UTC),
        "analyzed_at": datetime(2025, 1, 15, 14, 10, tzinfo=UTC),
        "sentiment_score": -0.3,
        "entities": ["Federal Reserve", "$SPY"],
        "source_credibility": 0.95,
        "corroboration": 0.8,
        "contradiction_score": 0.1,
        "propagation_delay_seconds": 120.0,
        "freshness_score": 0.9,
        "novelty": 0.7,
        "article_count": 5,
        "query": "federal reserve rates",
    }
