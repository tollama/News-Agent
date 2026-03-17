"""Tests for schemas.article."""

from datetime import UTC, datetime

from schemas.article import ArticleSnapshot
from schemas.enums import NewsCategory, NewsProvider


def test_article_snapshot_creation():
    now = datetime.now(UTC)
    snap = ArticleSnapshot(
        ts=now,
        article_id="test-123",
        source_name="Reuters",
        headline="Test headline",
        provider=NewsProvider.NEWSAPI,
        published_at=now,
    )
    assert snap.article_id == "test-123"
    assert snap.source_name == "Reuters"
    assert snap.category == NewsCategory.GENERAL
    assert snap.language == "en"
    assert snap.body is None


def test_article_snapshot_with_all_fields():
    now = datetime.now(UTC)
    snap = ArticleSnapshot(
        ts=now,
        article_id="test-456",
        source_name="Bloomberg",
        source_url="https://bloomberg.com/123",
        headline="Market rally continues",
        body="Stocks rose for the third straight day.",
        category=NewsCategory.BUSINESS,
        provider=NewsProvider.NEWSAPI,
        published_at=now,
        language="en",
        author="John Doe",
    )
    assert snap.category == NewsCategory.BUSINESS
    assert snap.author == "John Doe"
    assert snap.body is not None
