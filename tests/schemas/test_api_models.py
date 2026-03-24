"""Tests for schemas.api_models."""

from __future__ import annotations

from datetime import UTC, datetime

from agents.news_agent import NewsAgent
from schemas.api_models import ErrorEnvelope, LiveSignalResponse, NormalizedTrustResult, TrustPayloadResponse
from schemas.signals import NewsSignal


def _make_signal() -> NewsSignal:
    now = datetime.now(UTC)
    return NewsSignal(
        story_id="story-1",
        headline="Federal Reserve holds rates steady",
        source_name="Reuters",
        published_at=now,
        analyzed_at=now,
        sentiment_score=0.1,
        entities=["Federal Reserve"],
        source_credibility=0.9,
        corroboration=0.8,
        contradiction_score=0.1,
        propagation_delay_seconds=90.0,
        freshness_score=0.95,
        novelty=0.5,
        article_count=3,
        query="fed rates",
    )


def test_normalized_trust_result_accepts_agent_output():
    agent = NewsAgent()
    signal = _make_signal()

    result = agent.analyze(signal.model_dump(mode="json"))
    parsed = NormalizedTrustResult.model_validate(result)

    assert parsed.agent_name == "news_agent"
    assert parsed.evidence.source_type == "news_feed"
    assert parsed.component_breakdown["source_credibility"].weight >= 0.0


def test_live_signal_response_accepts_typed_trust_payload():
    agent = NewsAgent()
    signal = _make_signal()
    trust = agent.analyze(signal.model_dump(mode="json"))

    response = LiveSignalResponse.model_validate(
        {
            "signal": signal.model_dump(mode="json"),
            "trust": trust,
            "source": "live",
        }
    )

    assert response.source == "live"
    assert response.trust.trust_score >= 0.0


def test_trust_payload_response_accepts_story_payload():
    agent = NewsAgent()
    signal = _make_signal()

    payload = TrustPayloadResponse.model_validate(agent.to_trust_payload(signal))

    assert payload.story_id == signal.story_id
    assert payload.freshness_score == signal.freshness_score


def test_error_envelope_accepts_validation_error_details():
    envelope = ErrorEnvelope.model_validate(
        {
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": [
                    {
                        "type": "missing",
                        "loc": ["body", "text"],
                        "msg": "Field required",
                        "input": {"query": "fed"},
                    }
                ],
            }
        }
    )

    assert envelope.error.code == "validation_error"
    assert envelope.error.details is not None
    assert envelope.error.details[0].loc == ["body", "text"]
