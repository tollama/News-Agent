"""NewsAPI.org connector — fetches articles via the /everything endpoint."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx

from connectors.http_utils import fetch_with_retry

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 900  # 15 minutes


class NewsAPIConnector:
    """Async connector for NewsAPI.org REST API."""

    provider_name = "newsapi"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://newsapi.org/v2",
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    async def fetch_articles(
        self,
        *,
        query: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch articles matching the query from NewsAPI /everything endpoint."""
        request_params: dict[str, Any] = {
            "q": query,
            "pageSize": min(limit, 100),
            "sortBy": "publishedAt",
            "language": "en",
        }
        if from_date is not None:
            request_params["from"] = from_date.strftime("%Y-%m-%dT%H:%M:%S")
        if to_date is not None:
            request_params["to"] = to_date.strftime("%Y-%m-%dT%H:%M:%S")
        if params:
            request_params.update(params)

        # Check cache
        cache_key = f"{query}|{from_date}|{to_date}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            ts, articles = cached
            if time.monotonic() - ts < _CACHE_TTL_SECONDS:
                logger.info("Cache hit for query '%s' (%d articles)", query, len(articles))
                return articles[:limit]

        headers = {"X-Api-Key": self._api_key}
        logger.info("Fetching from NewsAPI: query='%s'", query)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await fetch_with_retry(
                client,
                f"{self._base_url}/everything",
                params=request_params,
                headers=headers,
            )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                logger.error("Invalid JSON response from NewsAPI for query '%s'", query)
                return []

        articles = [_normalize_article(a) for a in data.get("articles", [])[:limit]]
        logger.info("Fetched %d articles from NewsAPI", len(articles))

        # Store in cache
        self._cache[cache_key] = (time.monotonic(), articles)
        return articles


def _normalize_article(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw NewsAPI article to a flat dict."""
    source = raw.get("source", {})
    return {
        "article_id": raw.get("url", ""),
        "source_name": source.get("name", "unknown"),
        "source_url": raw.get("url", ""),
        "headline": raw.get("title", ""),
        "body": raw.get("description") or raw.get("content"),
        "author": raw.get("author"),
        "published_at": raw.get("publishedAt", ""),
        "provider": "newsapi",
    }


__all__ = ["NewsAPIConnector"]
