"""Tests for explicit persisted story cluster storage helpers."""

from __future__ import annotations

from storage.readers import JsonlReader
from storage.story_clusters import StoryClusterStore, cluster_matches_query


def test_story_cluster_store_write_read_and_query(tmp_path):
    store = StoryClusterStore(
        reader=JsonlReader(base_dir=str(tmp_path)),
    )
    clusters = [
        {
            "cluster_id": "persisted-1",
            "headline": "Federal Reserve holds rates steady",
            "query": "fed rates",
            "story_ids": ["fed-1", "fed-2"],
            "story_count": 2,
            "total_article_count": 7,
            "source_names": ["Reuters", "Associated Press"],
            "top_entities": ["Federal Reserve", "Jerome Powell"],
            "latest_published_at": "2026-03-24T12:00:00+00:00",
            "latest_analyzed_at": "2026-03-24T12:05:00+00:00",
            "avg_trust_score": 0.81,
            "max_trust_score": 0.88,
            "risk_category": "low",
            "calibration_status": "well_calibrated",
        },
        {
            "cluster_id": "persisted-2",
            "headline": "Nvidia unveils next AI chip roadmap",
            "query": "ai chips",
            "story_ids": ["ai-1"],
            "story_count": 1,
            "total_article_count": 2,
            "source_names": ["Reuters"],
            "top_entities": ["Nvidia", "AI"],
            "latest_published_at": "2026-03-24T10:00:00+00:00",
            "latest_analyzed_at": "2026-03-24T10:05:00+00:00",
            "avg_trust_score": 0.75,
            "max_trust_score": 0.75,
            "risk_category": "low",
            "calibration_status": "well_calibrated",
        },
    ]

    store.write(clusters, date_str="2026-03-24")

    assert len(store.read("2026-03-24")) == 2
    assert [cluster["cluster_id"] for cluster in store.list_recent(limit=5)] == ["persisted-2", "persisted-1"]
    assert [cluster["cluster_id"] for cluster in store.list_recent(limit=5, query="powell")] == ["persisted-1"]
    assert [cluster["cluster_id"] for cluster in store.list_recent(limit=5, query="associated press")] == ["persisted-1"]


def test_cluster_matches_query_checks_cluster_specific_fields():
    cluster = {
        "cluster_id": "persisted-fed-1",
        "headline": "Federal Reserve holds rates steady",
        "query": "fed rates",
        "story_ids": ["fed-1"],
        "top_entities": ["Federal Reserve"],
        "source_names": ["Reuters"],
    }

    assert cluster_matches_query(cluster, "persisted-fed") is True
    assert cluster_matches_query(cluster, "reuters") is True
    assert cluster_matches_query(cluster, "missing") is False
