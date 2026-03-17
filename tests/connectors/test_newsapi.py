"""Tests for connectors.newsapi."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from connectors.newsapi import NewsAPIConnector


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    """Create a mock httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {"articles": []},
        request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
    )
    return resp


def _mock_response_with_articles() -> httpx.Response:
    return _mock_response(
        json_data={
            "articles": [
                {
                    "source": {"name": "Reuters"},
                    "url": "https://example.com/1",
                    "title": "Test article",
                    "description": "Test body",
                    "author": "Author",
                    "publishedAt": "2025-01-15T14:00:00Z",
                },
            ]
        }
    )


@pytest.mark.asyncio()
async def test_fetch_articles_success():
    connector = NewsAPIConnector(api_key="test-key")
    with patch("connectors.newsapi.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _mock_response_with_articles()
        articles = await connector.fetch_articles(query="test")

    assert len(articles) == 1
    assert articles[0]["source_name"] == "Reuters"
    assert articles[0]["provider"] == "newsapi"


@pytest.mark.asyncio()
async def test_fetch_articles_empty():
    connector = NewsAPIConnector(api_key="test-key")
    with patch("connectors.newsapi.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _mock_response(json_data={"articles": []})
        articles = await connector.fetch_articles(query="test")

    assert articles == []


@pytest.mark.asyncio()
async def test_fetch_articles_json_error():
    connector = NewsAPIConnector(api_key="test-key")
    resp = httpx.Response(
        status_code=200,
        content=b"not json",
        request=httpx.Request("GET", "https://newsapi.org/v2/everything"),
    )
    with patch("connectors.newsapi.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = resp
        articles = await connector.fetch_articles(query="test")

    assert articles == []


@pytest.mark.asyncio()
async def test_cache_hit():
    connector = NewsAPIConnector(api_key="test-key")
    with patch("connectors.newsapi.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _mock_response_with_articles()
        # First call
        await connector.fetch_articles(query="cache-test")
        # Second call should use cache
        articles = await connector.fetch_articles(query="cache-test")

    assert mock_fetch.call_count == 1  # Only called once
    assert len(articles) == 1
