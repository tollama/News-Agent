"""Source credibility scoring with tiered database."""

from __future__ import annotations

# Credibility tiers (0-1 scale)
# Tier 1: Wire services and major international outlets
_TIER_1: set[str] = {
    "associated press", "ap news", "reuters", "afp",
    "bbc news", "the new york times", "the washington post",
    "the wall street journal", "financial times", "the economist",
    "bloomberg", "cnbc",
}

# Tier 2: Major national and respected outlets
_TIER_2: set[str] = {
    "cnn", "nbc news", "abc news", "cbs news", "fox news",
    "the guardian", "politico", "npr", "pbs",
    "usa today", "los angeles times", "chicago tribune",
    "time", "newsweek", "forbes", "business insider",
    "techcrunch", "ars technica", "the verge",
    "nature", "science", "the lancet",
}

# Tier 3: Regional and specialized outlets
_TIER_3: set[str] = {
    "axios", "the hill", "vox", "vice",
    "mashable", "wired", "engadget",
    "marketwatch", "yahoo finance", "seeking alpha",
    "coindesk", "cointelegraph",
}

_TIER_SCORES = {
    1: 0.95,
    2: 0.80,
    3: 0.65,
}

_DEFAULT_SCORE = 0.40  # Unknown / blog / unranked sources


def get_credibility_score(source_name: str) -> float:
    """Return credibility score (0-1) for a source name."""
    name = source_name.strip().lower()
    if name in _TIER_1:
        return _TIER_SCORES[1]
    if name in _TIER_2:
        return _TIER_SCORES[2]
    if name in _TIER_3:
        return _TIER_SCORES[3]
    return _DEFAULT_SCORE


def get_credibility_tier(source_name: str) -> int:
    """Return credibility tier (1=highest, 4=unranked) for a source."""
    name = source_name.strip().lower()
    if name in _TIER_1:
        return 1
    if name in _TIER_2:
        return 2
    if name in _TIER_3:
        return 3
    return 4


__all__ = ["get_credibility_score", "get_credibility_tier"]
