"""Tests for features.nlp.entities."""

from features.nlp.entities import extract_entities, extract_tickers


def test_extract_tickers():
    text = "Investors are watching $AAPL and $TSLA closely."
    tickers = extract_tickers(text)
    assert "AAPL" in tickers
    assert "TSLA" in tickers


def test_extract_entities_with_orgs():
    text = "Apple Inc announced new products. Microsoft Corp reported earnings."
    entities = extract_entities(text)
    assert any("Apple Inc" in e for e in entities)
    assert any("Microsoft Corp" in e for e in entities)


def test_extract_entities_empty():
    assert extract_entities("") == []


def test_extract_entities_proper_nouns():
    text = "Janet Yellen spoke about the economy."
    entities = extract_entities(text)
    assert any("Janet Yellen" in e for e in entities)
