# News Agent

`news-agent` is a Python service package for ingesting news articles, extracting trust-relevant signals, and producing a normalized trust result for the TollamaAI trust pipeline.

The current implementation already includes:

- async connectors for `NewsAPI`, `GDELT`, and `RSS`
- a `NewsAgent` orchestrator for fetch -> feature build -> trust scoring
- a FastAPI surface for health, signal generation, and trust payload access
- batch and polling pipeline classes
- schema and feature tests that currently pass

## Architecture

The main execution path is:

1. A caller invokes `NewsAgent.process_query(...)` or `GET /api/v1/news/signals`.
2. The configured connectors fetch raw article records.
3. Raw records are normalized into `ArticleSnapshot` objects.
4. `features.build_features.build_news_features(...)` computes sentiment, entities, credibility, novelty, freshness, corroboration, and placeholder contradiction values.
5. `NewsAgent` aggregates the article-level features into one `NewsSignal`.
6. `calibration.news_trust_score.compute_news_trust(...)` produces the composite trust score and component breakdown.
7. The API or pipeline returns a normalized result or a trust payload.

## Repository Layout

- `agents/`: orchestration logic, primarily [`agents/news_agent.py`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/agents/news_agent.py)
- `api/`: FastAPI routes in [`api/routes.py`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/api/routes.py)
- `connectors/`: provider clients and normalizers
- `features/`: feature engineering and heuristic NLP helpers
- `calibration/`: trust score composition
- `pipelines/`: batch and polling workflows
- `schemas/`: `ArticleSnapshot`, `NewsSignal`, and enums
- `storage/`: JSONL read/write helpers
- `configs/`: default configuration values in [`configs/default.yaml`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/configs/default.yaml)
- `tests/`: unit coverage across schemas, features, connectors, calibration, pipelines, and agent contract behavior

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,server]"
```

## Test

```bash
pytest -q
```

The current test suite passes in this workspace.

## API Surface

Defined in [`api/routes.py`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/api/routes.py):

- `GET /api/v1/news/health`
- `GET /api/v1/news/signals`
- `GET /api/v1/news/trust/{story_id}`
- `POST /api/v1/news/analyze`
- `GET /stories/{story_id}` for compatibility

Important: the FastAPI app expects `init_agent(...)` to be called before handling requests. This repository does not currently include a dedicated startup module that reads `configs/default.yaml` and wires connectors automatically.

## Minimal Bootstrap Pattern

The intended integration pattern is:

```python
from agents.news_agent import NewsAgent
from api.routes import app, init_agent
from connectors.factory import create_news_connector
from schemas.enums import NewsProvider

connectors = [
    create_news_connector(
        NewsProvider.NEWSAPI,
        {
            "api_key": "...",
            "base_url": "https://newsapi.org/v2",
            "timeout": 10.0,
        },
    )
]

init_agent(NewsAgent(connectors))
```

Once initialized, the shared `app` object can be served by Uvicorn or mounted into a larger application.

## Current Implementation Notes

- Trust scoring is heuristic and deterministic, not model-based.
- Source credibility comes from a static source tier map.
- Contradiction detection is currently a placeholder fixed to a low contradiction baseline.
- Storage helpers exist, but the provided pipelines do not yet persist artifacts by default.
- Provider-specific normalizer modules exist for `GDELT` and `RSS`, but the main `NewsAgent.process_query(...)` path currently normalizes fetched records through the NewsAPI snapshot normalizer.

## Detailed Design

Implementation details, data contracts, and follow-up gaps are documented in [`docs/implementation.md`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/docs/implementation.md).
