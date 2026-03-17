"""Contract compliance tests — validates News-Agent output against tollama schemas.

These tests ensure the News-Agent's analyze() and to_trust_payload() outputs
are strictly compatible with tollama's NormalizedTrustResult, TrustComponent,
TrustEvidence, TrustAudit, and NewsTrustPayload contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime
import pytest

from agents.news_agent import NewsAgent
from schemas.signals import NewsSignal

# --- Canonical field requirements from tollama/xai/trust_contract.py ---

_NORMALIZED_RESULT_REQUIRED_KEYS = {
    "agent_name",
    "domain",
    "trust_score",
    "risk_category",
    "calibration_status",
    "component_breakdown",
    "violations",
    "why_trusted",
    "evidence",
    "audit",
}

_TRUST_COMPONENT_REQUIRED_KEYS = {"score", "weight"}

_TRUST_EVIDENCE_REQUIRED_KEYS = {"source_type", "source_ids", "freshness_seconds"}

_TRUST_AUDIT_REQUIRED_KEYS = {"formula_version", "generated_at", "agent_version"}

_NEWS_TRUST_PAYLOAD_REQUIRED_KEYS = {
    "story_id",
    "source_credibility",
    "corroboration",
    "contradiction_score",
    "propagation_delay_seconds",
    "freshness_score",
    "novelty",
}

_VALID_RISK_CATEGORIES = {"GREEN", "YELLOW", "RED"}

_VALID_CALIBRATION_STATUSES = {
    "well_calibrated",
    "moderately_calibrated",
    "poorly_calibrated",
}


@pytest.fixture()
def agent() -> NewsAgent:
    return NewsAgent()


@pytest.fixture()
def sample_signal() -> NewsSignal:
    return NewsSignal(
        story_id="test-story-001",
        headline="Test headline",
        source_name="reuters",
        published_at=datetime(2025, 6, 15, 12, 0, tzinfo=UTC),
        analyzed_at=datetime(2025, 6, 15, 12, 5, tzinfo=UTC),
        sentiment_score=0.3,
        entities=["AAPL", "Fed"],
        source_credibility=0.85,
        corroboration=0.7,
        contradiction_score=0.15,
        propagation_delay_seconds=120.0,
        freshness_score=0.9,
        novelty=0.6,
        article_count=5,
        query="Federal Reserve interest rate",
    )


@pytest.fixture()
def high_trust_signal() -> NewsSignal:
    return NewsSignal(
        story_id="high-trust",
        headline="Confirmed event",
        source_name="AP",
        published_at=datetime(2025, 6, 15, 12, 0, tzinfo=UTC),
        analyzed_at=datetime(2025, 6, 15, 12, 1, tzinfo=UTC),
        sentiment_score=0.5,
        entities=[],
        source_credibility=0.95,
        corroboration=0.9,
        contradiction_score=0.05,
        propagation_delay_seconds=60.0,
        freshness_score=0.95,
        novelty=0.5,
        article_count=10,
        query="test",
    )


@pytest.fixture()
def low_trust_signal() -> NewsSignal:
    return NewsSignal(
        story_id="low-trust",
        headline="Dubious claim",
        source_name="unknown-blog",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        analyzed_at=datetime(2025, 6, 15, tzinfo=UTC),
        sentiment_score=-0.8,
        entities=[],
        source_credibility=0.1,
        corroboration=0.1,
        contradiction_score=0.9,
        propagation_delay_seconds=86400.0,
        freshness_score=0.05,
        novelty=0.1,
        article_count=1,
        query="test",
    )


# === NormalizedTrustResult structure ===


class TestNormalizedTrustResultStructure:
    """Validate analyze() output matches NormalizedTrustResult schema."""

    def test_all_required_keys_present(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert _NORMALIZED_RESULT_REQUIRED_KEYS.issubset(result.keys())

    def test_agent_name_and_domain(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert result["agent_name"] == "news_agent"
        assert result["domain"] == "news"

    def test_trust_score_bounded(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert 0.0 <= result["trust_score"] <= 1.0

    def test_risk_category_valid(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert result["risk_category"] in _VALID_RISK_CATEGORIES

    def test_calibration_status_valid(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert result["calibration_status"] in _VALID_CALIBRATION_STATUSES

    def test_calibration_status_consistency(self, agent: NewsAgent):
        """calibration_status must align with trust_score thresholds."""
        # High trust
        high_payload = {
            "source_credibility": 0.95,
            "corroboration": 0.9,
            "freshness_score": 0.95,
            "novelty": 0.8,
            "contradiction_score": 0.05,
        }
        result = agent.analyze(high_payload)
        if result["trust_score"] >= 0.75:
            assert result["calibration_status"] == "well_calibrated"

        # Low trust
        low_payload = {
            "source_credibility": 0.1,
            "corroboration": 0.1,
            "freshness_score": 0.1,
            "novelty": 0.1,
            "contradiction_score": 0.9,
        }
        result = agent.analyze(low_payload)
        if result["trust_score"] < 0.50:
            assert result["calibration_status"] == "poorly_calibrated"


# === Component Breakdown ===


class TestComponentBreakdown:
    """Validate component_breakdown matches TrustComponent schema."""

    def test_components_have_required_keys(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        for name, component in result["component_breakdown"].items():
            assert _TRUST_COMPONENT_REQUIRED_KEYS.issubset(component.keys()), (
                f"Component '{name}' missing keys: "
                f"{_TRUST_COMPONENT_REQUIRED_KEYS - component.keys()}"
            )

    def test_component_scores_bounded(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        for name, component in result["component_breakdown"].items():
            assert 0.0 <= component["score"] <= 1.0, (
                f"Component '{name}' score {component['score']} out of [0,1]"
            )

    def test_component_weights_positive(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        for name, component in result["component_breakdown"].items():
            assert component["weight"] >= 0.0, (
                f"Component '{name}' weight {component['weight']} is negative"
            )

    def test_expected_component_names(self, agent: NewsAgent, sample_signal: NewsSignal):
        """Validate known component names for schema drift detection."""
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        expected = {
            "source_credibility",
            "corroboration",
            "freshness",
            "novelty",
            "contradiction_penalty",
        }
        actual = set(result["component_breakdown"].keys())
        assert actual == expected, f"Component name drift: expected {expected}, got {actual}"


# === Evidence ===


class TestEvidence:
    """Validate evidence matches TrustEvidence schema."""

    def test_evidence_required_keys(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert _TRUST_EVIDENCE_REQUIRED_KEYS.issubset(result["evidence"].keys())

    def test_evidence_source_type(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert result["evidence"]["source_type"] == "news_feed"

    def test_evidence_source_ids_nonempty(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert len(result["evidence"]["source_ids"]) > 0

    def test_evidence_freshness_seconds_type(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        fs = result["evidence"]["freshness_seconds"]
        assert fs is None or (isinstance(fs, (int, float)) and fs >= 0)


# === Audit ===


class TestAudit:
    """Validate audit matches TrustAudit schema."""

    def test_audit_required_keys(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert _TRUST_AUDIT_REQUIRED_KEYS.issubset(result["audit"].keys())

    def test_audit_generated_at_iso(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        # Should parse as ISO datetime
        datetime.fromisoformat(result["audit"]["generated_at"])


# === Violations ===


class TestViolations:
    """Validate violations list format and detection logic."""

    def test_violations_is_list(self, agent: NewsAgent, sample_signal: NewsSignal):
        result = agent.analyze(sample_signal.model_dump(mode="json"))
        assert isinstance(result["violations"], list)

    def test_violation_structure(self, agent: NewsAgent, low_trust_signal: NewsSignal):
        result = agent.analyze(low_trust_signal.model_dump(mode="json"))
        for v in result["violations"]:
            assert "name" in v
            assert "severity" in v

    def test_low_trust_triggers_violation(self, agent: NewsAgent, low_trust_signal: NewsSignal):
        result = agent.analyze(low_trust_signal.model_dump(mode="json"))
        # Low trust signal should trigger at least stale_data or high_contradiction
        assert len(result["violations"]) > 0

    def test_high_trust_no_critical_violations(
        self, agent: NewsAgent, high_trust_signal: NewsSignal
    ):
        result = agent.analyze(high_trust_signal.model_dump(mode="json"))
        critical = [v for v in result["violations"] if v["severity"] == "critical"]
        assert len(critical) == 0


# === NewsTrustPayload compatibility ===


class TestNewsTrustPayload:
    """Validate to_trust_payload() output matches NewsTrustPayload schema."""

    def test_all_required_keys(self, agent: NewsAgent, sample_signal: NewsSignal):
        payload = agent.to_trust_payload(sample_signal)
        assert _NEWS_TRUST_PAYLOAD_REQUIRED_KEYS.issubset(payload.keys())

    def test_score_ranges(self, agent: NewsAgent, sample_signal: NewsSignal):
        payload = agent.to_trust_payload(sample_signal)
        for key in ("source_credibility", "corroboration", "freshness_score"):
            assert 0.0 <= payload[key] <= 1.0, f"{key} = {payload[key]} out of [0,1]"

    def test_contradiction_score_range(self, agent: NewsAgent, sample_signal: NewsSignal):
        payload = agent.to_trust_payload(sample_signal)
        assert 0.0 <= payload["contradiction_score"] <= 1.0

    def test_propagation_delay_nonnegative(self, agent: NewsAgent, sample_signal: NewsSignal):
        payload = agent.to_trust_payload(sample_signal)
        assert payload["propagation_delay_seconds"] >= 0.0

    def test_story_id_nonempty(self, agent: NewsAgent, sample_signal: NewsSignal):
        payload = agent.to_trust_payload(sample_signal)
        assert len(payload["story_id"]) > 0
