"""SQLite-backed artifact index for persisted news datasets.

Keeps JSONL as the source-of-truth append log while adding a pragmatic lookup
layer for repeated reads by story_id (and other scalar fields).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteArtifactIndex:
    """Small SQLite index/store for persisted artifact records."""

    def __init__(self, base_dir: str = "data/raw") -> None:
        self._base_dir = Path(base_dir)
        self._db_path = self._base_dir / ".artifacts.sqlite3"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def upsert_records(
        self,
        dataset: str,
        date_str: str,
        filepath: Path,
        records: list[dict[str, Any]],
    ) -> None:
        if not records:
            return

        payloads: list[tuple[str, str, str, str, str, str]] = []
        for record in records:
            record_json = json.dumps(record, default=str)
            for field, value in record.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    payloads.append(
                        (
                            dataset,
                            date_str,
                            str(filepath),
                            field,
                            self._normalize_value(value),
                            record_json,
                        )
                    )

        if not payloads:
            return

        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO artifact_records (
                    dataset, date_str, file_path, field_name, field_value, record_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                payloads,
            )
            conn.commit()

    def find_first(self, dataset: str, field: str, value: Any) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT record_json
                FROM artifact_records
                WHERE dataset = ? AND field_name = ? AND field_value = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (dataset, field, self._normalize_value(value)),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list_recent(self, dataset: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent distinct records for a dataset ordered by ingest time desc."""
        safe_limit = max(1, min(int(limit), 200))
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT record_json
                FROM artifact_records
                WHERE dataset = ?
                GROUP BY record_json
                ORDER BY MAX(id) DESC
                LIMIT ?
                """,
                (dataset, safe_limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _initialize(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifact_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset TEXT NOT NULL,
                    date_str TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    field_value TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifact_lookup
                ON artifact_records(dataset, field_name, field_value, id)
                """
            )
            conn.commit()

    @staticmethod
    def _normalize_value(value: Any) -> str:
        if value is None:
            return "__none__"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)


__all__ = ["SQLiteArtifactIndex"]
