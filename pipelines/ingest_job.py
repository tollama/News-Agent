"""Batch news ingestion pipeline with staged execution."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from agents.news_agent import NewsAgent
from storage.writers import JsonlWriter

logger = logging.getLogger(__name__)

StageName = Literal[
    "discover",
    "ingest",
    "normalize",
    "features",
    "trust",
    "publish",
]

_STAGE_ORDER: list[StageName] = [
    "discover",
    "ingest",
    "normalize",
    "features",
    "trust",
    "publish",
]


class NewsIngestPipeline:
    """Staged batch pipeline for periodic news ingestion.

    Follows the same checkpoint/resume pattern as MCA's daily_job.py.
    """

    def __init__(
        self,
        agent: NewsAgent,
        queries: list[str],
        lookback_hours: float = 24.0,
        limit_per_query: int = 100,
        writer: JsonlWriter | None = None,
    ) -> None:
        self._agent = agent
        self._queries = queries
        self._lookback_hours = lookback_hours
        self._limit = limit_per_query
        self._writer = writer
        self._checkpoint: StageName | None = None
        self._results: dict[str, Any] = {}

    async def run(
        self,
        resume_from: StageName | None = None,
    ) -> dict[str, Any]:
        """Run the full pipeline, optionally resuming from a checkpoint."""
        start_idx = 0
        if resume_from is not None:
            start_idx = _STAGE_ORDER.index(resume_from)

        for stage in _STAGE_ORDER[start_idx:]:
            logger.info("Running stage: %s", stage)
            self._checkpoint = stage
            await self._run_stage(stage)

        return self._results

    async def _run_stage(self, stage: StageName) -> None:
        now = datetime.now(UTC)
        from_date = now - timedelta(hours=self._lookback_hours)

        if stage == "discover":
            self._results["queries"] = self._queries
            self._results["from_date"] = from_date.isoformat()
            self._results["to_date"] = now.isoformat()

        elif stage == "ingest":
            signals = []
            for query in self._queries:
                signal = await self._agent.process_query(
                    query,
                    from_date=from_date,
                    to_date=now,
                    limit=self._limit,
                )
                signals.append(signal)
            self._results["signals"] = [s.model_dump(mode="json") for s in signals]

        elif stage == "normalize":
            # Normalization is done within process_query
            pass

        elif stage == "features":
            # Feature extraction is done within process_query
            pass

        elif stage == "trust":
            trust_results = []
            for signal_data in self._results.get("signals", []):
                result = self._agent.analyze(signal_data)
                trust_results.append(result)
            self._results["trust_results"] = trust_results

        elif stage == "publish":
            # Publish artifacts (trust payloads, signals)
            payloads = []
            for signal_data in self._results.get("signals", []):
                from schemas.signals import NewsSignal

                signal = NewsSignal(**signal_data)
                payload = self._agent.to_trust_payload(signal)
                payloads.append(payload)
            self._results["trust_payloads"] = payloads

            # Persist artifacts if a writer is configured
            if self._writer is not None:
                signals = self._results.get("signals", [])
                if signals:
                    self._writer.write(signals, "signals")
                if payloads:
                    self._writer.write(payloads, "trust_payloads")
                logger.info("Persisted %d signals and %d payloads", len(signals), len(payloads))

            logger.info(
                "Pipeline complete: %d queries, %d payloads",
                len(self._queries),
                len(payloads),
            )

    @property
    def checkpoint(self) -> StageName | None:
        return self._checkpoint


__all__ = ["NewsIngestPipeline"]
