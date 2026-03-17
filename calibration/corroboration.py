"""Cross-source corroboration scoring."""

from __future__ import annotations


def corroboration_score(
    source_count: int,
    unique_sources: int,
    min_sources_for_high: int = 3,
) -> float:
    """Compute corroboration score based on multi-source confirmation.

    Args:
        source_count: Total articles on the same topic.
        unique_sources: Number of distinct sources.
        min_sources_for_high: Threshold for high corroboration.

    Returns:
        Score in [0, 1] where 1.0 = well-corroborated.
    """
    if unique_sources <= 0:
        return 0.0
    if unique_sources >= min_sources_for_high:
        return min(1.0, 0.7 + 0.3 * (unique_sources / (min_sources_for_high * 2)))
    return unique_sources / min_sources_for_high * 0.7


def source_diversity_ratio(unique_sources: int, total_articles: int) -> float:
    """Ratio of unique sources to total articles (0-1)."""
    if total_articles <= 0:
        return 0.0
    return min(1.0, unique_sources / total_articles)


__all__ = ["corroboration_score", "source_diversity_ratio"]
