"""Protocol definitions for news data connectors."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NewsDataConnector(Protocol):
    """Fetches articles from a news data provider (REST or similar)."""

    provider_name: str

    async def fetch_articles(
        self,
        *,
        query: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


@runtime_checkable
class NewsStreamConnector(Protocol):
    """Polls or streams articles in near-real-time."""

    provider_name: str

    async def poll_articles(
        self,
        *,
        query: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]: ...


__all__ = [
    "NewsDataConnector",
    "NewsStreamConnector",
]
