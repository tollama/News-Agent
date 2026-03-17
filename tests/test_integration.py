"""Integration test: config → agent → pipeline → trust result."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from agents.news_agent import NewsAgent
from configs.loader import bootstrap_agent, load_config
from pipelines.ingest_job import NewsIngestPipeline
from schemas.signals import NewsSignal


def test_load_config():
    config = load_config("configs/default.yaml")
    assert "providers" in config
    assert "newsapi" in config["providers"]


def test_bootstrap_agent_creates_connectors():
    config = load_config("configs/default.yaml")
    # newsapi is enabled by default
    with patch.dict("os.environ", {"NEWSAPI_API_KEY": "test-key"}):
        agent = bootstrap_agent(config)
    assert len(agent._connectors) >= 1


@pytest.mark.asyncio()
async def test_end_to_end_pipeline():
    """Full pipeline: agent → process_query → analyze → trust payloads."""
    now = datetime.now(UTC)
    signal = NewsSignal(
        story_id="integration-test",
        headline="Integration test headline",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=-0.2,
        entities=["Federal Reserve"],
        source_credibility=0.9,
        corroboration=0.8,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.95,
        novelty=0.6,
        article_count=3,
        query="fed rates",
    )

    agent = NewsAgent(connectors=[])
    with patch.object(agent, "process_query", new_callable=AsyncMock, return_value=signal):
        pipeline = NewsIngestPipeline(agent, queries=["fed rates"])
        results = await pipeline.run()

    # Verify full output structure
    assert "signals" in results
    assert "trust_results" in results
    assert "trust_payloads" in results

    trust = results["trust_results"][0]
    assert "trust_score" in trust
    assert "component_breakdown" in trust
    assert "why_trusted" in trust
    assert "strongest factor" in trust["why_trusted"]

    payload = results["trust_payloads"][0]
    assert payload["story_id"] == "integration-test"
    assert "source_credibility" in payload
