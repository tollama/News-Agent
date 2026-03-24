"""NewsAgent — main orchestrating agent for the News Agent service.

Implements the TrustAgent protocol from tollama.xai.trust_contract
so it can be registered in the trust pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from calibration.corroboration import corroboration_score
from calibration.news_trust_score import compute_news_trust, resolve_trust_weights
from connectors.base import NewsDataConnector
from connectors.normalizer_registry import normalize_article
from features.build_features import build_news_features
from features.story_cluster import build_cluster_summary, choose_representative_index
from schemas.signals import NewsSignal

logger = __import__("logging").getLogger(__name__)


class NewsAgent:
    """Orchestrates news ingestion, feature extraction, and trust scoring.

    Satisfies the TrustAgent protocol:
        agent_name: str
        domain: str
        priority: int
        supports(context) -> bool
        analyze(payload) -> NormalizedTrustResult | dict
    """

    agent_name = "news_agent"
    domain = "news"
    priority = 50

    def __init__(
        self,
        connectors: list[NewsDataConnector] | None = None,
        trust_weights: dict[str, float] | None = None,
    ) -> None:
        self._connectors = connectors or []
        self._trust_weights = resolve_trust_weights(trust_weights)

    def supports(self, context: dict[str, Any]) -> bool:
        """Return True if this agent can handle the given context."""
        domain = context.get("domain", "")
        return domain == "news" or "news" in domain

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Analyze a pre-computed news signal or raw payload.

        Accepts either a NewsSignal-compatible dict or raw query parameters.
        Returns a NormalizedTrustResult-compatible dict.
        """
        # If payload already has trust-relevant fields, wrap as signal
        if "story_id" in payload and "source_credibility" in payload:
            signal = NewsSignal(**payload)
        else:
            # Build a minimal signal from payload
            signal = NewsSignal(
                story_id=payload.get("story_id", payload.get("headline", "unknown")),
                headline=payload.get("headline", "unknown"),
                source_name=payload.get("source_name", "unknown"),
                published_at=payload.get("published_at", datetime.now(UTC)),
                analyzed_at=datetime.now(UTC),
                sentiment_score=payload.get("sentiment_score", 0.0),
                entities=payload.get("entities", []),
                source_credibility=payload.get("source_credibility", 0.5),
                corroboration=payload.get("corroboration", 0.5),
                contradiction_score=payload.get("contradiction_score", 0.2),
                propagation_delay_seconds=payload.get("propagation_delay_seconds", 300.0),
                freshness_score=payload.get("freshness_score", 0.5),
                novelty=payload.get("novelty", 0.5),
                article_count=payload.get("article_count", 1),
                query=payload.get("query", ""),
            )

        trust_result = compute_news_trust(signal, weights=self._trust_weights)
        return self._to_normalized_result(signal, trust_result)

    async def process_query(
        self,
        query: str,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
    ) -> NewsSignal:
        """Fetch articles, compute features, and produce a NewsSignal."""
        query = query.strip()
        if not query:
            return self._empty_signal("")

        if from_date and to_date and from_date > to_date:
            logger.warning("from_date (%s) > to_date (%s), swapping", from_date, to_date)
            from_date, to_date = to_date, from_date

        # Collect articles from all connectors
        all_raw: list[dict[str, Any]] = []
        for connector in self._connectors:
            articles = await connector.fetch_articles(
                query=query,
                from_date=from_date,
                to_date=to_date,
                limit=limit,
            )
            all_raw.extend(articles)

        if not all_raw:
            return self._empty_signal(query)

        logger.info("Fetched %d articles from %d connector(s)", len(all_raw), len(self._connectors))

        # Normalize to snapshots (provider-aware dispatch)
        snapshots = [normalize_article(a) for a in all_raw]
        df = pd.DataFrame([s.model_dump() for s in snapshots])

        # Build features
        featured = build_news_features(df)

        # Aggregate into a single signal
        return self._aggregate_to_signal(featured, query)

    def to_trust_payload(self, signal: NewsSignal) -> dict[str, Any]:
        """Convert a NewsSignal to a NewsTrustPayload-compatible dict.

        Output is directly consumable by tollama's NewsTrustPayload model.
        """
        return {
            "story_id": signal.story_id,
            "source_credibility": signal.source_credibility,
            "corroboration": signal.corroboration,
            "contradiction_score": signal.contradiction_score,
            "propagation_delay_seconds": signal.propagation_delay_seconds,
            "freshness_score": signal.freshness_score,
            "novelty": signal.novelty,
        }

    @staticmethod
    def _derive_calibration_status(score: float) -> str:
        """Derive calibration status from trust score."""
        if score >= 0.75:
            return "well_calibrated"
        if score >= 0.50:
            return "moderately_calibrated"
        return "poorly_calibrated"

    @staticmethod
    def _detect_violations(
        trust_score: float,
        signal: NewsSignal,
    ) -> list[dict[str, str]]:
        """Detect trust violations from signal data."""
        violations: list[dict[str, str]] = []
        if trust_score < 0.3:
            violations.append({"name": "low_trust", "severity": "critical"})
        if signal.freshness_score < 0.3:
            violations.append({"name": "stale_data", "severity": "warning"})
        if signal.contradiction_score > 0.8:
            violations.append({"name": "high_contradiction", "severity": "warning"})
        if signal.source_credibility < 0.3:
            violations.append({"name": "low_source_credibility", "severity": "warning"})
        return violations

    def _to_normalized_result(
        self,
        signal: NewsSignal,
        trust_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a NormalizedTrustResult-compatible dict."""
        components = trust_result["components"]
        weights = trust_result["weights"]
        trust_score = trust_result["trust_score"]
        component_breakdown = {
            name: {"score": score, "weight": weights.get(name, 0.0)}
            for name, score in components.items()
        }
        return {
            "agent_name": self.agent_name,
            "domain": self.domain,
            "trust_score": trust_score,
            "risk_category": trust_result["risk_category"],
            "calibration_status": self._derive_calibration_status(trust_score),
            "component_breakdown": component_breakdown,
            "violations": self._detect_violations(trust_score, signal),
            "why_trusted": self._build_why_trusted(
                trust_score, component_breakdown, signal.article_count,
            ),
            "evidence": {
                "source_type": "news_feed",
                "source_ids": [signal.story_id],
                "freshness_seconds": signal.propagation_delay_seconds,
            },
            "audit": {
                "formula_version": "v1",
                "generated_at": datetime.now(UTC).isoformat(),
                "agent_version": "0.1.0",
            },
        }

    @staticmethod
    def _build_why_trusted(
        trust_score: float,
        component_breakdown: dict[str, dict[str, float]],
        article_count: int,
    ) -> str:
        """Build a human-readable trust explanation from component scores."""
        if not component_breakdown:
            return f"Trust score {trust_score:.2f} based on {article_count} article(s)."

        # Sort by weighted contribution (score * weight), descending
        ranked = sorted(
            component_breakdown.items(),
            key=lambda kv: kv[1].get("score", 0) * kv[1].get("weight", 0),
            reverse=True,
        )
        top_name, top = ranked[0]
        weak_name, weak = ranked[-1]
        return (
            f"Trust score {trust_score:.2f}: strongest factor is "
            f"{top_name} ({top['score']:.0%}), "
            f"weakest is {weak_name} ({weak['score']:.0%}), "
            f"based on {article_count} article(s)."
        )

    def _aggregate_to_signal(
        self,
        df: pd.DataFrame,
        query: str,
    ) -> NewsSignal:
        """Aggregate featured DataFrame into a single NewsSignal.

        Prefers the strongest multi-article story cluster when available instead
        of anchoring on a single highest-credibility article.
        """
        now = datetime.now(UTC)
        cluster_column = "story_cluster" if "story_cluster" in df.columns else None

        if cluster_column is not None:
            cluster_summaries = []
            for cluster_id, cluster_df in df.groupby(cluster_column, sort=False):
                summary = build_cluster_summary(df, cluster_df.index)
                summary["cluster_id"] = cluster_id
                cluster_summaries.append(summary)
            selected_cluster = max(cluster_summaries, key=lambda item: item["aggregate_score"])
            cluster_indices = selected_cluster["indices"]
            cluster_df = df.iloc[cluster_indices]
            representative_idx = choose_representative_index(df, cluster_indices)
            best = df.iloc[representative_idx]
        else:
            representative_idx = int(df["source_credibility"].idxmax())
            best = df.iloc[representative_idx]
            cluster_df = df

        all_entities: list[str] = []
        for ents in cluster_df["entities"]:
            if isinstance(ents, list):
                all_entities.extend(ents)
        unique_entities = sorted(set(all_entities))

        unique_sources = int(cluster_df["source_name"].nunique())
        total = len(cluster_df)

        return NewsSignal(
            story_id=str(best.get("article_id", query)),
            headline=str(best.get("headline", query)),
            source_name=str(best.get("source_name", "unknown")),
            published_at=best.get("published_at", now),
            analyzed_at=now,
            sentiment_score=float(cluster_df["sentiment_score"].mean()),
            entities=unique_entities[:50],
            source_credibility=float(cluster_df["source_credibility"].max()),
            corroboration=corroboration_score(total, unique_sources),
            contradiction_score=float(cluster_df["contradiction_score"].mean()),
            propagation_delay_seconds=float(cluster_df["propagation_delay_seconds"].mean()),
            freshness_score=float(cluster_df["freshness_score"].max()),
            novelty=float(cluster_df["novelty"].mean()),
            article_count=total,
            query=query,
        )

    def _empty_signal(self, query: str) -> NewsSignal:
        """Return a low-confidence signal when no articles are found."""
        now = datetime.now(UTC)
        return NewsSignal(
            story_id=f"empty:{query}",
            headline=query,
            source_name="none",
            published_at=now,
            analyzed_at=now,
            sentiment_score=0.0,
            entities=[],
            source_credibility=0.0,
            corroboration=0.0,
            contradiction_score=0.0,
            propagation_delay_seconds=0.0,
            freshness_score=0.0,
            novelty=1.0,
            article_count=0,
            query=query,
        )


__all__ = ["NewsAgent"]
