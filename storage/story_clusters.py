"""Explicit storage helpers for persisted story cluster artifacts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from storage.readers import JsonlReader
from storage.writers import JsonlWriter


class StoryClusterStore:
    """Pragmatic read/write/query helpers for persisted ``story_clusters`` artifacts."""

    def __init__(
        self,
        *,
        reader: JsonlReader | None = None,
        writer: JsonlWriter | None = None,
    ) -> None:
        self._reader = reader or JsonlReader()
        self._writer = writer or JsonlWriter(base_dir=str(self._reader.base_dir))

    def write(self, clusters: list[dict[str, Any]], *, date_str: str | None = None) -> Any:
        """Persist story cluster summaries as a date-partitioned dataset."""
        return self._writer.write(clusters, dataset="story_clusters", date_str=date_str)

    def write_by_partition(self, clusters: list[Mapping[str, Any]]) -> list[Any]:
        """Persist cluster summaries grouped by their analyzed/published date."""
        writes: list[Any] = []
        for partition_date, partition_clusters in _group_clusters_by_partition_date(clusters).items():
            writes.append(self.write(partition_clusters, date_str=partition_date))
        return writes

    def read(self, date_str: str) -> list[dict[str, Any]]:
        """Read all persisted story cluster summaries for a partition date."""
        return self._reader.read("story_clusters", date_str)

    def list_recent(self, *, limit: int = 20, query: str | None = None) -> list[dict[str, Any]]:
        """List recent persisted cluster summaries with optional free-text matching."""
        clusters = self._reader.list_recent("story_clusters", limit=max(limit * 4, 20))
        if query:
            clusters = [cluster for cluster in clusters if cluster_matches_query(cluster, query)]
        return clusters[:limit]


def cluster_matches_query(cluster: Mapping[str, Any], query: str | None) -> bool:
    """Return whether a persisted story cluster matches a search needle."""
    if not query:
        return True
    needle = query.lower()
    haystacks = [
        cluster.get("cluster_id", ""),
        cluster.get("query", ""),
        cluster.get("headline", ""),
        *(cluster.get("story_ids", []) or []),
        *(cluster.get("top_entities", []) or []),
        *(cluster.get("source_names", []) or []),
    ]
    return any(needle in str(value).lower() for value in haystacks)


def _group_clusters_by_partition_date(clusters: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    partitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cluster in clusters:
        partition_date = _partition_date_for_cluster(cluster)
        partitions[partition_date].append(dict(cluster))
    return dict(partitions)


def _partition_date_for_cluster(cluster: Mapping[str, Any]) -> str:
    for field in ("latest_analyzed_at", "latest_published_at"):
        raw_value = cluster.get(field)
        parsed = _parse_datetime(raw_value)
        if parsed is not None:
            return parsed.date().isoformat()
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


__all__ = ["StoryClusterStore", "cluster_matches_query"]
