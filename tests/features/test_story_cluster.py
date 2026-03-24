"""Tests for event/story clustering helpers."""

from __future__ import annotations

import pandas as pd

from features.story_cluster import assign_story_clusters, build_cluster_summary, choose_representative_index


def test_assign_story_clusters_merges_related_non_duplicate_articles():
    df = pd.DataFrame(
        [
            {
                "headline": "Federal Reserve raises rates again",
                "entities": ["Federal Reserve", "Inflation"],
                "source_credibility": 0.95,
                "source_name": "Reuters",
            },
            {
                "headline": "Markets react as Fed lifts rates to fight inflation",
                "entities": ["Federal Reserve", "Inflation", "Markets"],
                "source_credibility": 0.8,
                "source_name": "Bloomberg",
            },
            {
                "headline": "Startup releases new AI coding model",
                "entities": ["Startup", "AI"],
                "source_credibility": 0.4,
                "source_name": "TechBlog",
            },
        ]
    )

    clusters = assign_story_clusters(df, duplicate_clusters=[])
    assert clusters.iloc[0] == clusters.iloc[1]
    assert clusters.iloc[2] != clusters.iloc[0]


def test_cluster_summary_and_representative_bias_toward_consensus():
    df = pd.DataFrame(
        [
            {
                "headline": "Federal Reserve raises rates again",
                "entities": ["Federal Reserve", "Inflation"],
                "source_credibility": 0.95,
                "source_name": "Reuters",
            },
            {
                "headline": "Fed raises rates as inflation stays elevated",
                "entities": ["Federal Reserve", "Inflation", "Economy"],
                "source_credibility": 0.8,
                "source_name": "AP",
            },
            {
                "headline": "Federal Reserve surprises markets with rate rise",
                "entities": ["Federal Reserve", "Markets"],
                "source_credibility": 0.7,
                "source_name": "CNBC",
            },
        ]
    )

    summary = build_cluster_summary(df, [0, 1, 2])
    representative_idx = choose_representative_index(df, [0, 1, 2])

    assert summary["article_count"] == 3
    assert summary["source_count"] == 3
    assert representative_idx in {0, 1}
