"""Tests for explicit persisted signal storage helpers."""

from __future__ import annotations

import pytest

from datetime import UTC, datetime

from schemas.signals import NewsSignal
from storage.persisted_signals import PersistedSignalStore, decode_persisted_signal_cursor
from storage.readers import JsonlReader


def _make_signal(story_id: str, *, query: str = "fed rates", analyzed_at: datetime | None = None) -> NewsSignal:
    now = analyzed_at or datetime(2026, 3, 24, 12, 0, tzinfo=UTC)
    return NewsSignal(
        story_id=story_id,
        headline=f"Headline for {story_id}",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.0,
        entities=["Federal Reserve", "Jerome Powell"],
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.5,
        article_count=2,
        query=query,
    )


def test_persisted_signal_store_writes_and_reads_signals(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))
    signal = _make_signal("story-1")

    store.write([signal], date_str="2026-03-24")

    persisted = store.find_story("story-1")
    assert persisted is not None
    assert persisted["story_id"] == "story-1"
    assert persisted["headline"] == "Headline for story-1"


def test_persisted_signal_store_lists_recent_with_query_filter(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))
    store.write(
        [
            _make_signal("story-fed", query="fed rates"),
            _make_signal("story-ai", query="ai chips"),
        ],
        date_str="2026-03-24",
    )

    recent = store.list_recent(limit=5, query="story-fed")

    assert [signal["story_id"] for signal in recent] == ["story-fed"]


def test_persisted_signal_store_lists_recent_with_story_id_and_date_filters(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))
    store.write_by_partition(
        [
            _make_signal("story-fed", analyzed_at=datetime(2026, 3, 24, 12, 0, tzinfo=UTC)),
            _make_signal("story-ai", query="ai chips", analyzed_at=datetime(2026, 3, 25, 12, 0, tzinfo=UTC)),
        ]
    )

    recent = store.list_recent(
        limit=5,
        story_id="story-fed",
        from_date=datetime(2026, 3, 24, 0, 0, tzinfo=UTC),
        to_date=datetime(2026, 3, 24, 23, 59, tzinfo=UTC),
    )

    assert [signal["story_id"] for signal in recent] == ["story-fed"]


def test_persisted_signal_store_writes_by_partition_from_signal_timestamps(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))
    store.write_by_partition(
        [
            _make_signal("story-1", analyzed_at=datetime(2026, 3, 24, 0, 5, tzinfo=UTC)),
            _make_signal("story-2", analyzed_at=datetime(2026, 3, 25, 0, 5, tzinfo=UTC)),
        ]
    )

    reader = JsonlReader(base_dir=str(tmp_path))
    assert reader.find_first("signals", "story_id", "story-1") is not None
    assert reader.read("signals", "2026-03-24")[0]["story_id"] == "story-1"
    assert reader.read("signals", "2026-03-25")[0]["story_id"] == "story-2"


def test_persisted_signal_store_lists_recent_page_with_cursor(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))
    store.write(
        [
            _make_signal("story-1"),
            _make_signal("story-2"),
            _make_signal("story-3"),
        ],
        date_str="2026-03-24",
    )

    first_page = store.list_recent_page(limit=2)

    assert [signal["story_id"] for signal in first_page["signals"]] == ["story-3", "story-2"]
    assert first_page["count"] == 2
    assert first_page["has_more"] is True
    assert first_page["next_cursor"] is not None

    second_page = store.list_recent_page(limit=2, cursor=first_page["next_cursor"])

    assert [signal["story_id"] for signal in second_page["signals"]] == ["story-1"]
    assert second_page["count"] == 1
    assert second_page["has_more"] is False
    assert second_page["next_cursor"] is None


def test_persisted_signal_store_rejects_invalid_cursor(tmp_path):
    store = PersistedSignalStore(reader=JsonlReader(base_dir=str(tmp_path)))

    with pytest.raises(ValueError, match="Invalid cursor"):
        store.list_recent_page(limit=2, cursor="not-a-real-cursor")

    with pytest.raises(ValueError, match="Invalid cursor"):
        decode_persisted_signal_cursor("not-a-real-cursor")
