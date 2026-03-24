"""Tests for explicit persisted story storage helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from schemas.signals import NewsSignal
from storage.persisted_stories import PersistedStoryStore, story_matches_query
from storage.readers import JsonlReader
from storage.writers import JsonlWriter


def _make_signal(
    story_id: str,
    *,
    query: str = "fed rates",
    headline: str = "Federal Reserve holds rates steady",
    entities: list[str] | None = None,
) -> NewsSignal:
    now = datetime.now(UTC)
    return NewsSignal(
        story_id=story_id,
        headline=headline,
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.0,
        entities=entities or ["Federal Reserve", "Jerome Powell"],
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.5,
        article_count=2,
        query=query,
    )


def test_persisted_story_store_prefers_story_summaries_for_recent_reads(tmp_path):
    store = PersistedStoryStore(reader=JsonlReader(base_dir=str(tmp_path)))
    store.write(
        [
            {
                "story_id": "story-1",
                "headline": "Federal Reserve holds rates steady",
                "query": "fed rates",
                "source_name": "Reuters",
                "published_at": "2026-03-24T12:00:00+00:00",
                "analyzed_at": "2026-03-24T12:05:00+00:00",
                "article_count": 2,
                "entities": ["Federal Reserve", "Jerome Powell"],
                "trust_score": 0.81,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            },
            {
                "story_id": "story-2",
                "headline": "Nvidia unveils AI chip roadmap",
                "query": "ai chips",
                "source_name": "Reuters",
                "published_at": "2026-03-24T10:00:00+00:00",
                "analyzed_at": "2026-03-24T10:05:00+00:00",
                "article_count": 1,
                "entities": ["Nvidia", "AI"],
                "trust_score": 0.75,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            },
        ],
        date_str="2026-03-24",
    )

    recent = store.list_recent(limit=5, query="powell")

    assert [story["story_id"] for story in recent] == ["story-1"]
    assert recent[0]["trust_score"] == 0.81


def test_persisted_story_store_builds_recent_stories_from_signals(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            _make_signal("story-1").model_dump(mode="json"),
            _make_signal(
                "story-2",
                query="ai chips",
                headline="Nvidia unveils AI chip roadmap",
                entities=["Nvidia", "AI"],
            ).model_dump(mode="json"),
        ],
        dataset="signals",
        date_str="2026-03-24",
    )
    store = PersistedStoryStore(reader=JsonlReader(base_dir=str(tmp_path)))

    recent = store.list_recent(
        limit=5,
        query="fed",
        analyze_signal=lambda signal: {
            "trust_score": 0.82 if signal.story_id == "story-1" else 0.55,
            "risk_category": "low",
            "calibration_status": "well_calibrated",
        },
    )

    assert [story["story_id"] for story in recent] == ["story-1"]
    assert recent[0]["risk_category"] == "low"

    persisted = JsonlReader(base_dir=str(tmp_path)).find_first("story_summaries", "story_id", "story-1")
    assert persisted is not None
    assert persisted["trust_score"] == 0.82


def test_persisted_story_store_finds_story_payload_via_signal_fallback(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [_make_signal("story-1").model_dump(mode="json")],
        dataset="signals",
        date_str="2026-03-24",
    )
    store = PersistedStoryStore(reader=JsonlReader(base_dir=str(tmp_path)))

    payload = store.find_story_payload(
        "story-1",
        to_trust_payload=lambda signal: {
            "story_id": signal.story_id,
            "source_credibility": signal.source_credibility,
            "corroboration": signal.corroboration,
            "contradiction_score": signal.contradiction_score,
            "propagation_delay_seconds": signal.propagation_delay_seconds,
            "freshness_score": signal.freshness_score,
            "novelty": signal.novelty,
            "published_at": signal.published_at.isoformat(),
            "analyzed_at": signal.analyzed_at.isoformat(),
        },
    )

    assert payload is not None
    assert payload["story_id"] == "story-1"
    assert payload["contradiction_score"] == 0.1

    persisted = JsonlReader(base_dir=str(tmp_path)).find_first("trust_payloads", "story_id", "story-1")
    assert persisted is not None
    assert persisted["contradiction_score"] == 0.1


def test_persisted_story_store_can_skip_persisting_generated_trust_payload(tmp_path):
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [_make_signal("story-1").model_dump(mode="json")],
        dataset="signals",
        date_str="2026-03-24",
    )
    store = PersistedStoryStore(reader=JsonlReader(base_dir=str(tmp_path)))

    payload = store.find_story_payload(
        "story-1",
        to_trust_payload=lambda signal: {
            "story_id": signal.story_id,
            "source_credibility": signal.source_credibility,
            "corroboration": signal.corroboration,
            "contradiction_score": signal.contradiction_score,
            "propagation_delay_seconds": signal.propagation_delay_seconds,
            "freshness_score": signal.freshness_score,
            "novelty": signal.novelty,
            "published_at": signal.published_at.isoformat(),
            "analyzed_at": signal.analyzed_at.isoformat(),
        },
        persist_generated=False,
    )

    assert payload is not None
    persisted = JsonlReader(base_dir=str(tmp_path)).find_first("trust_payloads", "story_id", "story-1")
    assert persisted is None


def test_story_matches_query_checks_summary_fields():
    story = {
        "story_id": "story-fed-1",
        "headline": "Federal Reserve holds rates steady",
        "query": "fed rates",
        "source_name": "Reuters",
        "entities": ["Federal Reserve", "Jerome Powell"],
    }

    assert story_matches_query(story, "powell") is True
    assert story_matches_query(story, "reuters") is True
    assert story_matches_query(story, "missing") is False
