"""Pragmatic story clustering helpers.

Goal: bias aggregation toward multi-article event clusters rather than a single
best article. Clustering combines near-duplicate headline similarity with
entity/token overlap so stories can gather multiple angles from different
publishers.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

import pandas as pd

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "to", "was", "were", "will", "with",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]+")


def assign_story_clusters(df: pd.DataFrame, duplicate_clusters: list[set[int]]) -> pd.Series:
    """Assign a cluster id to each article using duplicate + overlap heuristics."""
    if df.empty:
        return pd.Series(dtype="string")

    article_clusters = _expand_clusters(df, duplicate_clusters)
    labels = [""] * len(df)
    for cluster_num, cluster in enumerate(article_clusters):
        label = f"story-{cluster_num + 1}"
        for idx in cluster:
            labels[idx] = label

    for idx, label in enumerate(labels):
        if not label:
            labels[idx] = f"story-{idx + 1}"

    return pd.Series(labels, index=df.index, dtype="string")


def build_cluster_summary(df: pd.DataFrame, cluster_indices: Iterable[int]) -> dict[str, object]:
    """Summarize a cluster for aggregate story selection."""
    indices = sorted(set(int(i) for i in cluster_indices))
    cluster_df = df.iloc[indices]

    entity_counts = Counter()
    for values in cluster_df.get("entities", []):
        if isinstance(values, list):
            entity_counts.update(str(v) for v in values if v)

    token_counts = Counter()
    for headline in cluster_df["headline"].fillna(""):
        token_counts.update(_headline_tokens(str(headline)))

    avg_credibility = float(cluster_df["source_credibility"].mean()) if len(cluster_df) else 0.0
    article_count = len(cluster_df)
    source_count = int(cluster_df["source_name"].nunique()) if len(cluster_df) else 0
    aggregate_score = (article_count * 0.45) + (source_count * 0.35) + (avg_credibility * 2.0)

    return {
        "indices": indices,
        "article_count": article_count,
        "source_count": source_count,
        "entity_counts": entity_counts,
        "token_counts": token_counts,
        "aggregate_score": aggregate_score,
    }


def choose_representative_index(df: pd.DataFrame, cluster_indices: Iterable[int]) -> int:
    """Select the article that best represents the cluster centroid."""
    indices = sorted(set(int(i) for i in cluster_indices))
    if len(indices) == 1:
        return indices[0]

    entity_counts = Counter()
    token_counts = Counter()
    for idx in indices:
        entities = df.iloc[idx].get("entities", [])
        if isinstance(entities, list):
            entity_counts.update(str(v) for v in entities if v)
        token_counts.update(_headline_tokens(str(df.iloc[idx].get("headline", ""))))

    best_idx = indices[0]
    best_score = float("-inf")
    for idx in indices:
        row = df.iloc[idx]
        row_entities = row.get("entities", []) if isinstance(row.get("entities", []), list) else []
        row_tokens = _headline_tokens(str(row.get("headline", "")))
        centrality = sum(entity_counts.get(ent, 0) for ent in row_entities)
        centrality += sum(token_counts.get(tok, 0) for tok in row_tokens)
        score = centrality + float(row.get("source_credibility", 0.0)) * 2.0
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def _expand_clusters(df: pd.DataFrame, duplicate_clusters: list[set[int]]) -> list[set[int]]:
    n = len(df)
    adjacency = {i: {i} for i in range(n)}

    for cluster in duplicate_clusters:
        for i in cluster:
            adjacency.setdefault(i, {i}).update(cluster)

    entity_sets = [_normalized_entities(v) for v in df["entities"]]
    token_sets = [_headline_tokens(str(v)) for v in df["headline"].fillna("")]

    for i in range(n):
        for j in range(i + 1, n):
            entity_overlap = len(entity_sets[i] & entity_sets[j])
            token_overlap = len(token_sets[i] & token_sets[j])
            if entity_overlap >= 2 or (entity_overlap >= 1 and token_overlap >= 2):
                adjacency[i].add(j)
                adjacency[j].add(i)

    seen: set[int] = set()
    clusters: list[set[int]] = []
    for start in range(n):
        if start in seen:
            continue
        stack = [start]
        cluster: set[int] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            cluster.add(node)
            stack.extend(adjacency.get(node, set()) - seen)
        clusters.append(cluster)
    return clusters


def _normalized_entities(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip().lower() for item in value if str(item).strip()}


def _headline_tokens(text: str) -> set[str]:
    return {
        token.lower() for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOPWORDS and len(token) > 2
    }


__all__ = ["assign_story_clusters", "build_cluster_summary", "choose_representative_index"]
