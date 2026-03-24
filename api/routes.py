"""FastAPI routes for the News Agent service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agents.news_agent import NewsAgent
from schemas.api_models import (
    AnalyzeRequest,
    ClusterSummaryListResponse,
    ErrorEnvelope,
    LiveSignalResponse,
    NormalizedTrustResult,
    PersistedSignalPage,
    ReadinessPayload,
    StorySummaryListResponse,
    TrustPayloadResponse,
)
from services.persisted_story_clusters import PersistedStoryClusterService
from storage.persisted_signals import PersistedSignalStore, decode_persisted_signal_cursor
from storage.persisted_stories import PersistedStoryStore
from storage.readers import JsonlReader

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


app = FastAPI(
    title="News Agent",
    version="0.1.0",
    lifespan=_lifespan,
    description=(
        "HTTP surface for live news trust analysis plus persisted signal, story, and cluster reads "
        "consumed by Tollama connectors and internal product clients."
    ),
)


API_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope, "description": "Bad request"},
    401: {"model": ErrorEnvelope, "description": "Authentication failed"},
    404: {"model": ErrorEnvelope, "description": "Artifact not found"},
    422: {"model": ErrorEnvelope, "description": "Validation error"},
    500: {"model": ErrorEnvelope, "description": "Internal server error"},
}


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


def _signal_store() -> PersistedSignalStore:
    return PersistedSignalStore(reader=_reader())


def _lookup_persisted_trust_payload(story_id: str) -> dict[str, Any] | None:
    return _story_store().find_story_payload(
        story_id,
        to_trust_payload=lambda signal: get_agent().to_trust_payload(signal),
    )


def _build_recent_story_summaries(limit: int, query: str | None = None) -> list[dict[str, Any]]:
    return _story_store().list_recent(
        limit=limit,
        query=query,
        analyze_signal=lambda signal: get_agent().analyze(signal.model_dump(mode="json")),
    )


def _build_recent_cluster_summaries(limit: int, query: str | None = None) -> list[dict[str, Any]]:
    return PersistedStoryClusterService(reader=_reader()).list_recent(
        limit=limit,
        query=query,
        analyze_signal=lambda signal: get_agent().analyze(signal.model_dump(mode="json")),
        cluster_id_prefix="recent-cluster",
    )


def _build_recent_signals(
    *,
    limit: int,
    query: str | None = None,
    story_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    return _signal_store().list_recent_page(
        limit=limit,
        query=query,
        story_id=story_id,
        from_date=from_date,
        to_date=to_date,
        cursor=cursor,
    )


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


@app.get(
    "/api/v1/news/health",
    tags=["system"],
    summary="Health check",
    description="Lightweight liveness probe for load balancers and local service checks.",
)
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "news-agent"}


@app.get(
    "/api/v1/news/ready",
    tags=["system"],
    summary="Readiness and storage status",
    description="Reports whether the agent is initialized and whether persisted storage is writable.",
)
async def readiness() -> ReadinessPayload:
    ready = _agent is not None
    storage = _story_store().readiness()
    return {
        "status": "ok" if ready and storage["data_dir_writable"] else "degraded",
        "service": "news-agent",
        "ready": ready,
        **storage,
    }


@app.get(
    "/api/v1/news/signals",
    dependencies=[Depends(require_api_key)],
    tags=["signals"],
    summary="Fetch a live signal or list persisted signals",
    description=(
        "Live mode runs the full fetch → feature → trust pipeline and requires `query`. "
        "Persisted mode (`persisted=true`) reads stored signal artifacts, supports product-facing filters, "
        "and returns cursor pagination metadata."
    ),
    response_model=LiveSignalResponse | PersistedSignalPage,
    responses=API_ERROR_RESPONSES,
)
async def get_signals(
    query: str | None = Query(None, min_length=1, max_length=500),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=500),
    persisted: bool = Query(False),
    story_id: str | None = Query(None, min_length=1, max_length=1000),
    cursor: str | None = Query(None, min_length=1, max_length=1000),
) -> dict[str, Any]:
    """Fetch live news signals or retrieve persisted signal artifacts."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be <= to_date")

    if persisted:
        if cursor is not None:
            try:
                decode_persisted_signal_cursor(cursor)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="cursor must be a valid persisted signals cursor") from exc

        logger.info("GET /signals persisted=true query=%r story_id=%r limit=%d cursor=%r", query, story_id, limit, cursor)
        page = _build_recent_signals(
            limit=limit,
            query=query,
            story_id=story_id,
            from_date=from_date,
            to_date=to_date,
            cursor=cursor,
        )
        return {
            **page,
            "source": "persisted",
        }

    if not query:
        raise HTTPException(status_code=422, detail="query is required unless persisted=true")

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
        "source": "live",
    }


@app.get(
    "/api/v1/news/stories/recent",
    dependencies=[Depends(require_api_key)],
    tags=["stories"],
    summary="List recent persisted story summaries",
    description=(
        "Returns consumer-friendly story summary rows backed by persisted artifacts, "
        "including trust rollups when available."
    ),
    response_model=StorySummaryListResponse,
    responses=API_ERROR_RESPONSES,
)
async def get_recent_stories(
    limit: int = Query(10, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
) -> StorySummaryListResponse:
    """Return recent persisted story summaries backed by the SQLite sidecar."""
    stories = _build_recent_story_summaries(limit=limit, query=query)
    return {
        "stories": stories,
        "count": len(stories),
    }


@app.get(
    "/api/v1/news/clusters/recent",
    dependencies=[Depends(require_api_key)],
    tags=["clusters"],
    summary="List recent persisted cluster summaries",
    description=(
        "Returns recent event/story cluster summaries backed by explicit cluster artifacts "
        "or reconstructed from persisted signals when needed."
    ),
    response_model=ClusterSummaryListResponse,
    responses=API_ERROR_RESPONSES,
)
async def get_recent_clusters(
    limit: int = Query(10, ge=1, le=100),
    query: str | None = Query(None, min_length=1, max_length=500),
) -> ClusterSummaryListResponse:
    """Return recent persisted cluster summaries backed by persisted signals."""
    clusters = _build_recent_cluster_summaries(limit=limit, query=query)
    return {
        "clusters": clusters,
        "count": len(clusters),
    }


@app.get(
    "/api/v1/news/trust/{story_id:path}",
    dependencies=[Depends(require_api_key)],
    tags=["trust"],
    summary="Fetch a normalized trust payload for one story",
    description=(
        "Returns the persisted trust payload for a story id. This is the canonical product-facing "
        "story trust endpoint and is also exposed via `/stories/{story_id}` for connector compatibility."
    ),
    response_model=TrustPayloadResponse,
    responses=API_ERROR_RESPONSES,
)
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
    return payload


@app.post(
    "/api/v1/news/analyze",
    dependencies=[Depends(require_api_key)],
    tags=["trust"],
    summary="Analyze arbitrary text into a trust result",
    description="Scores a caller-provided headline or text fragment without fetching external articles.",
    response_model=NormalizedTrustResult,
    responses=API_ERROR_RESPONSES,
)
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
@app.get(
    "/stories/{story_id:path}",
    dependencies=[Depends(require_api_key)],
    tags=["trust"],
    summary="Compatibility alias for story trust payloads",
    description="Connector-compatible alias for `/api/v1/news/trust/{story_id}`.",
    response_model=TrustPayloadResponse,
    responses=API_ERROR_RESPONSES,
)
async def stories_compat(story_id: str) -> dict[str, Any]:
    """Compatibility endpoint for tollama's HttpNewsConnector."""
    return await get_trust(story_id)


__all__ = ["app", "init_agent"]
