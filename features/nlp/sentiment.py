"""Sentiment analysis using VADER."""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer: SentimentIntensityAnalyzer | None = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def compute_sentiment(text: str) -> float:
    """Return VADER compound sentiment score in [-1, 1]."""
    if not text:
        return 0.0
    scores = _get_analyzer().polarity_scores(text)
    return float(scores["compound"])


def compute_sentiment_label(compound: float) -> str:
    """Map compound score to a label."""
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


__all__ = ["compute_sentiment", "compute_sentiment_label"]
