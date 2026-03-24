"""Service-layer helpers for persisted story cluster artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from schemas.signals import NewsSignal
from services.story_clusters import build_signal_cluster_summaries
from storage.persisted_signals import PersistedSignalStore
from storage.readers import JsonlReader
from storage.story_clusters import StoryClusterStore


class PersistedStoryClusterService:
    """Read/query/build persisted story cluster artifacts.

    Keeps API and pipeline flows oriented around explicit persisted cluster
    artifacts instead of reimplementing signal-to-cluster fallbacks inline.
    """

    def __init__(
        self,
        *,
        reader: JsonlReader | None = None,
        store: StoryClusterStore | None = None,
    ) -> None:
        self._reader = reader or JsonlReader()
        self._store = store or StoryClusterStore(reader=self._reader)
        self._signal_store = PersistedSignalStore(reader=self._reader)

    def list_recent(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
        analyze_signal: Callable[[NewsSignal], Mapping[str, Any]] | None = None,
        persist_generated: bool = True,
        cluster_id_prefix: str = "recent-cluster",
    ) -> list[dict[str, Any]]:
        """List recent clusters from persisted artifacts or fallback signals."""
        persisted_clusters = self._store.list_recent(limit=limit, query=query)
        if persisted_clusters:
            return persisted_clusters

        signals = [
            NewsSignal(**signal_data)
            for signal_data in self._signal_store.list_recent(limit=max(limit * 8, 40), query=query)
        ]

        if analyze_signal is None:
            return []

        generated_clusters = build_signal_cluster_summaries(
            signals,
            analyze_signal,
            cluster_id_prefix=cluster_id_prefix,
        )[:limit]
        if generated_clusters and persist_generated:
            self._store.write_by_partition(generated_clusters)
        return generated_clusters

    def write_by_partition(self, clusters: list[Mapping[str, Any]]) -> list[Any]:
        """Persist cluster summaries grouped by their analyzed/published date."""
        return self._store.write_by_partition(clusters)


__all__ = ["PersistedStoryClusterService"]
