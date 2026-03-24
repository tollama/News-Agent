"""Backward-compatible story cluster helpers.

Cluster-building heuristics now live in ``services.story_clusters`` so API,
pipeline, and feature paths can share the same logic.
"""

from services.story_clusters import (
    assign_story_clusters,
    build_cluster_summary,
    choose_representative_index,
)

__all__ = ["assign_story_clusters", "build_cluster_summary", "choose_representative_index"]
