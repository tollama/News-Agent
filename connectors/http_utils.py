"""Shared HTTP utilities for news connectors."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_DEFAULT_MAX_RETRIES = 3


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retryable_status: frozenset[int] = _DEFAULT_RETRYABLE_STATUS,
) -> httpx.Response:
    """GET a URL with exponential-backoff retry on transient errors."""
    last_response: httpx.Response | None = None

    for attempt in range(max_retries):
        response = await client.get(url, params=params, headers=headers)
        last_response = response

        if response.status_code not in retryable_status:
            return response

        if attempt < max_retries - 1:
            wait = 2**attempt
            logger.warning(
                "Retryable status %d from %s (attempt %d/%d, waiting %ds)",
                response.status_code,
                url,
                attempt + 1,
                max_retries,
                wait,
            )
            await asyncio.sleep(wait)

    # All retries exhausted — return the last response for the caller to handle
    assert last_response is not None  # noqa: S101
    return last_response


__all__ = ["fetch_with_retry"]
