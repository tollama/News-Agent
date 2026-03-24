"""Tests for service-layer story cluster helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from schemas.signals import NewsSignal
from services.story_clusters import build_signal_cluster_summaries, cluster_signals, stories_are_related


def _make_signal(
    story_id: str,
    *,
    headline: str,
    query: str,
    entities: list[str],
    source_name: str = "Reuters",
    article_count: int = 1,
    published_offset_minutes: int = 0,
) -> NewsSignal:
    now = datetime.now(UTC)
    published_at = now - timedelta(minutes=published_offset_minutes)
    return NewsSignal(
        story_id=story_id,
        headline=headline,
        source_name=source_name,
        published_at=published_at,
        analyzed_at=now,
        sentiment_score=0.0,
        entities=entities,
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.5,
        article_count=article_count,
        query=query,
    )


def test_stories_are_related_uses_shared_query_or_entity_overlap():
    left = _make_signal(
        "fed-1",
        headline="Federal Reserve holds rates steady",
        query="fed rates",
        entities=["Federal Reserve", "Rates"],
    )
    right = _make_signal(
        "fed-2",
        headline="Powell says Federal Reserve can wait on cuts",
        query="fed rates",
        entities=["Federal Reserve", "Jerome Powell", "Rates"],
        source_name="AP",
    )

    assert stories_are_related(left, right) is True


def test_build_signal_cluster_summaries_groups_related_signals():
    signals = [
        _make_signal(
            "fed-1",
            headline="Federal Reserve holds rates steady",
            query="fed rates",
            entities=["Federal Reserve", "Rates"],
            article_count=4,
        ),
        _make_signal(
            "fed-2",
            headline="Powell says Federal Reserve can wait on cuts",
            query="fed rates",
            entities=["Federal Reserve", "Jerome Powell", "Rates"],
            source_name="AP",
            article_count=3,
            published_offset_minutes=5,
        ),
        _make_signal(
            "ai-1",
            headline="Nvidia unveils AI chip roadmap",
            query="ai chips",
            entities=["Nvidia", "AI"],
            article_count=2,
        ),
    ]

    summaries = build_signal_cluster_summaries(
        signals,
        lambda signal: {
            "trust_score": 0.75 if signal.story_id.startswith("fed") else 0.55,
            "risk_category": "low",
            "calibration_status": "well_calibrated",
        },
        cluster_id_prefix="test-cluster",
    )

    assert len(cluster_signals(signals)) == 2
    assert summaries[0]["cluster_id"] == "test-cluster-1"
    assert set(summaries[0]["story_ids"]) == {"fed-1", "fed-2"}
    assert summaries[0]["story_count"] == 2
    assert summaries[0]["total_article_count"] == 7
    assert "Federal Reserve" in summaries[0]["top_entities"]
