"""FastAPI routes for the News Agent service."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from agents.news_agent import NewsAgent

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


@app.get("/api/v1/news/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "news-agent"}


@app.get("/api/v1/news/signals")
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


@app.get("/api/v1/news/trust/{story_id}")
async def get_trust(story_id: str) -> dict[str, Any]:
    """Get trust payload for a specific story.

    This endpoint is consumed by tollama's HttpNewsConnector
    at GET /stories/{story_id}.
    """
    agent = get_agent()
    # For now, return a basic analysis of the story_id
    result = agent.analyze({"story_id": story_id, "headline": story_id})
    payload = {
        "story_id": story_id,
        "source_credibility": result["component_breakdown"].get(
            "source_credibility", {}
        ).get("score", 0.5),
        "corroboration": result["component_breakdown"].get(
            "corroboration", {}
        ).get("score", 0.5),
        "contradiction_score": result["component_breakdown"].get(
            "contradiction_penalty", {}
        ).get("score", 0.2),
        "propagation_delay_seconds": 300.0,
        "freshness_score": result["component_breakdown"].get(
            "freshness", {}
        ).get("score", 0.5),
        "novelty": result["component_breakdown"].get(
            "novelty", {}
        ).get("score", 0.5),
    }
    return payload


@app.post("/api/v1/news/analyze")
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
@app.get("/stories/{story_id}")
async def stories_compat(story_id: str) -> dict[str, Any]:
    """Compatibility endpoint for tollama's HttpNewsConnector."""
    return await get_trust(story_id)


__all__ = ["app", "init_agent"]
