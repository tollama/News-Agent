"""NewsAPI.org connector — fetches articles via the /everything endpoint."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx


_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_MAX_RETRIES = 3


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

        headers = {"X-Api-Key": self._api_key}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(_MAX_RETRIES):
                response = await client.get(
                    f"{self._base_url}/everything",
                    params=request_params,
                    headers=headers,
                )
                if response.status_code not in _RETRYABLE_STATUS:
                    break
                if attempt < _MAX_RETRIES - 1:
                    import asyncio

                    await asyncio.sleep(2**attempt)

            response.raise_for_status()
            data = response.json()

        articles = data.get("articles", [])
        return [_normalize_article(a) for a in articles[:limit]]


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
