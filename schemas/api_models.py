"""API-facing schema models for typed response payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.signals import NewsSignal


class HealthPayload(BaseModel):
    """Lightweight liveness payload for product and infrastructure probes."""

    status: Literal["ok"] = Field(default="ok", examples=["ok"])
    service: Literal["news-agent"] = Field(default="news-agent", examples=["news-agent"])


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
    source: Literal["persisted"] = Field(default="persisted", examples=["persisted"])


class TrustComponent(BaseModel):
    """One weighted component contributing to the normalized trust score."""

    model_config = ConfigDict(extra="allow")

    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)


class TrustEvidence(BaseModel):
    """Evidence summary associated with a trust result."""

    model_config = ConfigDict(extra="allow")

    source_type: str
    source_ids: list[str] = Field(default_factory=list)
    freshness_seconds: float | None = Field(default=None, ge=0.0)


class TrustAudit(BaseModel):
    """Audit metadata for a generated trust result."""

    model_config = ConfigDict(extra="allow")

    formula_version: str
    generated_at: str
    agent_version: str


class TrustViolation(BaseModel):
    """Validation or policy violation flagged during trust scoring."""

    model_config = ConfigDict(extra="allow")

    name: str
    severity: str


class NormalizedTrustResult(BaseModel):
    """Product-facing normalized trust result returned by live/analyze endpoints."""

    model_config = ConfigDict(extra="allow")

    agent_name: str
    domain: str
    trust_score: float = Field(ge=0.0, le=1.0)
    risk_category: str
    calibration_status: str
    component_breakdown: dict[str, TrustComponent]
    violations: list[TrustViolation] = Field(default_factory=list)
    why_trusted: str
    evidence: TrustEvidence
    audit: TrustAudit


class TrustPayloadResponse(BaseModel):
    """Normalized trust payload shape returned for a persisted story."""

    model_config = ConfigDict(extra="allow")

    story_id: str = Field(min_length=1)
    source_credibility: float | None = Field(default=None, ge=0.0, le=1.0)
    corroboration: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_score: float | None = Field(default=None, ge=0.0, le=1.0)
    propagation_delay_seconds: float | None = Field(default=None, ge=0.0)
    freshness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    novelty: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_category: str | None = None
    calibration_status: str | None = None
    components: dict[str, float] | None = None


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""

    text: str = Field(description="Freeform text or headline to score", examples=["Federal Reserve holds rates steady"])
    query: str = Field(default="", description="Optional user/search query context", examples=["fed rates"])


class ErrorDetail(BaseModel):
    """Structured error detail row, especially for validation failures."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    loc: list[str | int] | None = None
    msg: str | None = None
    input: Any | None = None
    ctx: dict[str, Any] | None = None
    url: str | None = None


class ErrorBody(BaseModel):
    """Normalized error payload returned by API routes."""

    code: str = Field(description="Stable machine-readable error code", examples=["validation_error"])
    message: str = Field(description="Human-readable error message")
    details: list[ErrorDetail] | None = Field(default=None, description="Optional validation details")


class ErrorEnvelope(BaseModel):
    """Top-level error envelope."""

    error: ErrorBody


class LiveSignalResponse(BaseModel):
    """Live signal analysis returned by GET /api/v1/news/signals."""

    signal: NewsSignal
    trust: NormalizedTrustResult
    source: Literal["live"] = Field(default="live", examples=["live"])


__all__ = [
    "AnalyzeRequest",
    "ClusterSummary",
    "ClusterSummaryListResponse",
    "ErrorBody",
    "ErrorDetail",
    "ErrorEnvelope",
    "HealthPayload",
    "LiveSignalResponse",
    "NormalizedTrustResult",
    "PersistedSignalPage",
    "PersistedSignalRow",
    "ReadinessPayload",
    "StorySummary",
    "StorySummaryListResponse",
    "TrustAudit",
    "TrustComponent",
    "TrustEvidence",
    "TrustPayloadResponse",
    "TrustViolation",
]
