"""Data writers for persisting news artifacts."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from storage.sqlite_index import SQLiteArtifactIndex

logger = logging.getLogger(__name__)


class JsonlWriter:
    """Write JSONL files for raw news data.

    JSONL remains the append-log format, while a small SQLite sidecar is updated
    to accelerate practical lookups across persisted artifacts.
    """

    def __init__(self, base_dir: str = "data/raw") -> None:
        self._base_dir = Path(base_dir)
        self._sqlite_index = SQLiteArtifactIndex(base_dir=base_dir)

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

        try:
            self._sqlite_index.upsert_records(dataset, date_str, filepath, records)
        except Exception:  # pragma: no cover - fallback keeps JSONL writes alive
            logger.exception("Failed to update SQLite artifact index for %s", filepath)

        return filepath


__all__ = ["JsonlWriter"]
