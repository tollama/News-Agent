"""Tests for features.nlp.sentiment."""

from features.nlp.sentiment import compute_sentiment, compute_sentiment_label


def test_positive_sentiment():
    score = compute_sentiment("This is great news! Wonderful achievement.")
    assert score > 0.0


def test_negative_sentiment():
    score = compute_sentiment("Terrible disaster, catastrophic failure.")
    assert score < 0.0


def test_neutral_sentiment():
    score = compute_sentiment("The meeting is scheduled for Tuesday.")
    assert -0.3 < score < 0.3


def test_empty_text():
    assert compute_sentiment("") == 0.0


def test_sentiment_label_positive():
    assert compute_sentiment_label(0.5) == "positive"


def test_sentiment_label_negative():
    assert compute_sentiment_label(-0.5) == "negative"


def test_sentiment_label_neutral():
    assert compute_sentiment_label(0.0) == "neutral"
