"""News feature engineering — builds feature columns from ArticleSnapshot data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd

from features.nlp.credibility import get_credibility_score
from features.nlp.dedup import compute_novelty, find_duplicates
from features.nlp.entities import extract_entities
from features.nlp.sentiment import compute_sentiment
from utils.datetime_helpers import parse_datetime

logger = logging.getLogger(__name__)


def build_news_features(articles: pd.DataFrame) -> pd.DataFrame:
    """Compute news features from a DataFrame of article dicts.

    Expected columns: headline, body, source_name, published_at.
    Returns DataFrame with additional feature columns.
    """
    df = articles.copy()
    now = datetime.now(UTC)

    # Sentiment
    df["sentiment_score"] = df.apply(
        lambda r: compute_sentiment(f"{r.get('headline', '')} {r.get('body', '') or ''}"),
        axis=1,
    )

    # Entities
    df["entities"] = df.apply(
        lambda r: extract_entities(f"{r.get('headline', '')} {r.get('body', '') or ''}"),
        axis=1,
    )

    # Source credibility
    df["source_credibility"] = df["source_name"].apply(get_credibility_score)

    # Near-duplicate detection and novelty
    article_dicts = df[["headline"]].to_dict("records")
    clusters = find_duplicates(article_dicts, threshold=0.5)
    df["novelty"] = [compute_novelty(i, clusters) for i in range(len(df))]

    # Freshness (exponential decay with 6h half-life)
    half_life_seconds = 6 * 3600
    df["freshness_score"] = df["published_at"].apply(
        lambda pub: _freshness_decay(pub, now, half_life_seconds)
    )

    # Propagation delay (seconds since first article in same cluster)
    df["propagation_delay_seconds"] = 0.0
    if "published_at" in df.columns:
        for cluster in clusters:
            indices = sorted(cluster)
            pub_times = df.iloc[indices]["published_at"]
            try:
                earliest = pd.to_datetime(pub_times).min()
                for idx in indices:
                    pub = pd.to_datetime(df.iloc[idx]["published_at"])
                    delay = (pub - earliest).total_seconds()
                    df.loc[df.index[idx], "propagation_delay_seconds"] = max(0.0, delay)
            except (TypeError, ValueError):
                pass

    # Corroboration (article count in same entity cluster / total)
    entity_overlap = _compute_entity_overlap(df)
    df["corroboration"] = entity_overlap

    # Contradiction: sentiment divergence within duplicate clusters
    df["contradiction_score"] = _compute_contradiction(df, clusters)

    # Article count for the query window
    df["article_count"] = len(df)

    return df


def _freshness_decay(
    published_at: str | datetime,
    now: datetime,
    half_life_seconds: float,
) -> float:
    """Compute freshness score using exponential decay."""
    import math

    pub = parse_datetime(published_at)

    age_seconds = max(0.0, (now - pub).total_seconds())
    return math.exp(-0.693 * age_seconds / half_life_seconds)


def _compute_contradiction(
    df: pd.DataFrame,
    clusters: list[set[int]],
) -> pd.Series:
    """Compute contradiction score from sentiment divergence within clusters.

    Articles in the same duplicate cluster that have divergent sentiment
    produce a high contradiction score.  Singletons get a low baseline.
    """
    # Build index → cluster mapping
    idx_to_cluster: dict[int, int] = {}
    for cluster_id, cluster in enumerate(clusters):
        if len(cluster) >= 2:
            for idx in cluster:
                idx_to_cluster[idx] = cluster_id

    scores = []
    for i in range(len(df)):
        cluster_id = idx_to_cluster.get(i)
        if cluster_id is None:
            scores.append(0.1)
            continue

        cluster_indices = sorted(clusters[cluster_id])
        sentiments = df.iloc[cluster_indices]["sentiment_score"].values
        stddev = float(sentiments.std(ddof=0))
        # Scale: stddev of 0.5 on [-1,1] scale → max contradiction
        scores.append(min(1.0, stddev / 0.5))

    return pd.Series(scores, index=df.index)


def _compute_entity_overlap(df: pd.DataFrame) -> pd.Series:
    """Compute corroboration score based on entity overlap across articles."""
    if len(df) <= 1:
        return pd.Series([0.5] * len(df), index=df.index)

    all_entities = df["entities"].tolist()
    scores = []
    for i, ents in enumerate(all_entities):
        if not ents:
            scores.append(0.3)
            continue
        ent_set = set(ents)
        overlap_count = 0
        for j, other_ents in enumerate(all_entities):
            if i != j and ent_set & set(other_ents):
                overlap_count += 1
        # Normalize: what fraction of other articles share entities
        score = min(1.0, overlap_count / max(1, len(df) - 1))
        scores.append(score)

    return pd.Series(scores, index=df.index)


__all__ = ["build_news_features"]
