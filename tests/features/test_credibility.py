"""Tests for features.nlp.credibility."""

from features.nlp.credibility import get_credibility_score, get_credibility_tier


def test_tier_1_source():
    assert get_credibility_score("Reuters") == 0.95
    assert get_credibility_score("Associated Press") == 0.95
    assert get_credibility_tier("Reuters") == 1


def test_tier_2_source():
    assert get_credibility_score("CNN") == 0.80
    assert get_credibility_tier("CNN") == 2


def test_tier_3_source():
    assert get_credibility_score("Axios") == 0.65
    assert get_credibility_tier("Axios") == 3


def test_unknown_source():
    assert get_credibility_score("random-blog.com") == 0.40
    assert get_credibility_tier("random-blog.com") == 4


def test_case_insensitive():
    assert get_credibility_score("REUTERS") == 0.95
    assert get_credibility_score("  Reuters  ") == 0.95
