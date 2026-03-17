"""Tests for calibration.corroboration."""

import pytest

from calibration.corroboration import corroboration_score, source_diversity_ratio


def test_no_sources():
    assert corroboration_score(0, 0) == 0.0


def test_single_source():
    score = corroboration_score(5, 1)
    assert 0.0 < score < 0.5


def test_high_corroboration():
    score = corroboration_score(10, 5, min_sources_for_high=3)
    assert score >= 0.7


def test_source_diversity_ratio_normal():
    ratio = source_diversity_ratio(3, 10)
    assert ratio == pytest.approx(0.3)


def test_source_diversity_ratio_all_unique():
    ratio = source_diversity_ratio(5, 5)
    assert ratio == pytest.approx(1.0)


def test_source_diversity_ratio_empty():
    assert source_diversity_ratio(0, 0) == 0.0
