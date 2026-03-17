"""Temporal freshness decay computation."""

from __future__ import annotations

import math
from datetime import UTC, datetime


def freshness_score(
    published_at: datetime,
    now: datetime | None = None,
    half_life_hours: float = 6.0,
) -> float:
    """Compute freshness score using exponential decay.

    Returns value in [0, 1] where 1.0 = just published.
    """
    if now is None:
        now = datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    age_seconds = max(0.0, (now - published_at).total_seconds())
    half_life_seconds = half_life_hours * 3600.0
    return math.exp(-0.693 * age_seconds / half_life_seconds)


__all__ = ["freshness_score"]
