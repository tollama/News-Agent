"""Tests for pipelines.ingest_job."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from agents.news_agent import NewsAgent
from pipelines.ingest_job import NewsIngestPipeline
from schemas.signals import NewsSignal
from storage.readers import JsonlReader
from storage.story_clusters import StoryClusterStore
from storage.writers import JsonlWriter


def _make_signal(query: str = "test") -> NewsSignal:
    now = datetime.now(UTC)
    return NewsSignal(
        story_id=f"story:{query}",
        headline=f"Test headline for {query}",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=-0.1,
        entities=["Federal Reserve"],
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.95,
        novelty=0.6,
        article_count=3,
        query=query,
    )


@pytest.mark.asyncio()
async def test_full_pipeline_run():
    agent = NewsAgent(connectors=[])
    signal = _make_signal()

    with patch.object(agent, "process_query", return_value=signal):
        pipeline = NewsIngestPipeline(agent, queries=["test"])
        results = await pipeline.run()

    assert "signals" in results
    assert "trust_results" in results
    assert "trust_payloads" in results
    assert "story_summaries" in results
    assert "story_clusters" in results
    assert len(results["trust_payloads"]) == 1
    assert len(results["story_summaries"]) == 1
    assert len(results["story_clusters"]) == 1
    assert results["trust_payloads"][0]["story_id"] == "story:test"
    assert results["story_summaries"][0]["story_id"] == "story:test"


@pytest.mark.asyncio()
async def test_pipeline_with_writer(tmp_path):
    agent = NewsAgent(connectors=[])
    signal = _make_signal()
    writer = JsonlWriter(base_dir=str(tmp_path))

    with patch.object(agent, "process_query", return_value=signal):
        pipeline = NewsIngestPipeline(agent, queries=["test"], writer=writer)
        await pipeline.run()

    # Check that files were written
    signals_dir = tmp_path / "signals"
    payloads_dir = tmp_path / "trust_payloads"
    summaries_dir = tmp_path / "story_summaries"
    clusters_dir = tmp_path / "story_clusters"
    assert signals_dir.exists()
    assert payloads_dir.exists()
    assert summaries_dir.exists()
    assert clusters_dir.exists()

    recent_summaries = JsonlReader(base_dir=str(tmp_path)).list_recent("story_summaries", limit=1)
    assert recent_summaries[0]["story_id"] == "story:test"


@pytest.mark.asyncio()
async def test_pipeline_publish_persists_clusters_by_signal_partition(tmp_path):
    agent = NewsAgent(connectors=[])
    signal = _make_signal("partitioned")
    signal = signal.model_copy(
        update={
            "published_at": datetime(2026, 3, 23, 23, 30, tzinfo=UTC),
            "analyzed_at": datetime(2026, 3, 24, 0, 5, tzinfo=UTC),
        }
    )
    writer = JsonlWriter(base_dir=str(tmp_path))

    with patch.object(agent, "process_query", return_value=signal):
        pipeline = NewsIngestPipeline(agent, queries=["test"], writer=writer)
        await pipeline.run()

    persisted_clusters = StoryClusterStore(reader=JsonlReader(base_dir=str(tmp_path))).read("2026-03-24")
    assert len(persisted_clusters) == 1
    assert persisted_clusters[0]["story_ids"] == ["story:partitioned"]


@pytest.mark.asyncio()
async def test_pipeline_resume():
    agent = NewsAgent(connectors=[])
    signal = _make_signal()

    with patch.object(agent, "process_query", return_value=signal):
        pipeline = NewsIngestPipeline(agent, queries=["test"])
        # Run full first
        await pipeline.run()
        # Resume from trust stage
        results = await pipeline.run(resume_from="trust")

    assert "trust_results" in results
