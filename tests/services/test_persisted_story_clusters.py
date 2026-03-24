"""Tests for persisted story cluster service helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from schemas.signals import NewsSignal
from services.persisted_story_clusters import PersistedStoryClusterService
from storage.readers import JsonlReader
from storage.story_clusters import StoryClusterStore
from storage.writers import JsonlWriter


def _make_signal(story_id: str, *, query: str, headline: str, entities: list[str], source_name: str = "Reuters") -> NewsSignal:
    now = datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
    return NewsSignal(
        story_id=story_id,
        headline=headline,
        source_name=source_name,
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.0,
        entities=entities,
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.5,
        article_count=2,
        query=query,
    )


def test_persisted_story_cluster_service_prefers_persisted_clusters(tmp_path):
    reader = JsonlReader(base_dir=str(tmp_path))
    store = StoryClusterStore(reader=reader)
    store.write(
        [
            {
                "cluster_id": "persisted-1",
                "headline": "Federal Reserve holds rates steady",
                "query": "fed rates",
                "story_ids": ["fed-1"],
                "story_count": 1,
                "total_article_count": 2,
                "source_names": ["Reuters"],
                "top_entities": ["Federal Reserve"],
                "latest_published_at": "2026-03-24T12:00:00+00:00",
                "latest_analyzed_at": "2026-03-24T12:00:00+00:00",
                "avg_trust_score": 0.8,
                "max_trust_score": 0.8,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            }
        ],
        date_str="2026-03-24",
    )

    service = PersistedStoryClusterService(reader=reader, store=store)
    clusters = service.list_recent(limit=5, query="fed", analyze_signal=lambda signal: {"trust_score": 0.5})

    assert [cluster["cluster_id"] for cluster in clusters] == ["persisted-1"]


def test_persisted_story_cluster_service_generates_and_persists_clusters_from_signals(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            _make_signal(
                "fed-1",
                query="fed rates",
                headline="Federal Reserve holds rates steady",
                entities=["Federal Reserve", "Rates"],
            ).model_dump(mode="json"),
            _make_signal(
                "fed-2",
                query="fed rates",
                headline="Powell says Federal Reserve can wait on cuts",
                entities=["Federal Reserve", "Jerome Powell", "Rates"],
                source_name="AP",
            ).model_dump(mode="json"),
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    reader = JsonlReader(base_dir=str(tmp_path))
    service = PersistedStoryClusterService(reader=reader)
    clusters = service.list_recent(
        limit=5,
        query="fed",
        analyze_signal=lambda signal: {
            "trust_score": 0.75,
            "risk_category": "low",
            "calibration_status": "well_calibrated",
        },
        cluster_id_prefix="recent-cluster",
    )

    assert len(clusters) == 1
    assert clusters[0]["cluster_id"] == "recent-cluster-1"
    assert set(clusters[0]["story_ids"]) == {"fed-1", "fed-2"}

    persisted = StoryClusterStore(reader=reader).list_recent(limit=5, query="fed")
    assert len(persisted) == 1
    assert persisted[0]["cluster_id"] == "recent-cluster-1"
