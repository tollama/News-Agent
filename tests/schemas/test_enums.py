"""Tests for schemas.enums."""

from schemas.enums import EntityType, NewsCategory, NewsProvider, SentimentLabel


def test_news_provider_values():
    assert NewsProvider.NEWSAPI == "newsapi"
    assert NewsProvider.GDELT == "gdelt"
    assert NewsProvider.RSS == "rss"


def test_news_category_values():
    assert NewsCategory.BUSINESS == "business"
    assert NewsCategory.GENERAL == "general"


def test_sentiment_label_values():
    assert SentimentLabel.POSITIVE == "positive"
    assert SentimentLabel.NEGATIVE == "negative"
    assert SentimentLabel.NEUTRAL == "neutral"


def test_entity_type_values():
    assert EntityType.TICKER == "ticker"
    assert EntityType.PERSON == "person"
