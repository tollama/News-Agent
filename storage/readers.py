"""Data readers for persisted news artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonlReader:
    """Read JSONL files for raw news data."""

    def __init__(self, base_dir: str = "data/raw") -> None:
        self._base_dir = Path(base_dir)

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

    def find_first(self, dataset: str, field: str, value: Any) -> dict[str, Any] | None:
        """Return the first record whose field equals the requested value."""
        for record in self.read_all(dataset):
            if record.get(field) == value:
                return record
        return None


__all__ = ["JsonlReader"]
