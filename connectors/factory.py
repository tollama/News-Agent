"""Factory functions for news connector instantiation."""

from __future__ import annotations

from typing import Any

from connectors.base import NewsDataConnector
from schemas.enums import NewsProvider


def create_news_connector(
    provider: NewsProvider,
    config: dict[str, Any],
) -> NewsDataConnector:
    """Create a news data connector for the given provider.

    Args:
        provider: The news provider to create a connector for.
        config: Provider-specific configuration dict.

    Returns:
        A connector satisfying the NewsDataConnector protocol.

    Raises:
        ValueError: If the provider is not supported.
    """
    if provider == NewsProvider.NEWSAPI:
        from connectors.newsapi import NewsAPIConnector

        return NewsAPIConnector(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://newsapi.org/v2"),
            timeout=config.get("timeout", 10.0),
        )
    if provider == NewsProvider.GDELT:
        from connectors.gdelt import GDELTConnector

        return GDELTConnector(
            base_url=config.get("base_url", "https://api.gdeltproject.org/api/v2"),
            timeout=config.get("timeout", 15.0),
        )
    if provider == NewsProvider.RSS:
        from connectors.rss import RSSConnector

        return RSSConnector(
            feed_urls=config.get("feed_urls", []),
            timeout=config.get("timeout", 10.0),
        )
    msg = f"Unsupported news provider: {provider}"
    raise ValueError(msg)


__all__ = ["create_news_connector"]
