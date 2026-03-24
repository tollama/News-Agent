"""Tests for the realtime news polling pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.news_agent import NewsAgent
from pipelines.realtime_job import RealtimeNewsPipeline
from storage.readers import JsonlReader
from storage.writers import JsonlWriter
from tests.api.test_routes import _make_signal


@pytest.mark.asyncio
async def test_realtime_pipeline_emits_new_signal_once_for_duplicate_story_ids():
    agent = NewsAgent(connectors=[])
    agent.process_query = AsyncMock(
        side_effect=[
            _make_signal("story-1"),
            _make_signal("story-1"),
        ],
    )
    emitted: list[dict] = []
    pipeline = RealtimeNewsPipeline(
        agent=agent,
        queries=["fed"],
        poll_interval_seconds=0,
        on_signal=emitted.append,
    )

    await pipeline.run(max_iterations=2)

    assert len(emitted) == 1
    assert emitted[0]["story_id"] == "story-1"


@pytest.mark.asyncio
async def test_realtime_pipeline_emits_distinct_story_ids():
    agent = NewsAgent(connectors=[])
    agent.process_query = AsyncMock(
        side_effect=[
            _make_signal("story-1"),
            _make_signal("story-2"),
        ],
    )
    emitted: list[dict] = []
    pipeline = RealtimeNewsPipeline(
        agent=agent,
        queries=["fed"],
        poll_interval_seconds=0,
        on_signal=emitted.append,
    )

    await pipeline.run(max_iterations=2)

    assert [item["story_id"] for item in emitted] == ["story-1", "story-2"]


@pytest.mark.asyncio
async def test_realtime_pipeline_persists_signal_and_story_summary(tmp_path):
    agent = NewsAgent(connectors=[])
    agent.process_query = AsyncMock(return_value=_make_signal("story-1", query="fed"))
    emitted: list[dict] = []
    writer = JsonlWriter(base_dir=str(tmp_path))
    pipeline = RealtimeNewsPipeline(
        agent=agent,
        queries=["fed"],
        poll_interval_seconds=0,
        on_signal=emitted.append,
        writer=writer,
    )

    await pipeline.run(max_iterations=1)

    reader = JsonlReader(base_dir=str(tmp_path))
    persisted_signal = reader.find_first("signals", "story_id", "story-1")
    persisted_summary = reader.find_first("story_summaries", "story_id", "story-1")
    persisted_trust = reader.find_first("trust_payloads", "story_id", "story-1")

    assert len(emitted) == 1
    assert persisted_signal is not None
    assert persisted_summary is not None
    assert persisted_trust is not None
    assert persisted_summary["story_id"] == "story-1"
    assert persisted_summary["trust_score"] is not None
    assert persisted_trust["story_id"] == "story-1"
