# News Agent

`news-agent` is a Python service package for ingesting news articles, extracting trust-relevant signals, and producing a normalized trust result for the TollamaAI trust pipeline.

The current implementation already includes:

- async connectors for `NewsAPI`, `GDELT`, and `RSS`
- a `NewsAgent` orchestrator for fetch -> feature build -> trust scoring
- a FastAPI surface for health, readiness, signal generation, trust payload access, recent persisted story summaries, and recent cluster summaries
- optional API-key protection for non-health endpoints via `NEWS_AGENT_API_KEY` or `API_KEY`
- lightweight persisted `story_id` lookup indexing for faster trust artifact reads
- JSONL persistence with a SQLite sidecar index for practical artifact lookup without changing the append-log format
- event/story clustering that can aggregate a dominant multi-article cluster instead of always anchoring on a single article
- a dedicated `services.story_clusters` module that centralizes cluster heuristics for feature extraction, pipeline publication, and API reads
- polling pipeline deduplication to avoid re-emitting the same story repeatedly
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
- `storage/`: JSONL read/write helpers plus a SQLite artifact index sidecar
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
- `GET /api/v1/news/ready`
- `GET /api/v1/news/signals`
- `GET /api/v1/news/stories/recent`
- `GET /api/v1/news/clusters/recent`
- `GET /api/v1/news/trust/{story_id}`
- `POST /api/v1/news/analyze`
- `GET /stories/{story_id}` for compatibility

When `NEWS_AGENT_API_KEY` (or fallback `API_KEY`) is set, all non-health/readiness API routes require either `X-API-Key: <key>` or `Authorization: Bearer <key>`.

### `GET /api/v1/news/signals` modes

This endpoint has two product-facing modes:

- **Live mode** (default): runs the full fetch -> feature -> trust pipeline and **requires** `query`.
- **Persisted mode** (`persisted=true`): returns stored signal artifacts and supports product-facing filters plus cursor pagination.

Persisted-mode query parameters:

- `persisted=true`
- `limit` (`1-500`)
- `cursor` (opaque pagination token returned by a previous persisted read)
- `query` (matches persisted `query`, `headline`, `story_id`, `source_name`, or extracted `entities`)
- `story_id`
- `from` / `to` (ISO datetime window applied against `analyzed_at`, falling back to `published_at`)

Persisted-mode response contract:

```json
{
  "signals": [{ "story_id": "story-123", "headline": "..." }],
  "count": 1,
  "has_more": false,
  "next_cursor": null,
  "source": "persisted"
}
```

Pagination notes:

- Results are returned newest-first from persisted storage.
- `next_cursor` is only present when `has_more=true`.
- Pass `next_cursor` back unchanged to fetch the next page.
- Invalid persisted cursors return `400` with `cursor must be a valid persisted signals cursor`.
- When `persisted` is omitted/false, `query` is required and the response shape switches to the live contract: `{ "signal": ..., "trust": ..., "source": "live" }`.

### Example: live signals request

```bash
curl --get "$BASE_URL/api/v1/news/signals" \
  -H "X-API-Key: $NEWS_AGENT_API_KEY" \
  --data-urlencode "query=fed rates" \
  --data-urlencode "limit=5"
```

Example live response:

```json
{
  "signal": {
    "story_id": "fed-rates-2026-03-24",
    "headline": "Federal Reserve holds rates steady",
    "source_name": "Reuters",
    "published_at": "2026-03-24T12:00:00+00:00",
    "analyzed_at": "2026-03-24T12:00:03+00:00",
    "entities": ["Federal Reserve", "Jerome Powell"],
    "article_count": 6,
    "query": "fed rates"
  },
  "trust": {
    "agent_name": "news_agent",
    "domain": "news",
    "trust_score": 0.82,
    "risk_category": "low",
    "calibration_status": "well_calibrated",
    "component_breakdown": {
      "source_credibility": {"score": 0.91, "weight": 0.35},
      "corroboration": {"score": 0.78, "weight": 0.25},
      "contradiction_penalty": {"score": 0.96, "weight": 0.10}
    },
    "violations": [],
    "why_trusted": "Trust score 0.82: strongest factor is source_credibility (91%), weakest is contradiction_penalty (96%), based on 6 article(s).",
    "evidence": {
      "source_type": "news_feed",
      "source_ids": ["fed-rates-2026-03-24"],
      "freshness_seconds": 45.0
    },
    "audit": {
      "formula_version": "v1",
      "generated_at": "2026-03-24T12:00:03+00:00",
      "agent_version": "0.1.0"
    }
  },
  "source": "live"
}
```

### Example: persisted signals request

