"""GDELT 2.0 connector — fetches articles via the DOC API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx

from connectors.http_utils import fetch_with_retry

logger = logging.getLogger(__name__)


class GDELTConnector:
    """Async connector for GDELT 2.0 DOC API."""

    provider_name = "gdelt"

    def __init__(
        self,
        base_url: str = "https://api.gdeltproject.org/api/v2",
        timeout: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def fetch_articles(
        self,
        *,
        query: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch articles from GDELT DOC API."""
        request_params: dict[str, Any] = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(min(limit, 250)),
            "format": "json",
        }
        if from_date is not None:
            request_params["startdatetime"] = from_date.strftime("%Y%m%d%H%M%S")
        if to_date is not None:
            request_params["enddatetime"] = to_date.strftime("%Y%m%d%H%M%S")
        if params:
            request_params.update(params)

        logger.info("Fetching from GDELT: query='%s'", query)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await fetch_with_retry(
                client,
                f"{self._base_url}/doc/doc",
                params=request_params,
            )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                logger.error("Invalid JSON response from GDELT for query '%s'", query)
                return []

        articles = [_normalize_gdelt_article(a) for a in data.get("articles", [])[:limit]]
        logger.info("Fetched %d articles from GDELT", len(articles))
        return articles


def _normalize_gdelt_article(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a GDELT article to a flat dict."""
    return {
        "article_id": raw.get("url", ""),
        "source_name": raw.get("domain", raw.get("source", "unknown")),
        "source_url": raw.get("url", ""),
        "headline": raw.get("title", ""),
        "body": raw.get("seendate", ""),
        "author": None,
        "published_at": raw.get("seendate", ""),
        "provider": "gdelt",
        "language": raw.get("language", "English"),
        "tone": raw.get("tone", 0.0),
        "socialimage": raw.get("socialimage", ""),
    }


__all__ = ["GDELTConnector"]
