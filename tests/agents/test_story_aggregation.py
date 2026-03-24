"""Tests for cluster-aware signal aggregation."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from agents.news_agent import NewsAgent


def test_aggregate_to_signal_prefers_strongest_cluster_over_single_best_article():
    now = datetime.now(UTC)
    df = pd.DataFrame(
        [
            {
                "article_id": "singleton-high-cred",
                "headline": "Obscure blog posts sensational claim",
                "source_name": "Reuters",
                "published_at": now,
                "sentiment_score": 0.2,
                "entities": ["Claim"],
                "source_credibility": 0.95,
                "corroboration": 0.2,
                "contradiction_score": 0.4,
                "propagation_delay_seconds": 0.0,
                "freshness_score": 0.8,
                "novelty": 1.0,
                "story_cluster": "story-1",
            },
            {
                "article_id": "fed-1",
                "headline": "Federal Reserve raises rates",
                "source_name": "AP",
                "published_at": now,
                "sentiment_score": 0.1,
                "entities": ["Federal Reserve", "Inflation"],
                "source_credibility": 0.8,
                "corroboration": 0.8,
                "contradiction_score": 0.1,
                "propagation_delay_seconds": 0.0,
                "freshness_score": 0.9,
                "novelty": 0.5,
                "story_cluster": "story-2",
            },
            {
                "article_id": "fed-2",
                "headline": "Markets react as Fed raises rates",
                "source_name": "Bloomberg",
                "published_at": now,
                "sentiment_score": 0.0,
                "entities": ["Federal Reserve", "Inflation", "Markets"],
                "source_credibility": 0.95,
                "corroboration": 0.85,
                "contradiction_score": 0.1,
                "propagation_delay_seconds": 60.0,
                "freshness_score": 0.95,
                "novelty": 0.5,
                "story_cluster": "story-2",
            },
        ]
    )

    agent = NewsAgent()
    signal = agent._aggregate_to_signal(df, query="fed")

    assert signal.story_id in {"fed-1", "fed-2"}
    assert signal.article_count == 2
    assert "Federal Reserve" in signal.entities
    assert signal.source_name in {"AP", "Bloomberg"}
