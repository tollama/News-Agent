"""Tests for schemas.signals."""

from datetime import UTC, datetime

from schemas.signals import NewsSignal


def test_news_signal_creation():
    now = datetime.now(UTC)
    signal = NewsSignal(
        story_id="story-1",
        headline="Test headline",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.5,
        source_credibility=0.95,
        corroboration=0.8,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.7,
        article_count=3,
    )
    assert signal.story_id == "story-1"
    assert signal.source_credibility == 0.95
    assert signal.entities == []


def test_news_signal_from_dict(sample_news_signal_data):
    signal = NewsSignal(**sample_news_signal_data)
    assert signal.story_id == "https://example.com/article/123"
    assert signal.article_count == 5
    assert len(signal.entities) == 2
