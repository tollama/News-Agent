"""Enumerations for the News Agent domain."""

from __future__ import annotations

from enum import StrEnum


class NewsProvider(StrEnum):
    NEWSAPI = "newsapi"
    GDELT = "gdelt"
    RSS = "rss"


class NewsCategory(StrEnum):
    BUSINESS = "business"
    TECHNOLOGY = "technology"
    POLITICS = "politics"
    SCIENCE = "science"
    HEALTH = "health"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    TICKER = "ticker"
    EVENT = "event"


__all__ = [
    "EntityType",
    "NewsCategory",
    "NewsProvider",
    "SentimentLabel",
]
