"""Tests for calibration.news_trust_score."""

from datetime import UTC, datetime

from calibration.news_trust_score import compute_news_trust
from schemas.signals import NewsSignal


def _make_signal(**overrides) -> NewsSignal:
    defaults = {
        "story_id": "test",
        "headline": "Test headline",
        "source_name": "Reuters",
        "published_at": datetime(2025, 1, 15, tzinfo=UTC),
        "analyzed_at": datetime(2025, 1, 15, tzinfo=UTC),
        "sentiment_score": 0.0,
        "source_credibility": 0.9,
        "corroboration": 0.8,
        "contradiction_score": 0.1,
        "propagation_delay_seconds": 60.0,
        "freshness_score": 0.9,
        "novelty": 0.7,
        "article_count": 5,
    }
    defaults.update(overrides)
    return NewsSignal(**defaults)


def test_high_trust_signal():
    signal = _make_signal(
        source_credibility=0.95,
        corroboration=0.9,
        freshness_score=0.95,
        novelty=0.8,
        contradiction_score=0.05,
    )
    result = compute_news_trust(signal)
    assert result["trust_score"] >= 0.75
    assert result["risk_category"] == "GREEN"


def test_low_trust_signal():
    signal = _make_signal(
        source_credibility=0.2,
        corroboration=0.1,
        freshness_score=0.1,
        novelty=0.3,
        contradiction_score=0.9,
    )
    result = compute_news_trust(signal)
    assert result["trust_score"] < 0.50
    assert result["risk_category"] == "RED"


def test_components_present():
    signal = _make_signal()
    result = compute_news_trust(signal)
    assert "source_credibility" in result["components"]
    assert "corroboration" in result["components"]
    assert "freshness" in result["components"]
    assert "novelty" in result["components"]
    assert "contradiction_penalty" in result["components"]


def test_trust_score_bounded():
    signal = _make_signal()
    result = compute_news_trust(signal)
    assert 0.0 <= result["trust_score"] <= 1.0
