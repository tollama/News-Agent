"""Data readers for persisted news artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from storage.sqlite_index import SQLiteArtifactIndex


class JsonlReader:
    """Read JSONL files for raw news data.

    Includes a lightweight per-dataset index cache for common story_id lookups so
    repeated API reads do not require scanning every JSONL partition.
    """

    def __init__(self, base_dir: str = "data/raw") -> None:
        self._base_dir = Path(base_dir)
        self._index_cache: dict[tuple[str, str], dict[str, Path]] = {}
        self._sqlite_index = SQLiteArtifactIndex(base_dir=base_dir)

    def read(self, dataset: str, date_str: str) -> list[dict[str, Any]]:
        """Read all records from a JSONL partition."""
        partition_dir = self._base_dir / dataset / f"dt={date_str}"
        records: list[dict[str, Any]] = []
        if not partition_dir.exists():
            return records
        for f in sorted(partition_dir.glob("*.jsonl")):
            with f.open() as fp:
                for line in fp:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records

    def read_all(self, dataset: str) -> list[dict[str, Any]]:
        """Read all records across all partitions for a dataset."""
        dataset_dir = self._base_dir / dataset
        records: list[dict[str, Any]] = []
        if not dataset_dir.exists():
            return records
        for partition_dir in sorted(dataset_dir.glob("dt=*")):
            if not partition_dir.is_dir():
                continue
            for f in sorted(partition_dir.glob("*.jsonl")):
                with f.open() as fp:
                    for line in fp:
                        line = line.strip()
                        if line:
                            records.append(json.loads(line))
        return records

    def list_recent(self, dataset: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent dataset records, preferring the SQLite sidecar."""
        recent = self._sqlite_index.list_recent(dataset, limit=limit)
        if recent:
            return recent
        records = self.read_all(dataset)
        return records[-limit:][::-1]

    def find_first(self, dataset: str, field: str, value: Any) -> dict[str, Any] | None:
        """Return the first record whose field equals the requested value."""
        sqlite_result = self._sqlite_index.find_first(dataset, field, value)
        if sqlite_result is not None:
            # Warm the legacy in-memory cache for compatibility with existing tests
            # and callers that introspect the reader cache.
            self._get_index(dataset, field)
            return sqlite_result

        indexed = self._find_first_indexed(dataset, field, value)
        if indexed is not None:
            return indexed

        for record in self.read_all(dataset):
            if record.get(field) == value:
                return record
        return None

    def _find_first_indexed(self, dataset: str, field: str, value: Any) -> dict[str, Any] | None:
        """Try a cached lookup for string-key lookups like story_id."""
        if not isinstance(value, str):
            return None

        index = self._get_index(dataset, field)
        record_path = index.get(value)
        if record_path is None or not record_path.exists():
            return None

        with record_path.open() as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get(field) == value:
                    return record
        return None

    def _get_index(self, dataset: str, field: str) -> dict[str, Path]:
        key = (dataset, field)
        if key not in self._index_cache:
            self._index_cache[key] = self._build_index(dataset, field)
        return self._index_cache[key]

    def _build_index(self, dataset: str, field: str) -> dict[str, Path]:
        dataset_dir = self._base_dir / dataset
        index: dict[str, Path] = {}
        if not dataset_dir.exists():
            return index

        for partition_dir in sorted(dataset_dir.glob("dt=*")):
            if not partition_dir.is_dir():
                continue
            for jsonl_file in sorted(partition_dir.glob("*.jsonl")):
                with jsonl_file.open() as fp:
                    for line in fp:
                        line = line.strip()
                        if not line:
                            continue
                        record = json.loads(line)
                        field_value = record.get(field)
                        if isinstance(field_value, str) and field_value not in index:
                            index[field_value] = jsonl_file
        return index


__all__ = ["JsonlReader"]
