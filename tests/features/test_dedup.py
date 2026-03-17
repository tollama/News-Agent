"""Tests for features.nlp.dedup."""

from features.nlp.dedup import build_minhash, compute_novelty, find_duplicates


def test_build_minhash():
    mh = build_minhash("test headline for dedup")
    assert mh is not None


def test_find_duplicates_similar():
    articles = [
        {"headline": "Federal Reserve raises interest rates by 25 basis points"},
        {"headline": "Federal Reserve raises interest rates by 25 bps today"},
        {"headline": "New AI model released by tech startup"},
    ]
    clusters = find_duplicates(articles, threshold=0.3)
    # The first two should cluster together
    found_fed_cluster = any(0 in c and 1 in c for c in clusters)
    assert found_fed_cluster


def test_find_duplicates_no_dupes():
    articles = [
        {"headline": "Completely different topic A"},
        {"headline": "Entirely unrelated subject B"},
    ]
    clusters = find_duplicates(articles, threshold=0.8)
    assert len(clusters) == 0


def test_compute_novelty_unique():
    clusters: list[set[int]] = []
    assert compute_novelty(0, clusters) == 1.0


def test_compute_novelty_in_cluster():
    clusters = [{0, 1, 2}]
    assert compute_novelty(0, clusters) == pytest.approx(1 / 3)


# Need to import pytest for approx
import pytest  # noqa: E402
