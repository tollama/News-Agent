"""API-facing schema models for typed response payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.signals import NewsSignal


class PersistedSignalRow(BaseModel):
    """Consumer-facing row returned from persisted signal reads."""

    model_config = ConfigDict(extra="allow")

    story_id: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    source_name: str | None = None
    published_at: str | None = None
    analyzed_at: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    entities: list[str] = Field(default_factory=list)
    source_credibility: float | None = Field(default=None, ge=0.0, le=1.0)
    corroboration: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_score: float | None = Field(default=None, ge=0.0, le=1.0)
    propagation_delay_seconds: float | None = Field(default=None, ge=0.0)
    freshness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty: float | None = Field(default=None, ge=0.0, le=1.0)
    article_count: int | None = Field(default=None, ge=0)
    query: str = Field(default="")


class ReadinessPayload(BaseModel):
    """Readiness and storage observability payload."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(description="Overall readiness state", examples=["ok", "degraded"])
    service: str = Field(description="Service identifier", examples=["news-agent"])
    ready: bool = Field(description="Whether the in-memory agent is initialized")
    data_dir: str = Field(description="Base data directory used for persisted artifacts")
    data_dir_exists: bool = Field(description="Whether the data directory currently exists")
    data_dir_writable: bool = Field(description="Whether the data directory can be written to")
    sqlite_index_path: str = Field(description="Path to the SQLite sidecar index file")
    sqlite_index_exists: bool = Field(description="Whether the SQLite sidecar index file exists")


class StorySummary(BaseModel):
    """Consumer-facing summary row for a persisted story."""

    model_config = ConfigDict(extra="allow")

    story_id: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    query: str = Field(default="")
    source_name: str = Field(min_length=1)
    published_at: str
    analyzed_at: str
    article_count: int = Field(ge=0)
    entities: list[str] = Field(default_factory=list)
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_category: str | None = None
    calibration_status: str | None = None


class StorySummaryListResponse(BaseModel):
    """Recent story summaries response."""

    stories: list[StorySummary]
    count: int


class ClusterSummary(BaseModel):
    """Consumer-facing summary row for a persisted story cluster."""

    model_config = ConfigDict(extra="allow")

    cluster_id: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    query: str = Field(default="")
    story_ids: list[str] = Field(default_factory=list)
    story_count: int = Field(ge=0)
    total_article_count: int = Field(ge=0)
    source_names: list[str] = Field(default_factory=list)
    top_entities: list[str] = Field(default_factory=list)
    latest_published_at: str
    latest_analyzed_at: str
    avg_trust_score: float = Field(ge=0.0, le=1.0)
    max_trust_score: float = Field(ge=0.0, le=1.0)
    risk_category: str | None = None
    calibration_status: str | None = None


class ClusterSummaryListResponse(BaseModel):
    """Recent cluster summaries response."""

    clusters: list[ClusterSummary]
    count: int


class PersistedSignalPage(BaseModel):
    """Persisted signals page returned by GET /api/v1/news/signals?persisted=true."""

    signals: list[PersistedSignalRow]
    count: int
    has_more: bool
    next_cursor: str | None = None
    source: str = Field(default="persisted", examples=["persisted"])


class LiveSignalResponse(BaseModel):
    """Live signal analysis returned by GET /api/v1/news/signals."""

    signal: NewsSignal
    trust: dict[str, Any]
    source: str = Field(default="live", examples=["live"])


__all__ = [
    "ClusterSummary",
    "ClusterSummaryListResponse",
    "LiveSignalResponse",
    "PersistedSignalPage",
    "PersistedSignalRow",
    "ReadinessPayload",
    "StorySummary",
    "StorySummaryListResponse",
]
