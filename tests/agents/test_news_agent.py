"""Tests for agents.news_agent."""

from agents.news_agent import NewsAgent


def test_agent_attributes():
    agent = NewsAgent()
    assert agent.agent_name == "news_agent"
    assert agent.domain == "news"
    assert agent.priority == 50


def test_supports_news_domain():
    agent = NewsAgent()
    assert agent.supports({"domain": "news"}) is True
    assert agent.supports({"domain": "financial_market"}) is False


def test_analyze_with_signal_data(sample_news_signal_data):
    agent = NewsAgent()
    result = agent.analyze(sample_news_signal_data)

    assert result["agent_name"] == "news_agent"
    assert result["domain"] == "news"
    assert 0.0 <= result["trust_score"] <= 1.0
    assert result["risk_category"] in ("GREEN", "YELLOW", "RED")
    assert "component_breakdown" in result
    assert "evidence" in result
    assert "audit" in result


def test_analyze_with_minimal_payload():
    agent = NewsAgent()
    result = agent.analyze({
        "headline": "Test article headline",
        "source_name": "Reuters",
    })
    assert result["agent_name"] == "news_agent"
    assert 0.0 <= result["trust_score"] <= 1.0


def test_to_trust_payload(sample_news_signal_data):
    from schemas.signals import NewsSignal

    agent = NewsAgent()
    signal = NewsSignal(**sample_news_signal_data)
    payload = agent.to_trust_payload(signal)

    # Should match NewsTrustPayload fields
    assert "story_id" in payload
    assert "source_credibility" in payload
    assert "corroboration" in payload
    assert "contradiction_score" in payload
    assert "propagation_delay_seconds" in payload
    assert "freshness_score" in payload
    assert "novelty" in payload


def test_empty_signal():
    agent = NewsAgent()
    signal = agent._empty_signal("test query")
    assert signal.article_count == 0
    assert signal.source_credibility == 0.0
    assert signal.story_id == "empty:test query"
