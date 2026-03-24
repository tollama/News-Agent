"""Source credibility scoring backed by a configurable registry."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path("configs/source_credibility.yaml")
_FALLBACK_TIER_SCORES = {
    1: 0.95,
    2: 0.80,
    3: 0.65,
}
_FALLBACK_DEFAULT_SCORE = 0.40
_FALLBACK_TIERS: dict[int, set[str]] = {
    1: {
        "associated press", "ap news", "reuters", "afp",
        "bbc news", "the new york times", "the washington post",
        "the wall street journal", "financial times", "the economist",
        "bloomberg", "cnbc",
    },
    2: {
        "cnn", "nbc news", "abc news", "cbs news", "fox news",
        "the guardian", "politico", "npr", "pbs",
        "usa today", "los angeles times", "chicago tribune",
        "time", "newsweek", "forbes", "business insider",
        "techcrunch", "ars technica", "the verge",
        "nature", "science", "the lancet",
    },
    3: {
        "axios", "the hill", "vox", "vice",
        "mashable", "wired", "engadget",
        "marketwatch", "yahoo finance", "seeking alpha",
        "coindesk", "cointelegraph",
    },
}


def _normalize_name(source_name: str) -> str:
    return source_name.strip().lower()


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    path = Path(os.environ.get("NEWS_AGENT_CREDIBILITY_CONFIG", _DEFAULT_CONFIG_PATH))
    data: dict[str, Any] = {}
    if path.exists():
        with path.open() as f:
            loaded = yaml.safe_load(f) or {}
            if isinstance(loaded, dict):
                data = loaded

    raw_scores = data.get("scores", {})
    tier_scores = {
        int(tier): float(raw_scores.get(str(tier), raw_scores.get(tier, fallback)))
        for tier, fallback in _FALLBACK_TIER_SCORES.items()
    }
    default_score = float(data.get("default_score", _FALLBACK_DEFAULT_SCORE))

    raw_tiers = data.get("tiers", {})
    tiers: dict[int, set[str]] = {}
    for tier, fallback_sources in _FALLBACK_TIERS.items():
        configured = raw_tiers.get(str(tier), raw_tiers.get(tier, list(fallback_sources)))
        if not isinstance(configured, list):
            configured = list(fallback_sources)
        tiers[tier] = {_normalize_name(str(name)) for name in configured if str(name).strip()}

    return {
        "tier_scores": tier_scores,
        "default_score": default_score,
        "tiers": tiers,
    }


def get_credibility_score(source_name: str) -> float:
    """Return credibility score (0-1) for a source name."""
    registry = _load_registry()
    tier = get_credibility_tier(source_name)
    if tier == 4:
        return registry["default_score"]
    return registry["tier_scores"][tier]


def get_credibility_tier(source_name: str) -> int:
    """Return credibility tier (1=highest, 4=unranked) for a source."""
    name = _normalize_name(source_name)
    registry = _load_registry()
    for tier, names in registry["tiers"].items():
        if name in names:
            return tier
    return 4


def reload_credibility_registry() -> None:
    """Clear the cached registry so tests or runtime config changes can reload it."""
    _load_registry.cache_clear()


__all__ = ["get_credibility_score", "get_credibility_tier", "reload_credibility_registry"]
