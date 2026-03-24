"""Tests for api.routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.news_agent import NewsAgent
from api.routes import app, init_agent
from storage.persisted_stories import PersistedStoryStore
from storage.story_clusters import StoryClusterStore
from schemas.signals import NewsSignal
from storage.writers import JsonlWriter


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("NEWS_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    agent = NewsAgent(connectors=[])
    init_agent(agent)
    with TestClient(app) as c:
        yield c


def _make_signal(story_id: str = "test-story", query: str = "test") -> NewsSignal:
    now = datetime.now(UTC)
    return NewsSignal(
        story_id=story_id,
        headline="Test headline",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.0,
        entities=[],
        source_credibility=0.9,
        corroboration=0.7,
        contradiction_score=0.1,
        propagation_delay_seconds=60.0,
        freshness_score=0.9,
        novelty=0.5,
        article_count=1,
        query=query,
    )


def test_health(client):
    resp = client.get("/api/v1/news/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready(client):
    resp = client.get("/api/v1/news/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "news-agent"
    assert body["ready"] is True


def test_signals(client):
    signal = _make_signal()
    with patch.object(NewsAgent, "process_query", new_callable=AsyncMock, return_value=signal):
        resp = client.get("/api/v1/news/signals", params={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "signal" in data
    assert "trust" in data


def test_signals_invalid_dates(client):
    resp = client.get(
        "/api/v1/news/signals",
        params={
            "query": "test",
            "from": "2025-02-01T00:00:00",
            "to": "2025-01-01T00:00:00",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["message"] == "from_date must be <= to_date"


def test_analyze(client):
    resp = client.post(
        "/api/v1/news/analyze",
        json={"text": "Federal Reserve raises rates", "query": "fed"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "trust_score" in data


def test_503_when_not_initialized(client):
    import api.routes as routes

    old = routes._agent
    routes._agent = None
    try:
        resp = client.get("/api/v1/news/signals", params={"query": "test"})
        assert resp.status_code == 503
        assert resp.json()["error"]["message"] == "Agent not initialized"
    finally:
        routes._agent = old


def test_api_key_is_optional_when_not_configured(client):
    response = client.post(
        "/api/v1/news/analyze",
        json={"text": "Federal Reserve raises rates", "query": "fed"},
    )
    assert response.status_code == 200


def test_api_key_required_via_x_api_key(monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_API_KEY", "secret-news-key")
    init_agent(NewsAgent(connectors=[]))

    with TestClient(app) as local_client:
        unauthorized = local_client.post(
            "/api/v1/news/analyze",
            json={"text": "Federal Reserve raises rates", "query": "fed"},
        )
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["message"] == "Invalid or missing API key"

        authorized = local_client.post(
            "/api/v1/news/analyze",
            headers={"X-API-Key": "secret-news-key"},
            json={"text": "Federal Reserve raises rates", "query": "fed"},
        )
        assert authorized.status_code == 200


def test_api_key_required_via_bearer_token(monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_API_KEY", "secret-news-key")
    init_agent(NewsAgent(connectors=[]))

    with TestClient(app) as local_client:
        response = local_client.get(
            "/api/v1/news/signals",
            headers={"Authorization": "Bearer secret-news-key"},
            params={"query": "test"},
        )
        assert response.status_code == 200


def test_validation_errors_return_json_envelope(client):
    response = client.post("/api/v1/news/analyze", json={"query": "fed"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]


def test_recent_stories_route_reads_persisted_signals(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            _make_signal("story-1", query="fed rates").model_dump(mode="json"),
            _make_signal("story-2", query="ai chips").model_dump(mode="json"),
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/news/stories/recent", params={"limit": 2, "query": "fed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["stories"][0]["story_id"] == "story-1"
    assert payload["stories"][0]["trust_score"] >= 0.0


def test_recent_stories_route_uses_persisted_story_store(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    called: dict[str, object] = {}

    def fake_list_recent(self, *, limit: int = 20, query: str | None = None, analyze_signal=None):
        called["limit"] = limit
        called["query"] = query
        called["analyze_signal"] = callable(analyze_signal)
        return [
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
            }
        ]

    monkeypatch.setattr(PersistedStoryStore, "list_recent", fake_list_recent)

    with TestClient(app) as client:
        response = client.get("/api/v1/news/stories/recent", params={"limit": 3, "query": "powell"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["stories"][0]["story_id"] == "story-1"
    assert called == {"limit": 3, "query": "powell", "analyze_signal": True}


def test_recent_clusters_route_prefers_persisted_cluster_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                "cluster_id": "persisted-1",
                "headline": "Federal Reserve holds rates as Powell signals patience",
                "query": "fed rates",
                "story_ids": ["fed-1", "fed-2"],
                "story_count": 2,
                "total_article_count": 7,
                "source_names": ["AP", "Reuters"],
                "top_entities": ["Federal Reserve", "Jerome Powell"],
                "latest_published_at": "2026-03-24T12:00:00+00:00",
                "latest_analyzed_at": "2026-03-24T12:05:00+00:00",
                "avg_trust_score": 0.81,
                "max_trust_score": 0.88,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            }
        ],
        dataset="story_clusters",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/news/clusters/recent", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    first_cluster = payload["clusters"][0]
    assert first_cluster["cluster_id"] == "persisted-1"
    assert first_cluster["story_ids"] == ["fed-1", "fed-2"]
    assert first_cluster["avg_trust_score"] == 0.81


def test_recent_clusters_route_uses_story_cluster_store_for_persisted_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    called: dict[str, object] = {}

    def fake_list_recent(self, *, limit: int = 20, query: str | None = None):
        called["limit"] = limit
        called["query"] = query
        return [
            {
                "cluster_id": "persisted-1",
                "headline": "Federal Reserve holds rates as Powell signals patience",
                "query": "fed rates",
                "story_ids": ["fed-1", "fed-2"],
                "story_count": 2,
                "total_article_count": 7,
                "source_names": ["AP", "Reuters"],
                "top_entities": ["Federal Reserve", "Jerome Powell"],
                "latest_published_at": "2026-03-24T12:00:00+00:00",
                "latest_analyzed_at": "2026-03-24T12:05:00+00:00",
                "avg_trust_score": 0.81,
                "max_trust_score": 0.88,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            }
        ]

    monkeypatch.setattr(StoryClusterStore, "list_recent", fake_list_recent)

    with TestClient(app) as client:
        response = client.get("/api/v1/news/clusters/recent", params={"limit": 3, "query": "powell"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["clusters"][0]["cluster_id"] == "persisted-1"
    assert called == {"limit": 3, "query": "powell"}


def test_recent_clusters_route_summarizes_related_persisted_signals(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                **_make_signal("fed-1", query="fed rates").model_dump(mode="json"),
                "headline": "Federal Reserve holds rates as Powell signals patience",
                "entities": ["Federal Reserve", "Jerome Powell", "US"],
                "article_count": 4,
            },
            {
                **_make_signal("fed-2", query="fed rates").model_dump(mode="json"),
                "headline": "Powell says Federal Reserve will wait before rate cuts",
                "entities": ["Federal Reserve", "Jerome Powell", "Rates"],
                "article_count": 3,
                "source_name": "AP",
            },
            {
                **_make_signal("ai-1", query="ai chips").model_dump(mode="json"),
                "headline": "Nvidia unveils next AI chip roadmap",
                "entities": ["Nvidia", "AI", "Chips"],
                "article_count": 2,
            },
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/news/clusters/recent", params={"limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    first_cluster = payload["clusters"][0]
    assert first_cluster["story_count"] == 2
    assert first_cluster["total_article_count"] == 7
    assert set(first_cluster["story_ids"]) == {"fed-1", "fed-2"}
    assert "Federal Reserve" in first_cluster["top_entities"]
    assert set(first_cluster["source_names"]) == {"AP", "Reuters"}
    assert first_cluster["avg_trust_score"] >= 0.0


def test_recent_clusters_route_filters_by_query(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                **_make_signal("fed-1", query="fed rates").model_dump(mode="json"),
                "headline": "Federal Reserve holds rates steady",
                "entities": ["Federal Reserve", "Rates"],
            },
            {
                **_make_signal("ai-1", query="ai chips").model_dump(mode="json"),
                "headline": "Nvidia unveils AI chip roadmap",
                "entities": ["Nvidia", "AI"],
            },
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/news/clusters/recent", params={"query": "fed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["clusters"][0]["query"] == "fed rates"
    assert payload["clusters"][0]["story_ids"] == ["fed-1"]


def test_stories_route_reads_persisted_trust_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                "story_id": "story-123",
                "source_credibility": 0.91,
                "corroboration": 0.82,
                "contradiction_score": 0.05,
                "propagation_delay_seconds": 45.0,
                "freshness_score": 0.97,
                "novelty": 0.33,
            }
        ],
        dataset="trust_payloads",
        date_str="2026-03-17",
    )

    with TestClient(app) as client:
        response = client.get("/stories/story-123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == "story-123"
    assert payload["contradiction_score"] == 0.05
    assert payload["contradiction_score"] != 0.95


def test_stories_route_uses_persisted_story_store_for_lookup(monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", "/tmp/news-agent-test")
    init_agent(NewsAgent())
    called: dict[str, object] = {}

    def fake_find_story_payload(self, story_id: str, *, to_trust_payload=None, persist_generated=True):
        called["story_id"] = story_id
        called["to_trust_payload"] = callable(to_trust_payload)
        called["persist_generated"] = persist_generated
        return {
            "story_id": story_id,
            "source_credibility": 0.91,
            "corroboration": 0.82,
            "contradiction_score": 0.05,
            "propagation_delay_seconds": 45.0,
            "freshness_score": 0.97,
            "novelty": 0.33,
        }

    monkeypatch.setattr(PersistedStoryStore, "find_story_payload", fake_find_story_payload)

    with TestClient(app) as client:
        response = client.get("/stories/story-123")

    assert response.status_code == 200
    assert response.json()["story_id"] == "story-123"
    assert called == {"story_id": "story-123", "to_trust_payload": True, "persist_generated": True}


def test_stories_route_falls_back_to_persisted_signal_without_inverting_contradiction_score(
    tmp_path,
    monkeypatch,
    sample_news_signal_data,
):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    sample_news_signal_data["contradiction_score"] = 0.05
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [sample_news_signal_data],
        dataset="signals",
        date_str="2026-03-17",
    )

    with TestClient(app) as client:
        response = client.get("/stories/https://example.com/article/123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == "https://example.com/article/123"
    assert payload["contradiction_score"] == 0.05
    assert payload["contradiction_score"] != 0.95


def test_stories_route_normalizes_legacy_contradiction_penalty_shape(monkeypatch):
    import api.routes as routes

    monkeypatch.setattr(
        routes,
        "_lookup_persisted_trust_payload",
        lambda story_id: {
            "story_id": story_id,
            "source_credibility": 0.91,
            "corroboration": 0.82,
            "components": {
                "contradiction_penalty": 0.95,
            },
            "propagation_delay_seconds": 45.0,
            "freshness_score": 0.97,
            "novelty": 0.33,
        },
    )
    init_agent(NewsAgent())

    with TestClient(app) as client:
        response = client.get("/stories/story-legacy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == "story-legacy"
    assert payload["contradiction_score"] == pytest.approx(0.05)
    assert payload["contradiction_score"] != 0.95


def test_stories_route_returns_404_when_story_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())

    with TestClient(app) as client:
        response = client.get("/stories/missing-story")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
