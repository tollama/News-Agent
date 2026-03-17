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


__all__ = ["JsonlReader"]
