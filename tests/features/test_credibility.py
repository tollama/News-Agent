"""Tests for features.nlp.credibility."""

from __future__ import annotations

from pathlib import Path

from features.nlp.credibility import (
    get_credibility_score,
    get_credibility_tier,
    reload_credibility_registry,
)


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


def test_registry_can_be_overridden_from_yaml(tmp_path, monkeypatch):
    config_path = Path(tmp_path) / "credibility.yaml"
    config_path.write_text(
        "default_score: 0.22\n"
        "scores:\n"
        "  1: 0.99\n"
        "tiers:\n"
        "  1:\n"
        "    - custom wire\n"
    )
    monkeypatch.setenv("NEWS_AGENT_CREDIBILITY_CONFIG", str(config_path))
    reload_credibility_registry()
    try:
        assert get_credibility_score("Custom Wire") == 0.99
        assert get_credibility_tier("Custom Wire") == 1
        assert get_credibility_score("Unlisted Outlet") == 0.22
    finally:
        monkeypatch.delenv("NEWS_AGENT_CREDIBILITY_CONFIG", raising=False)
        reload_credibility_registry()
