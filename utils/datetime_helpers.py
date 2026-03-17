"""Shared datetime parsing utilities."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def parse_datetime(value: str | datetime) -> datetime:
    """Parse a datetime value from multiple common formats.

    Handles ISO 8601, GDELT (``%Y%m%d%H%M%S``), and RFC 2822.
    Returns a timezone-aware datetime (defaults to UTC).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    if not value:
        return datetime.now(UTC)

    # ISO 8601 (with Z shorthand)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass

    # GDELT format: YYYYMMDDHHMMSS
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        pass

    # RFC 2822 (common in RSS feeds)
    try:
        return parsedate_to_datetime(value)
    except (ValueError, TypeError):
        pass

    return datetime.now(UTC)


__all__ = ["parse_datetime"]
