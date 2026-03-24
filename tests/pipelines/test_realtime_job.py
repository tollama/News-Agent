"""Tests for the realtime news polling pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agents.news_agent import NewsAgent
from pipelines.realtime_job import RealtimeNewsPipeline
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
