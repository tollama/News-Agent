"""Tests for SQLite-backed artifact indexing."""

from __future__ import annotations

from storage.readers import JsonlReader
from storage.writers import JsonlWriter


def test_writer_populates_sqlite_index_and_reader_uses_it(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {"story_id": "story-sqlite", "source_name": "Reuters", "value": 3},
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    db_path = tmp_path / ".artifacts.sqlite3"
    assert db_path.exists()

    reader = JsonlReader(base_dir=str(tmp_path))
    record = reader.find_first("signals", "story_id", "story-sqlite")

    assert record is not None
    assert record["value"] == 3
    assert record["source_name"] == "Reuters"
