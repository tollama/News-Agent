"""Tests for persisted JSONL readers."""

from __future__ import annotations

from storage.readers import JsonlReader
from storage.writers import JsonlWriter


def test_find_first_uses_story_id_index_cache(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {"story_id": "story-1", "value": 1},
            {"story_id": "story-2", "value": 2},
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    reader = JsonlReader(base_dir=str(tmp_path))
    first = reader.find_first("signals", "story_id", "story-2")
    second = reader.find_first("signals", "story_id", "story-2")

    assert first == second
    assert first is not None
    assert first["value"] == 2
    assert ("signals", "story_id") in reader._index_cache
