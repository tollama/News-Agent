"""Tests for calibration.freshness."""

from datetime import UTC, datetime, timedelta

import pytest

from calibration.freshness import freshness_score


def test_just_published():
    now = datetime.now(UTC)
    score = freshness_score(now, now)
    assert score == pytest.approx(1.0)


def test_half_life():
    now = datetime.now(UTC)
    pub = now - timedelta(hours=6)
    score = freshness_score(pub, now, half_life_hours=6.0)
    assert score == pytest.approx(0.5, abs=0.05)


def test_old_article():
    now = datetime.now(UTC)
    pub = now - timedelta(hours=48)
    score = freshness_score(pub, now, half_life_hours=6.0)
    assert score < 0.01


def test_future_article():
    now = datetime.now(UTC)
    pub = now + timedelta(hours=1)
    # Future article should score 1.0 (age clamped to 0)
    score = freshness_score(pub, now)
    assert score == pytest.approx(1.0)
