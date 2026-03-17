"""Named entity extraction using regex patterns."""

from __future__ import annotations

import re

# Common ticker patterns: $AAPL, $TSLA
_TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b")

# Organization patterns: common suffixes
_ORG_SUFFIXES = re.compile(
    r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)* (?:Inc|Corp|Ltd|LLC|Co|Group|Holdings|Bank))\b"
)

# Capitalized multi-word proper nouns (rough person/org heuristic)
_PROPER_NOUN_RE = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b")


def extract_entities(text: str) -> list[str]:
    """Extract named entities from text using regex heuristics.

    Returns deduplicated list of entity strings.
    """
    if not text:
        return []

    entities: set[str] = set()

    # Tickers
    for match in _TICKER_RE.finditer(text):
        entities.add(f"${match.group(1)}")

    # Organizations
    for match in _ORG_SUFFIXES.finditer(text):
        entities.add(match.group(1))

    # Proper nouns (people, places)
    for match in _PROPER_NOUN_RE.finditer(text):
        name = match.group(1)
        # Filter out common false positives
        if name not in {"The New", "New York", "United States", "Last Year"}:
            entities.add(name)

    return sorted(entities)


def extract_tickers(text: str) -> list[str]:
    """Extract stock tickers from text."""
    return sorted({m.group(1) for m in _TICKER_RE.finditer(text)})


__all__ = ["extract_entities", "extract_tickers"]
