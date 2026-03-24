"""Tests for api.routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.news_agent import NewsAgent
from api.routes import app, init_agent
from storage.persisted_signals import encode_persisted_signal_cursor
from services.persisted_story_clusters import PersistedStoryClusterService
from storage.persisted_signals import PersistedSignalStore
from storage.persisted_stories import PersistedStoryStore
from storage.readers import JsonlReader
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
    assert body["data_dir_exists"] is True
    assert body["data_dir_writable"] is True
    assert body["sqlite_index_path"].endswith(".artifacts.sqlite3")


def test_signals(client):
    signal = _make_signal()
    with patch.object(NewsAgent, "process_query", new_callable=AsyncMock, return_value=signal):
        resp = client.get("/api/v1/news/signals", params={"query": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "signal" in data
    assert "trust" in data
    assert data["source"] == "live"


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


def test_signals_requires_query_for_live_mode(client):
    resp = client.get("/api/v1/news/signals")

    assert resp.status_code == 422
    assert resp.json()["error"]["message"] == "query is required unless persisted=true"


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


def test_signals_route_reads_persisted_signal_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                **_make_signal("story-1", query="fed rates").model_dump(mode="json"),
                "headline": "Federal Reserve holds rates steady",
                "entities": ["Federal Reserve", "Rates"],
            },
            {
                **_make_signal("story-2", query="ai chips").model_dump(mode="json"),
                "headline": "Nvidia unveils AI chip roadmap",
                "entities": ["Nvidia", "AI"],
                "source_name": "Bloomberg",
            },
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/news/signals",
            params={
                "persisted": True,
                "query": "fed",
                "story_id": "story-1",
                "limit": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "persisted"
    assert payload["count"] == 1
    assert payload["signals"][0]["story_id"] == "story-1"
    assert payload["signals"][0]["headline"] == "Federal Reserve holds rates steady"


def test_signals_route_uses_persisted_signal_store_for_product_reads(monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", "/tmp/news-agent-test")
    init_agent(NewsAgent())
    called: dict[str, object] = {}

    def fake_list_recent_page(self, *, limit=20, query=None, story_id=None, from_date=None, to_date=None, cursor=None):
        called["limit"] = limit
        called["query"] = query
        called["story_id"] = story_id
        called["from_date"] = from_date.isoformat() if from_date else None
        called["to_date"] = to_date.isoformat() if to_date else None
        called["cursor"] = cursor
        return {
            "signals": [
                {
                    "story_id": "story-1",
                    "headline": "Federal Reserve holds rates steady",
                    "query": "fed rates",
                }
            ],
            "count": 1,
            "has_more": True,
            "next_cursor": "next-cursor-token",
        }

    monkeypatch.setattr(PersistedSignalStore, "list_recent_page", fake_list_recent_page)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/news/signals",
            params={
                "persisted": True,
                "query": "powell",
                "story_id": "story-1",
                "from": "2026-03-24T00:00:00+00:00",
                "to": "2026-03-25T00:00:00+00:00",
                "limit": 3,
                "cursor": encode_persisted_signal_cursor(3),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["signals"][0]["story_id"] == "story-1"
    assert payload["has_more"] is True
    assert payload["next_cursor"] == "next-cursor-token"
    assert called == {
        "limit": 3,
        "query": "powell",
        "story_id": "story-1",
        "from_date": "2026-03-24T00:00:00+00:00",
        "to_date": "2026-03-25T00:00:00+00:00",
        "cursor": encode_persisted_signal_cursor(3),
    }


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


def test_recent_clusters_route_uses_cluster_service_for_persisted_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    called: dict[str, object] = {}

    def fake_list_recent(
        self,
        *,
        limit: int = 20,
        query: str | None = None,
        analyze_signal=None,
        persist_generated: bool = True,
        cluster_id_prefix: str = "recent-cluster",
    ):
        called["limit"] = limit
        called["query"] = query
        called["analyze_signal"] = callable(analyze_signal)
        called["persist_generated"] = persist_generated
        called["cluster_id_prefix"] = cluster_id_prefix
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

    monkeypatch.setattr(PersistedStoryClusterService, "list_recent", fake_list_recent)

    with TestClient(app) as client:
        response = client.get("/api/v1/news/clusters/recent", params={"limit": 3, "query": "powell"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["clusters"][0]["cluster_id"] == "persisted-1"
    assert called == {
        "limit": 3,
        "query": "powell",
        "analyze_signal": True,
        "persist_generated": True,
        "cluster_id_prefix": "recent-cluster",
    }


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


def test_stories_route_normalizes_legacy_contradiction_penalty_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            {
                "story_id": "story-legacy",
                "payload": {
                    "story_id": "story-legacy",
                    "source_credibility": 0.91,
                    "corroboration": 0.82,
                    "components": {
                        "contradiction_penalty": 0.95,
                    },
                    "propagation_delay_seconds": 45.0,
                    "freshness_score": 0.97,
                    "novelty": 0.33,
                },
            }
        ],
        dataset="trust_payloads",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/stories/story-legacy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == "story-legacy"
    assert payload["contradiction_score"] == pytest.approx(0.05)
    assert payload["contradiction_score"] != 0.95


def test_stories_route_prefers_signal_backfill_over_summary_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    signal = _make_signal("story-123", query="fed rates")
    writer.write([signal.model_dump(mode="json")], dataset="signals", date_str="2026-03-24")
    PersistedStoryStore(reader=JsonlReader(base_dir=str(tmp_path))).write(
        [
            {
                "story_id": "story-123",
                "headline": signal.headline,
                "query": signal.query,
                "source_name": signal.source_name,
                "published_at": signal.published_at.isoformat(),
                "analyzed_at": signal.analyzed_at.isoformat(),
                "article_count": signal.article_count,
                "entities": signal.entities,
                "trust_score": 0.81,
                "risk_category": "low",
                "calibration_status": "well_calibrated",
            }
        ],
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        response = client.get("/stories/story-123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == "story-123"
    assert payload["source_credibility"] == 0.9
    assert "headline" not in payload


def test_stories_route_returns_404_when_story_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())

    with TestClient(app) as client:
        response = client.get("/stories/missing-story")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_signals_route_returns_cursor_metadata_for_persisted_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_AGENT_DATA_DIR", str(tmp_path))
    init_agent(NewsAgent())
    writer = JsonlWriter(base_dir=str(tmp_path))
    writer.write(
        [
            _make_signal("story-1", query="fed rates").model_dump(mode="json"),
            _make_signal("story-2", query="fed rates").model_dump(mode="json"),
            _make_signal("story-3", query="fed rates").model_dump(mode="json"),
        ],
        dataset="signals",
        date_str="2026-03-24",
    )

    with TestClient(app) as client:
        first = client.get("/api/v1/news/signals", params={"persisted": True, "limit": 2})
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["count"] == 2
        assert first_payload["has_more"] is True
        assert first_payload["next_cursor"] is not None

        second = client.get(
            "/api/v1/news/signals",
            params={"persisted": True, "limit": 2, "cursor": first_payload["next_cursor"]},
        )

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["count"] == 1
    assert second_payload["has_more"] is False
    assert second_payload["next_cursor"] is None


def test_signals_route_rejects_invalid_persisted_cursor(client):
    response = client.get("/api/v1/news/signals", params={"persisted": True, "cursor": "bad-cursor"})

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "cursor must be a valid persisted signals cursor"


def test_openapi_documents_product_facing_route_metadata(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    signals_operation = schema["paths"]["/api/v1/news/signals"]["get"]
    assert signals_operation["summary"] == "Fetch a live signal or list persisted signals"
    assert "Persisted mode (`persisted=true`)" in signals_operation["description"]
    assert signals_operation["tags"] == ["signals"]
    assert "400" in signals_operation["responses"]
    assert "422" in signals_operation["responses"]

    trust_operation = schema["paths"]["/api/v1/news/trust/{story_id}"]["get"]
    assert trust_operation["summary"] == "Fetch a normalized trust payload for one story"
    assert trust_operation["tags"] == ["trust"]

    readiness_response = schema["paths"]["/api/v1/news/ready"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert readiness_response["$ref"] == "#/components/schemas/ReadinessPayload"

    stories_response = schema["paths"]["/api/v1/news/stories/recent"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert stories_response["$ref"] == "#/components/schemas/StorySummaryListResponse"

    clusters_response = schema["paths"]["/api/v1/news/clusters/recent"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert clusters_response["$ref"] == "#/components/schemas/ClusterSummaryListResponse"


def test_openapi_exposes_union_response_for_live_and_persisted_signals(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    response_schema = schema["paths"]["/api/v1/news/signals"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    options = response_schema["anyOf"]
    refs = {option["$ref"] for option in options}
    assert "#/components/schemas/LiveSignalResponse" in refs
    assert "#/components/schemas/PersistedSignalPage" in refs

    persisted_signal_page = schema["components"]["schemas"]["PersistedSignalPage"]
    persisted_signal_rows = persisted_signal_page["properties"]["signals"]["items"]
    assert persisted_signal_rows["$ref"] == "#/components/schemas/PersistedSignalRow"
