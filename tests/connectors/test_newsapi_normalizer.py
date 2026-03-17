"""Tests for connectors.newsapi_normalizer."""

from connectors.newsapi_normalizer import infer_category, normalize_to_snapshot
from schemas.enums import NewsCategory, NewsProvider


def test_infer_category_business():
    assert infer_category("Stock market rally continues as earnings beat") == NewsCategory.BUSINESS


def test_infer_category_technology():
    assert infer_category("New AI software startup launches cloud platform") == NewsCategory.TECHNOLOGY


def test_infer_category_politics():
    assert infer_category("Senate votes on new election policy") == NewsCategory.POLITICS


def test_infer_category_general():
    assert infer_category("Something happened today") == NewsCategory.GENERAL


def test_normalize_to_snapshot(sample_newsapi_article):
    snap = normalize_to_snapshot(sample_newsapi_article)
    assert snap.article_id == "https://example.com/article/123"
    assert snap.source_name == "Reuters"
    assert snap.provider == NewsProvider.NEWSAPI
    assert snap.headline.startswith("Federal Reserve")
    assert snap.author == "Jane Reporter"
