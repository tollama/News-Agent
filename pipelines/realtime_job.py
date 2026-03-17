"""Polling-based real-time news ingestion pipeline."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from agents.news_agent import NewsAgent

logger = logging.getLogger(__name__)


class RealtimeNewsPipeline:
    """Near-real-time news monitoring via periodic polling.

    Polls configured connectors at a fixed interval and emits
    signals for new articles.
    """

    def __init__(
        self,
        agent: NewsAgent,
        queries: list[str],
        poll_interval_seconds: float = 60.0,
        on_signal: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._agent = agent
        self._queries = queries
        self._poll_interval = poll_interval_seconds
        self._on_signal = on_signal
        self._running = False
        self._last_check: datetime | None = None

    async def run(self, max_iterations: int | None = None) -> None:
        """Start the polling loop."""
        self._running = True
        iteration = 0

        while self._running:
            if max_iterations is not None and iteration >= max_iterations:
                break

            now = datetime.now(UTC)
            since = self._last_check

            for query in self._queries:
                try:
                    signal = await self._agent.process_query(
                        query,
                        from_date=since,
                        limit=50,
                    )
                    if signal.article_count > 0 and self._on_signal:
                        self._on_signal(signal.model_dump(mode="json"))
                except Exception:
                    logger.exception("Error polling query: %s", query)

            self._last_check = now
            iteration += 1

            if self._running and (max_iterations is None or iteration < max_iterations):
                await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False


__all__ = ["RealtimeNewsPipeline"]
