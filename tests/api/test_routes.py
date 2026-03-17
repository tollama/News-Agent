"""Tests for api.routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.news_agent import NewsAgent
from api.routes import app, init_agent
from schemas.signals import NewsSignal


@pytest.fixture()
def client():
    agent = NewsAgent(connectors=[])
    init_agent(agent)
    with TestClient(app) as c:
        yield c


def _make_signal() -> NewsSignal:
    now = datetime.now(UTC)
    return NewsSignal(
        story_id="test-story",
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
        query="test",
    )


def test_health(client):
    resp = client.get("/api/v1/news/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


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
    finally:
        routes._agent = old
