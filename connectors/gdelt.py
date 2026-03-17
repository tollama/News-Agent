"""GDELT 2.0 connector — fetches articles via the DOC API."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import httpx

_MAX_RETRIES = 3
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


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

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(_MAX_RETRIES):
                response = await client.get(
                    f"{self._base_url}/doc/doc",
                    params=request_params,
                )
                if response.status_code not in _RETRYABLE_STATUS:
                    break
                if attempt < _MAX_RETRIES - 1:
                    import asyncio

                    await asyncio.sleep(2**attempt)

            response.raise_for_status()
            data = response.json()

        articles = data.get("articles", [])
        return [_normalize_gdelt_article(a) for a in articles[:limit]]


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
