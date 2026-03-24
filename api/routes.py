"""FastAPI routes for the News Agent service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
import os
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.news_agent import NewsAgent
from schemas.signals import NewsSignal
from services.story_clusters import build_signal_cluster_summaries
from storage.persisted_stories import PersistedStoryStore, signal_matches_query
from storage.readers import JsonlReader
from storage.story_clusters import StoryClusterStore

logger = logging.getLogger(__name__)

# Agent is initialized at startup
_agent: NewsAgent | None = None


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Auto-bootstrap from config if agent not yet initialized."""
    global _agent
    if _agent is None:
        try:
            from configs.loader import bootstrap_agent, load_config

            config = load_config()
            if config:
                _agent = bootstrap_agent(config)
                logger.info("Agent bootstrapped from config at startup")
        except Exception:
            logger.exception("Failed to bootstrap agent from config")
    yield


app = FastAPI(title="News Agent", version="0.1.0", lifespan=_lifespan)


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""

    text: str
    query: str = ""


class TrustResponse(BaseModel):
    """Response for trust endpoints."""

    story_id: str
    trust_score: float
    risk_category: str
    components: dict[str, Any]
    payload: dict[str, Any]


def get_agent() -> NewsAgent:
    """Get the global NewsAgent instance."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return _agent


def init_agent(agent: NewsAgent) -> None:
    """Initialize the global agent (called at startup)."""
    global _agent
    _agent = agent


def _data_dir() -> str:
    return os.environ.get("NEWS_AGENT_DATA_DIR", "data/raw")


def _reader() -> JsonlReader:
    return JsonlReader(base_dir=_data_dir())


def _auth_api_key() -> str | None:
    for env_name in ("NEWS_AGENT_API_KEY", "API_KEY"):
        value = os.environ.get(env_name)
        if value:
            return value
    return None


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Optional API key auth.

    When NEWS_AGENT_API_KEY or API_KEY is set, callers must provide either
    X-API-Key: <key> or Authorization: Bearer <key>.
    """
    expected = _auth_api_key()
    if not expected:
        return

    bearer_token: str | None = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            bearer_token = token.strip()

    provided = x_api_key or bearer_token
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def _story_store() -> PersistedStoryStore:
    return PersistedStoryStore(reader=_reader())


def _lookup_persisted_trust_payload(story_id: str) -> dict[str, Any] | None:
    return _story_store().find_story_payload(
        story_id,
        to_trust_payload=lambda signal: get_agent().to_trust_payload(signal),
    )


def _normalize_compat_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize legacy adapter shapes to the raw NewsTrustPayload contract."""
    normalized = dict(payload)
    nested_payload = normalized.get("payload")
    if isinstance(nested_payload, Mapping):
        normalized = dict(nested_payload)

    if normalized.get("contradiction_score") is None:
        components = normalized.get("components")
        if isinstance(components, Mapping):
            contradiction_penalty = components.get("contradiction_penalty")
            if contradiction_penalty is not None:
                try:
                    normalized["contradiction_score"] = max(
                        0.0,
                        min(1.0, 1.0 - float(contradiction_penalty)),
                    )
                except (TypeError, ValueError):
                    pass

    return normalized


def _build_recent_story_summaries(limit: int, query: str | None = None) -> list[dict[str, Any]]:
    return _story_store().list_recent(
        limit=limit,
        query=query,
        analyze_signal=lambda signal: get_agent().analyze(signal.model_dump(mode="json")),
    )


def _build_recent_cluster_summaries(limit: int, query: str | None = None) -> list[dict[str, Any]]:
    reader = _reader()
    cluster_store = StoryClusterStore(reader=reader)

    persisted_clusters = cluster_store.list_recent(limit=limit, query=query)
    if persisted_clusters:
        return persisted_clusters

    signals: list[NewsSignal] = []
    for signal_data in reader.list_recent("signals", limit=max(limit * 8, 40)):
        signal = NewsSignal(**signal_data)
        if signal_matches_query(signal, query):
            signals.append(signal)

    return build_signal_cluster_summaries(
        signals,
        lambda signal: get_agent().analyze(signal.model_dump(mode="json")),
        cluster_id_prefix="recent-cluster",
    )[:limit]


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _json_error(exc.status_code, "http_error", message)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error while serving %s %s", request.method, request.url.path)
    return _json_error(500, "internal_error", "Internal server error")


@app.get("/api/v1/news/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "news-agent"}


@app.get("/api/v1/news/ready")
async def readiness() -> dict[str, Any]:
    ready = _agent is not None
    return {
        "status": "ok" if ready else "degraded",
        "service": "news-agent",
        "ready": ready,
        "data_dir": _data_dir(),
    }


@app.get("/api/v1/news/signals", dependencies=[Depends(require_api_key)])
async def get_signals(
    query: str = Query(..., min_length=1, max_length=500),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Fetch and analyze news for the given query."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")
    logger.info("GET /signals query='%s' limit=%d", query, limit)
    agent = get_agent()
    signal = await agent.process_query(
        query,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    trust_result = agent.analyze(signal.model_dump())
    return {
        "signal": signal.model_dump(mode="json"),
        "trust": trust_result,
    }


@app.get("/api/v1/news/stories/recent", dependencies=[Depends(require_api_key)])
async def get_recent_stories(
    limit: int = Query(10, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
) -> dict[str, Any]:
    """Return recent persisted story summaries backed by the SQLite sidecar."""
    stories = _build_recent_story_summaries(limit=limit, query=query)
    return {
        "stories": stories,
        "count": len(stories),
    }


@app.get("/api/v1/news/clusters/recent", dependencies=[Depends(require_api_key)])
async def get_recent_clusters(
    limit: int = Query(10, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
) -> dict[str, Any]:
    """Return recent persisted cluster summaries backed by persisted signals."""
    clusters = _build_recent_cluster_summaries(limit=limit, query=query)
    return {
        "clusters": clusters,
        "count": len(clusters),
    }


@app.get("/api/v1/news/trust/{story_id:path}", dependencies=[Depends(require_api_key)])
async def get_trust(story_id: str) -> dict[str, Any]:
    """Get trust payload for a specific story.

    This endpoint is consumed by tollama's HttpNewsConnector
    at GET /stories/{story_id}.
    """
    payload = _lookup_persisted_trust_payload(story_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"story_id {story_id!r} not found in persisted trust artifacts",
        )
    return _normalize_compat_payload(payload)


@app.post("/api/v1/news/analyze", dependencies=[Depends(require_api_key)])
async def analyze_text(request: AnalyzeRequest) -> dict[str, Any]:
    """Analyze arbitrary text for news trust signals."""
    agent = get_agent()
    result = agent.analyze({
        "headline": request.text,
        "source_name": "user_input",
        "query": request.query,
    })
    return result


# Compatibility alias for tollama HttpNewsConnector (GET /stories/{id})
@app.get("/stories/{story_id:path}", dependencies=[Depends(require_api_key)])
async def stories_compat(story_id: str) -> dict[str, Any]:
    """Compatibility endpoint for tollama's HttpNewsConnector."""
    return await get_trust(story_id)


__all__ = ["app", "init_agent"]
