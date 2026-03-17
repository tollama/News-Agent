"""News trust score computation aligned with NewsTrustPayload."""

from __future__ import annotations

from typing import Any

from schemas.signals import NewsSignal


# Component weights (sum to 1.0)
_DEFAULT_WEIGHTS = {
    "source_credibility": 0.30,
    "corroboration": 0.25,
    "freshness": 0.20,
    "novelty": 0.15,
    "contradiction_penalty": 0.10,
}


def compute_news_trust(
    signal: NewsSignal,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute composite news trust score from a NewsSignal.

    Returns dict with trust_score and component breakdown compatible
    with NormalizedTrustResult.
    """
    w = weights or _DEFAULT_WEIGHTS

    # Contradiction is inverted: high contradiction = low trust
    contradiction_component = max(0.0, 1.0 - signal.contradiction_score)

    components = {
        "source_credibility": signal.source_credibility,
        "corroboration": signal.corroboration,
        "freshness": signal.freshness_score,
        "novelty": signal.novelty,
        "contradiction_penalty": contradiction_component,
    }

    trust_score = sum(
        components[name] * w.get(name, 0.0) for name in components
    )
    trust_score = max(0.0, min(1.0, trust_score))

    # Risk category
    if trust_score >= 0.75:
        risk_category = "GREEN"
    elif trust_score >= 0.50:
        risk_category = "YELLOW"
    else:
        risk_category = "RED"

    return {
        "trust_score": trust_score,
        "risk_category": risk_category,
        "components": components,
        "weights": w,
    }


__all__ = ["compute_news_trust"]
