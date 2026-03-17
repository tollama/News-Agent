"""News signal schema — processed output ready for trust pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NewsSignal(BaseModel):
    """Processed news signal with computed features for trust analysis."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    story_id: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    published_at: datetime
    analyzed_at: datetime

    # NLP features
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="VADER compound score")
    entities: list[str] = Field(default_factory=list)

    # Trust-relevant scores (0-1 scale)
    source_credibility: float = Field(ge=0.0, le=1.0)
    corroboration: float = Field(ge=0.0, le=1.0)
    contradiction_score: float = Field(ge=0.0, le=1.0)
    propagation_delay_seconds: float = Field(ge=0.0)
    freshness_score: float = Field(ge=0.0, le=1.0)
    novelty: float = Field(ge=0.0, le=1.0)

    # Metadata
    article_count: int = Field(ge=0, description="Number of related articles found")
    query: str = Field(default="")


__all__ = ["NewsSignal"]
