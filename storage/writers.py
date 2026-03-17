"""Data writers for persisting news artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class JsonlWriter:
    """Write JSONL files for raw news data."""

    def __init__(self, base_dir: str = "data/raw") -> None:
        self._base_dir = Path(base_dir)

    def write(
        self,
        records: list[dict[str, Any]],
        dataset: str,
        date_str: str | None = None,
    ) -> Path:
        """Write records to a JSONL file in a date-partitioned directory."""
        if date_str is None:
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        partition_dir = self._base_dir / dataset / f"dt={date_str}"
        partition_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(UTC).strftime("%H%M%S")
        filepath = partition_dir / f"{ts}.jsonl"
        with filepath.open("w") as fp:
            for record in records:
                fp.write(json.dumps(record, default=str) + "\n")
        return filepath


__all__ = ["JsonlWriter"]
