"""Explicit storage helpers for persisted story signals and summaries."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from schemas.signals import NewsSignal
from storage.readers import JsonlReader
from storage.writers import JsonlWriter


class PersistedStoryStore:
    """Pragmatic read/query helpers for storage-backed story reads.

    This layer keeps API reads oriented around persisted artifacts instead of
    rebuilding ad hoc responses directly inside route handlers.
    """

    def __init__(
        self,
        *,
        reader: JsonlReader | None = None,
        writer: JsonlWriter | None = None,
    ) -> None:
        self._reader = reader or JsonlReader()
        self._writer = writer or JsonlWriter(base_dir=str(self._reader.base_dir))

    def write(self, stories: list[dict[str, Any]], *, date_str: str | None = None) -> Any:
        """Persist explicit story summary artifacts when callers have them."""
        return self._writer.write(stories, dataset="story_summaries", date_str=date_str)

    def read(self, date_str: str) -> list[dict[str, Any]]:
        """Read persisted story summary artifacts for a partition."""
        return self._reader.read("story_summaries", date_str)

    def list_recent(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
        analyze_signal: Callable[[NewsSignal], Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """List recent stories from persisted summaries or fallback signals."""
        stories = self._reader.list_recent("story_summaries", limit=max(limit * 4, 20))
        if stories:
            if query:
                stories = [story for story in stories if story_matches_query(story, query)]
            return stories[:limit]

        signals = self._reader.list_recent("signals", limit=max(limit * 4, 20))
        results: list[dict[str, Any]] = []
        for signal_data in signals:
            signal = NewsSignal(**signal_data)
            if not signal_matches_query(signal, query):
                continue
            trust = dict(analyze_signal(signal)) if analyze_signal is not None else {}
            results.append(build_story_summary(signal, trust))
            if len(results) >= limit:
                break
        return results

    def find_story_payload(
        self,
        story_id: str,
        *,
        to_trust_payload: Callable[[NewsSignal], Mapping[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Resolve a story payload from persisted trust artifacts or fallback signals."""
        payload = self._reader.find_first("trust_payloads", "story_id", story_id)
        if payload is not None:
            return payload

        payload = self._reader.find_first("story_summaries", "story_id", story_id)
        if payload is not None:
            return payload

        signal_data = self._reader.find_first("signals", "story_id", story_id)
        if signal_data is None or to_trust_payload is None:
            return None

        signal = NewsSignal(**signal_data)
        return dict(to_trust_payload(signal))


def build_story_summary(signal: NewsSignal, trust: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Convert a persisted signal into an API-ready story summary."""
    trust_payload = dict(trust or {})
    return {
        "story_id": signal.story_id,
        "headline": signal.headline,
        "query": signal.query,
        "source_name": signal.source_name,
        "published_at": signal.published_at.isoformat(),
        "analyzed_at": signal.analyzed_at.isoformat(),
        "article_count": signal.article_count,
        "entities": signal.entities,
        "trust_score": trust_payload.get("trust_score"),
        "risk_category": trust_payload.get("risk_category"),
        "calibration_status": trust_payload.get("calibration_status"),
    }


def signal_matches_query(signal: NewsSignal, query: str | None) -> bool:
    """Return whether a persisted signal matches a search needle."""
    if not query:
        return True
    needle = query.lower()
    haystacks = [signal.query, signal.headline, signal.story_id, *signal.entities]
    return any(needle in str(value).lower() for value in haystacks)


def story_matches_query(story: Mapping[str, Any], query: str | None) -> bool:
    """Return whether a persisted story summary matches a search needle."""
    if not query:
        return True
    needle = query.lower()
    haystacks = [
        story.get("story_id", ""),
        story.get("query", ""),
        story.get("headline", ""),
        story.get("source_name", ""),
        *(story.get("entities", []) or []),
    ]
    return any(needle in str(value).lower() for value in haystacks)


__all__ = [
    "PersistedStoryStore",
    "build_story_summary",
    "signal_matches_query",
    "story_matches_query",
]
