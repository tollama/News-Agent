"""Provider-aware normalizer dispatch for article snapshots."""

from __future__ import annotations

from typing import Any

from schemas.article import ArticleSnapshot


def normalize_article(raw: dict[str, Any]) -> ArticleSnapshot:
    """Dispatch to the correct normalizer based on the article's provider field."""
    provider = raw.get("provider", "newsapi")

    if provider == "gdelt":
        from connectors.gdelt_normalizer import normalize_to_snapshot

        return normalize_to_snapshot(raw)

    if provider == "rss":
        from connectors.rss_normalizer import normalize_to_snapshot

        return normalize_to_snapshot(raw)

    # Default: newsapi (backward compat)
    from connectors.newsapi_normalizer import normalize_to_snapshot

    return normalize_to_snapshot(raw)


__all__ = ["normalize_article"]
