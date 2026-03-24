"""Explicit storage helpers for persisted story signals, summaries, and trust payloads."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from schemas.signals import NewsSignal
from storage.persisted_signals import PersistedSignalStore
from storage.readers import JsonlReader
from storage.writers import JsonlWriter


class PersistedStoryStore:
    """Pragmatic read/query helpers for storage-backed story reads.

    This layer keeps API reads oriented around persisted artifacts instead of
    rebuilding ad hoc responses directly inside route handlers.
    """

    _TRUST_PAYLOAD_DATASET = "trust_payloads"
    _STORY_SUMMARY_DATASET = "story_summaries"

    def __init__(
        self,
        *,
        reader: JsonlReader | None = None,
        writer: JsonlWriter | None = None,
    ) -> None:
        self._reader = reader or JsonlReader()
        self._writer = writer or JsonlWriter(base_dir=str(self._reader.base_dir))
        self._signal_store = PersistedSignalStore(reader=self._reader, writer=self._writer)

    def write(self, stories: list[dict[str, Any]], *, date_str: str | None = None) -> Any:
        """Persist explicit story summary artifacts when callers have them."""
        return self._writer.write(stories, dataset=self._STORY_SUMMARY_DATASET, date_str=date_str)

    def write_by_partition(self, stories: list[dict[str, Any]]) -> list[Any]:
        """Persist story summaries grouped by their analyzed/published date."""
        return self._write_records_by_partition(stories, dataset=self._STORY_SUMMARY_DATASET)

    def write_trust_payloads(self, payloads: list[dict[str, Any]], *, date_str: str | None = None) -> Any:
        """Persist normalized trust payload artifacts when callers have them."""
        normalized_payloads = [normalize_trust_payload(payload) for payload in payloads]
        return self._writer.write(normalized_payloads, dataset=self._TRUST_PAYLOAD_DATASET, date_str=date_str)

    def write_trust_payloads_by_partition(self, payloads: list[dict[str, Any]]) -> list[Any]:
        """Persist trust payloads grouped by their analyzed/published date."""
        normalized_payloads = [normalize_trust_payload(payload) for payload in payloads]
        return self._write_records_by_partition(normalized_payloads, dataset=self._TRUST_PAYLOAD_DATASET)

    def read(self, date_str: str) -> list[dict[str, Any]]:
        """Read persisted story summary artifacts for a partition."""
        return self._reader.read(self._STORY_SUMMARY_DATASET, date_str)

    def readiness(self) -> dict[str, Any]:
        """Return lightweight storage/readiness details for observability endpoints."""
        base_dir = self._reader.base_dir
        sqlite_path = base_dir / ".artifacts.sqlite3"
        return {
            "data_dir": str(base_dir),
            "data_dir_exists": base_dir.exists(),
            "data_dir_writable": _is_writable_dir(base_dir),
            "sqlite_index_path": str(sqlite_path),
            "sqlite_index_exists": sqlite_path.exists(),
        }

    def _write_records_by_partition(
        self,
        records: list[Mapping[str, Any]],
        *,
        dataset: str,
    ) -> list[Any]:
        writes: list[Any] = []
        for partition_date, partition_records in _group_records_by_partition_date(records).items():
            writes.append(self._writer.write(partition_records, dataset=dataset, date_str=partition_date))
        return writes

    def list_recent(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
        analyze_signal: Callable[[NewsSignal], Mapping[str, Any]] | None = None,
        persist_generated: bool = True,
    ) -> list[dict[str, Any]]:
        """List recent stories from persisted summaries or fallback signals."""
        stories = self._reader.list_recent("story_summaries", limit=max(limit * 4, 20))
        if stories:
            if query:
                stories = [story for story in stories if story_matches_query(story, query)]
            return stories[:limit]

        signals = self._signal_store.list_recent(limit=max(limit * 4, 20), query=query)
        generated_stories: list[dict[str, Any]] = []
        for signal_data in signals:
            signal = NewsSignal(**signal_data)
            trust = dict(analyze_signal(signal)) if analyze_signal is not None else {}
            generated_stories.append(build_story_summary(signal, trust))
            if len(generated_stories) >= limit:
                break

        if generated_stories and persist_generated:
            self.write_by_partition(generated_stories)
        return generated_stories

    def find_story_payload(
        self,
        story_id: str,
        *,
        to_trust_payload: Callable[[NewsSignal], Mapping[str, Any]] | None = None,
        persist_generated: bool = True,
    ) -> dict[str, Any] | None:
        """Resolve a normalized trust payload from persisted artifacts or fallback signals."""
        payload = self._reader.find_first(self._TRUST_PAYLOAD_DATASET, "story_id", story_id)
        if payload is not None:
            normalized = normalize_trust_payload(payload)
            if persist_generated and normalized != payload:
                self.write_trust_payloads_by_partition([normalized])
            return normalized

        signal_data = self._signal_store.find_story(story_id)
        if signal_data is not None and to_trust_payload is not None:
            signal = NewsSignal(**signal_data)
            generated_payload = normalize_trust_payload(dict(to_trust_payload(signal)))
            if persist_generated and generated_payload:
                self.write_trust_payloads_by_partition([generated_payload])
            return generated_payload

        story_summary = self._reader.find_first(self._STORY_SUMMARY_DATASET, "story_id", story_id)
        if story_summary is not None:
            return normalize_trust_payload(story_summary)

        return None


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


def normalize_trust_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize legacy adapter shapes to the raw NewsTrustPayload contract."""
    normalized = dict(payload)
    nested_payload = normalized.get("payload")
    if isinstance(nested_payload, Mapping):
        normalized = dict(nested_payload)

    if normalized.get("contradiction_score") is None:
        components = normalized.get("components")
        if isinstance(components, Mapping):
            contradiction_penalty = components.get("contradiction_penalty")
            if contradiction_penalty is not None:
                try:
                    normalized["contradiction_score"] = max(
                        0.0,
                        min(1.0, 1.0 - float(contradiction_penalty)),
                    )
                except (TypeError, ValueError):
                    pass

    return normalized


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


def _group_records_by_partition_date(records: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group persisted artifacts by date derived from analyzed/published timestamps."""
    partitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        partition_date = _partition_date_for_record(record)
        partitions[partition_date].append(dict(record))
    return dict(partitions)


def _partition_date_for_record(record: Mapping[str, Any]) -> str:
    for field in ("analyzed_at", "published_at"):
        raw_value = record.get(field)
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


def _is_writable_dir(path: Path) -> bool:
    candidate = path if path.exists() else path.parent
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return candidate.exists() and candidate.is_dir()


__all__ = [
    "PersistedStoryStore",
    "build_story_summary",
    "normalize_trust_payload",
    "signal_matches_query",
    "story_matches_query",
]
