"""Explicit storage helpers for persisted ``signals`` artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from schemas.signals import NewsSignal
from storage.readers import JsonlReader
from storage.writers import JsonlWriter


class PersistedSignalStore:
    """Pragmatic read/write/query helpers for persisted signal artifacts."""

    _DATASET = "signals"

    def __init__(
        self,
        *,
        reader: JsonlReader | None = None,
        writer: JsonlWriter | None = None,
    ) -> None:
        self._reader = reader or JsonlReader()
        self._writer = writer or JsonlWriter(base_dir=str(self._reader.base_dir))

    def write(self, signals: list[NewsSignal | Mapping[str, Any]], *, date_str: str | None = None) -> Any:
        """Persist signal artifacts as a date-partitioned dataset."""
        return self._writer.write(
            [self._normalize_signal(signal) for signal in signals],
            dataset=self._DATASET,
            date_str=date_str,
        )

    def write_by_partition(self, signals: list[NewsSignal | Mapping[str, Any]]) -> list[Any]:
        """Persist signals grouped by their analyzed/published date."""
        normalized = [self._normalize_signal(signal) for signal in signals]
        partitions: dict[str, list[dict[str, Any]]] = {}
        for signal in normalized:
            partition_date = self._partition_date(signal)
            partitions.setdefault(partition_date, []).append(signal)
        return [
            self._writer.write(partition_signals, dataset=self._DATASET, date_str=partition_date)
            for partition_date, partition_signals in partitions.items()
        ]

    def read(self, date_str: str) -> list[dict[str, Any]]:
        """Read all persisted signal artifacts for a partition date."""
        return self._reader.read(self._DATASET, date_str)

    def list_recent(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent persisted signals with optional free-text matching."""
        signals = self._reader.list_recent(self._DATASET, limit=max(limit * 4, 20))
        if query:
            signals = [signal for signal in signals if signal_matches_query(signal, query)]
        return signals[:limit]

    def find_story(self, story_id: str) -> dict[str, Any] | None:
        """Resolve the first persisted signal for a story id."""
        return self._reader.find_first(self._DATASET, "story_id", story_id)

    def _normalize_signal(self, signal: NewsSignal | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(signal, NewsSignal):
            return signal.model_dump(mode="json")
        return dict(signal)

    def _partition_date(self, signal: Mapping[str, Any]) -> str:
        model = NewsSignal(**signal)
        return model.analyzed_at.date().isoformat()


def signal_matches_query(signal: Mapping[str, Any], query: str | None) -> bool:
    """Return whether a persisted signal matches a search needle."""
    if not query:
        return True
    needle = query.lower()
    haystacks = [
        signal.get("query", ""),
        signal.get("headline", ""),
        signal.get("story_id", ""),
        *(signal.get("entities", []) or []),
    ]
    return any(needle in str(value).lower() for value in haystacks)


__all__ = ["PersistedSignalStore", "signal_matches_query"]
