"""Tests for connectors.normalizer_registry."""

from __future__ import annotations

from connectors.normalizer_registry import normalize_article
from schemas.enums import NewsProvider


def test_dispatch_newsapi(sample_newsapi_article):
    snapshot = normalize_article(sample_newsapi_article)
    assert snapshot.provider == NewsProvider.NEWSAPI
    assert snapshot.source_name == "Reuters"


def test_dispatch_gdelt():
    raw = {
        "article_id": "https://example.com/gdelt/1",
        "source_name": "example.com",
        "source_url": "https://example.com/gdelt/1",
        "headline": "GDELT test article",
        "body": "Body text",
        "published_at": "20250115140000",
        "provider": "gdelt",
    }
    snapshot = normalize_article(raw)
    assert snapshot.provider == NewsProvider.GDELT


def test_dispatch_rss():
    raw = {
        "article_id": "https://example.com/rss/1",
        "source_name": "RSS Feed",
        "source_url": "https://example.com/rss/1",
        "headline": "RSS test article",
        "body": "Body text",
        "published_at": "Mon, 15 Jan 2025 14:00:00 GMT",
        "provider": "rss",
    }
    snapshot = normalize_article(raw)
    assert snapshot.provider == NewsProvider.RSS


def test_dispatch_unknown_falls_back_to_newsapi():
    raw = {
        "article_id": "https://example.com/1",
        "source_name": "Unknown",
        "headline": "Test",
        "published_at": "2025-01-15T14:00:00Z",
        "provider": "unknown_provider",
    }
    snapshot = normalize_article(raw)
    assert snapshot.provider == NewsProvider.NEWSAPI  # fallback
