"""Polling-based real-time news ingestion pipeline."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

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
        dedup_cache_size: int = 512,
    ) -> None:
        self._agent = agent
        self._queries = queries
        self._poll_interval = poll_interval_seconds
        self._on_signal = on_signal
        self._running = False
        self._last_check: datetime | None = None
        self._seen_story_ids: dict[str, datetime] = {}
        self._dedup_cache_size = max(1, dedup_cache_size)

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
                    if signal.article_count <= 0 or self._on_signal is None:
                        continue
                    if self._should_emit(signal.story_id, now):
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

    def _should_emit(self, story_id: str, now: datetime) -> bool:
        """Return True when the story has not already been emitted recently."""
        if not story_id:
            return True
        if story_id in self._seen_story_ids:
            return False

        self._seen_story_ids[story_id] = now
        if len(self._seen_story_ids) > self._dedup_cache_size:
            oldest_story_id = min(self._seen_story_ids, key=self._seen_story_ids.get)
            self._seen_story_ids.pop(oldest_story_id, None)
        return True


__all__ = ["RealtimeNewsPipeline"]
