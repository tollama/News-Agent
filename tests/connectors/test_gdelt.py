"""Tests for connectors.gdelt."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from connectors.gdelt import GDELTConnector


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {"articles": []},
        request=httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc"),
    )
    return resp


@pytest.mark.asyncio()
async def test_fetch_articles_success():
    connector = GDELTConnector()
    with patch("connectors.gdelt.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _mock_response(
            json_data={
                "articles": [
                    {
                        "url": "https://example.com/gdelt/1",
                        "title": "GDELT article",
                        "domain": "example.com",
                        "seendate": "20250115140000",
                    },
                ]
            }
        )
        articles = await connector.fetch_articles(query="test")

    assert len(articles) == 1
    assert articles[0]["provider"] == "gdelt"
    assert articles[0]["source_name"] == "example.com"


@pytest.mark.asyncio()
async def test_fetch_articles_json_error():
    connector = GDELTConnector()
    resp = httpx.Response(
        status_code=200,
        content=b"not json",
        request=httpx.Request("GET", "https://api.gdeltproject.org/api/v2/doc/doc"),
    )
    with patch("connectors.gdelt.fetch_with_retry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = resp
        articles = await connector.fetch_articles(query="test")

    assert articles == []
