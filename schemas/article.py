"""Canonical article snapshot model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import NewsCategory, NewsProvider


class ArticleSnapshot(BaseModel):
    """Normalized article representation across all news providers."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ts: datetime = Field(description="Ingestion timestamp")
    article_id: str = Field(min_length=1, description="Provider-unique article identifier")
    source_name: str = Field(min_length=1, description="Publishing source name")
    source_url: str = Field(default="", description="URL of the article")
    headline: str = Field(min_length=1, description="Article headline / title")
    body: str | None = Field(default=None, description="Article body text (may be truncated)")
    category: NewsCategory = Field(default=NewsCategory.GENERAL)
    provider: NewsProvider = Field(description="Data provider that supplied this article")
    published_at: datetime = Field(description="Original publication timestamp")
    language: str = Field(default="en", min_length=2, max_length=5)
    author: str | None = Field(default=None)


__all__ = ["ArticleSnapshot"]