```bash
curl --get "$BASE_URL/api/v1/news/signals" \
  -H "Authorization: Bearer $NEWS_AGENT_API_KEY" \
  --data-urlencode "persisted=true" \
  --data-urlencode "query=fed" \
  --data-urlencode "story_id=fed-rates-2026-03-24" \
  --data-urlencode "limit=2"
```

Example persisted response:

```json
{
  "signals": [
    {
      "story_id": "fed-rates-2026-03-24",
      "headline": "Federal Reserve holds rates steady",
      "source_name": "Reuters",
      "published_at": "2026-03-24T12:00:00+00:00",
      "analyzed_at": "2026-03-24T12:00:03+00:00",
      "entities": ["Federal Reserve", "Jerome Powell"],
      "article_count": 6,
      "query": "fed rates"
    }
  ],
  "count": 1,
  "has_more": false,
  "next_cursor": null,
  "source": "persisted"
}
```

### Example: recent stories request

```bash
curl --get "$BASE_URL/api/v1/news/stories/recent" \
  -H "X-API-Key: $NEWS_AGENT_API_KEY" \
  --data-urlencode "query=powell" \
  --data-urlencode "limit=3"
```

Example stories response:

```json
{
  "stories": [
    {
      "story_id": "fed-rates-2026-03-24",
      "headline": "Federal Reserve holds rates steady",
      "query": "fed rates",
      "source_name": "Reuters",
      "published_at": "2026-03-24T12:00:00+00:00",
      "analyzed_at": "2026-03-24T12:00:03+00:00",
      "article_count": 6,
      "entities": ["Federal Reserve", "Jerome Powell"],
      "trust_score": 0.82,
      "risk_category": "low",
      "calibration_status": "well_calibrated"
    }
  ],
  "count": 1
}
```

### Example: recent clusters request

```bash
curl --get "$BASE_URL/api/v1/news/clusters/recent" \
  -H "X-API-Key: $NEWS_AGENT_API_KEY" \
  --data-urlencode "query=fed" \
  --data-urlencode "limit=2"
```

Example clusters response:

```json
{
  "clusters": [
    {
      "cluster_id": "recent-cluster-1",
      "headline": "Federal Reserve holds rates as Powell signals patience",
      "query": "fed rates",
      "story_ids": ["fed-rates-2026-03-24", "powell-guidance-2026-03-24"],
      "story_count": 2,
      "total_article_count": 7,
      "source_names": ["Reuters", "AP"],
      "top_entities": ["Federal Reserve", "Jerome Powell"],
      "latest_published_at": "2026-03-24T12:00:00+00:00",
      "latest_analyzed_at": "2026-03-24T12:00:03+00:00",
      "avg_trust_score": 0.81,
      "max_trust_score": 0.88,
      "risk_category": "low",
      "calibration_status": "well_calibrated"
    }
  ],
  "count": 1
}
```

### Example: trust payload request

```bash
curl "$BASE_URL/api/v1/news/trust/fed-rates-2026-03-24" \
  -H "X-API-Key: $NEWS_AGENT_API_KEY"
```

Connector-compatible alias:

```bash
curl "$BASE_URL/stories/fed-rates-2026-03-24" \
  -H "X-API-Key: $NEWS_AGENT_API_KEY"
```

Example trust payload response:

```json
{
  "story_id": "fed-rates-2026-03-24",
  "source_credibility": 0.91,
  "corroboration": 0.78,
  "contradiction_score": 0.04,
  "propagation_delay_seconds": 45.0,
  "freshness_score": 0.97,
  "novelty": 0.33,
  "trust_score": 0.82,
  "risk_category": "low",
  "calibration_status": "well_calibrated"
}
```

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
- Trust weights now bootstrap from `configs/default.yaml`, so calibration can be tuned without touching code.
- Source credibility now loads from `configs/source_credibility.yaml` (overrideable via `NEWS_AGENT_CREDIBILITY_CONFIG`) instead of being hardcoded in-module.
- Contradiction detection is still heuristic, but now aggregates at the selected story-cluster level instead of a single representative article only.
- Storage helpers keep JSONL as the primary append log and additionally maintain `.artifacts.sqlite3` for fast lookups by persisted fields such as `story_id`, including recent persisted story summaries exposed by the API.
- Persisted `story_clusters` now have an explicit `storage.story_clusters` helper layer for write/read/query flows, so `/api/v1/news/clusters/recent` can serve stored cluster views through a dedicated accessor before falling back to ad hoc reconstruction from recent signals.
- Provider-specific normalizer modules exist for `GDELT` and `RSS`, and the main `NewsAgent.process_query(...)` path dispatches through the provider-aware normalizer registry.

## Detailed Design

Implementation details, data contracts, and follow-up gaps are documented in [`docs/implementation.md`](/Users/yongchoelchoi/Documents/TollamaAI-Github/News-Agent/docs/implementation.md).
