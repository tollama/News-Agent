# Implementation Notes

This document describes how the current `news-agent` package works at the code level. It is intentionally aligned to the repository as it exists now, including known shortcuts and incomplete wiring.

## 1. End-to-End Flow

### Query-driven signal generation

The main runtime path is implemented by [`agents/news_agent.py`](agents/news_agent.py):

1. `NewsAgent.process_query(query, from_date, to_date, limit)` loops over all configured connectors.
2. Each connector returns a list of flat article dictionaries.
3. Each raw article is normalized into an `ArticleSnapshot`.
4. The snapshots are converted into a pandas `DataFrame`.
5. `build_news_features(...)` enriches that frame with derived features.
6. `_aggregate_to_signal(...)` reduces the article set into one `NewsSignal`.
7. `analyze(...)` calls `compute_news_trust(...)` and emits a normalized trust result.

### API-driven execution

[`api/routes.py`](api/routes.py) exposes three distinct behaviors:

- `GET /api/v1/news/signals` in **live mode**: full fetch -> feature -> aggregate -> trust path
- `GET /api/v1/news/signals?persisted=true` in **persisted mode**: recent stored signal reads with filters and cursor pagination
- `POST /api/v1/news/analyze`: direct scoring from user-provided text or partial payload
- `GET /api/v1/news/trust/{story_id}`: compatibility payload generation for a single story id

The API stores the agent in a module-level `_agent` variable and requires `init_agent(...)` to be called at startup time.

#### Persisted signals pagination contract

When `persisted=true`, `GET /api/v1/news/signals` accepts:

- `limit` (`1-500`)
- `cursor` (opaque token)
- `query`
- `story_id`
- `from` / `to`

The route validates `cursor` up front and returns `400` when it is not a valid persisted-signals cursor. The response shape is:

```json
{
  "signals": [],
  "count": 0,
  "has_more": false,
  "next_cursor": null,
  "source": "persisted"
}
```

`next_cursor` is generated from an internal offset cursor and should be treated as opaque by clients. When `persisted` is not set, the same route requires `query` and returns the live contract instead (`signal` + `trust` + `source: "live"`).

### Pipeline execution

[`pipelines/ingest_job.py`](pipelines/ingest_job.py) provides a staged batch pipeline:

- `discover`
- `ingest`
- `normalize`
- `features`
- `trust`
- `publish`

In the current implementation, `normalize` and `features` are bookkeeping stages only. The actual work already happens inside `NewsAgent.process_query(...)`.

[`pipelines/realtime_job.py`](pipelines/realtime_job.py) provides polling-based monitoring. It repeatedly calls `process_query(...)` for each tracked query, suppresses recently seen `story_id` values, persists emitted signal/trust/story-summary artifacts, and forwards any non-empty signal to an optional callback.

## 2. Data Contracts

### Raw connector output

All connectors return flat dictionaries with fields such as:

- `article_id`
- `source_name`
- `source_url`
- `headline`
- `body`
- `author`
- `published_at`
- `provider`

This is a loose transport shape, not a validated schema.

### Canonical article snapshot

[`schemas/article.py`](schemas/article.py) defines `ArticleSnapshot`, the validated normalized article model:

- ingestion timestamp: `ts`
- identity: `article_id`
- publisher metadata: `source_name`, `source_url`, `author`
- content fields: `headline`, `body`
- classification: `category`, `provider`, `language`
- event time: `published_at`

### Aggregated trust signal

[`schemas/signals.py`](schemas/signals.py) defines `NewsSignal`, the package's main trust-facing schema.

It includes:

- article identity and representative headline
- the selected source name
- publication and analysis timestamps
- sentiment and entity extraction output
- trust-relevant scores on a `0.0-1.0` scale
- `article_count` and original `query`

### Final scoring output

`NewsAgent.analyze(...)` returns a dict shaped like a normalized trust result:

- `agent_name`
- `domain`
- `trust_score`
- `risk_category`
- `calibration_status`
- `component_breakdown`
- `violations`
- `why_trusted`
- `evidence`
- `audit`

`NewsAgent.to_trust_payload(...)` emits the smaller payload expected by downstream trust consumers.

## 3. Connector Layer

Connector protocols live in [`connectors/base.py`](connectors/base.py).

### Implemented providers

- [`connectors/newsapi.py`](connectors/newsapi.py)
  - calls `/everything`
  - retries common transient HTTP failures up to three times
  - uses `X-Api-Key`
- [`connectors/gdelt.py`](connectors/gdelt.py)
  - calls the GDELT DOC API in `ArtList` mode
  - retries the same transient status set
- [`connectors/rss.py`](connectors/rss.py)
  - parses configured feeds with `feedparser`
  - filters entries by simple query substring matches in headline/body

### Connector factory

[`connectors/factory.py`](connectors/factory.py) maps `NewsProvider` values to connector instances and fills provider defaults from a config dict.

## 4. Normalization

Provider-specific snapshot normalizers exist in:

- [`connectors/newsapi_normalizer.py`](connectors/newsapi_normalizer.py)
- [`connectors/gdelt_normalizer.py`](connectors/gdelt_normalizer.py)
- [`connectors/rss_normalizer.py`](connectors/rss_normalizer.py)

Normalization responsibilities are:

- parse provider-specific timestamps
- infer article category from headline keywords
- stamp ingestion time
- validate the normalized output with `ArticleSnapshot`

The main agent path dispatches normalization through `connectors.normalizer_registry.normalize_article(...)`, so provider-specific normalizers for `NewsAPI`, `GDELT`, and `RSS` are used automatically.

## 5. Feature Engineering

[`features/build_features.py`](features/build_features.py) computes the article-level features used later during scoring.

### Sentiment

[`features/nlp/sentiment.py`](features/nlp/sentiment.py) uses VADER and returns the compound score in `[-1, 1]`.

### Entities

[`features/nlp/entities.py`](features/nlp/entities.py) uses regex heuristics:

- `$AAPL`-style tickers
- organization suffix patterns like `Inc`, `Corp`, `Bank`
- capitalized multi-word proper nouns

This is deliberately lightweight and will miss many real-world entities.

### Credibility

[`features/nlp/credibility.py`](features/nlp/credibility.py) maps lowercased publisher names to a static tier table:

- Tier 1 -> `0.95`
- Tier 2 -> `0.80`
- Tier 3 -> `0.65`
- unknown -> `0.40`

### Deduplication and novelty

[`features/nlp/dedup.py`](features/nlp/dedup.py) builds MinHash signatures from headline character shingles and uses `MinHashLSH` to find near-duplicate clusters.

Novelty is computed as:

- `1.0 / cluster_size` when an article is in a duplicate cluster
- `1.0` when it is unique

### Freshness and corroboration

`build_news_features(...)` also computes:

- `freshness_score` using exponential decay with a 6 hour half-life
- `propagation_delay_seconds` relative to the earliest article in a duplicate cluster
- `corroboration` as the fraction of other articles that share extracted entities

### Contradiction

`contradiction_score` is currently a hard-coded placeholder of `0.2` for every article.

## 6. Aggregation Logic

`NewsAgent._aggregate_to_signal(...)` reduces a feature-enriched frame into one `NewsSignal`.

The current aggregation rules are:

- choose the article with highest `source_credibility` as the representative article
- merge and deduplicate entities across all articles
- compute average sentiment across all rows
- use unique source count and total article count to derive corroboration
- use means for freshness, novelty, contradiction, and propagation delay

This means the final signal is a blend of aggregate metrics plus the metadata of one representative source/article.

## 7. Trust Scoring

[`calibration/news_trust_score.py`](calibration/news_trust_score.py) defines the scoring formula.

Default component weights:

- `source_credibility`: `0.30`
- `corroboration`: `0.25`
- `freshness`: `0.20`
- `novelty`: `0.15`
- `contradiction_penalty`: `0.10`

The contradiction component is inverted before scoring:

- `contradiction_component = 1.0 - contradiction_score`

Composite score:

```text
trust_score =
    0.30 * source_credibility +
    0.25 * corroboration +
    0.20 * freshness +
    0.15 * novelty +
    0.10 * (1.0 - contradiction_score)
```

Risk mapping:

- `GREEN` for scores `>= 0.75`
- `YELLOW` for scores `>= 0.50` and `< 0.75`
- `RED` otherwise

`NewsAgent` adds:

- `calibration_status`
- rule-based violation flags
- human-readable explanation text
- evidence and audit metadata

## 8. Persistence Utilities

[`storage/writers.py`](storage/writers.py) writes JSONL partitions under:

```text
data/raw/<dataset>/dt=YYYY-MM-DD/<HHMMSS>.jsonl
```

[`storage/readers.py`](storage/readers.py) reads those partitions back.

These helpers are integrated into both pipeline classes: the batch pipeline persists signals, trust payloads, story summaries, and cluster summaries by partition, while the realtime pipeline persists emitted signals plus companion trust/story-summary artifacts.

## 9. Configuration

[`configs/default.yaml`](configs/default.yaml) declares defaults for:

- app metadata and timezone
- data directories
- provider settings
- NLP tuning
- trust weights
- pipeline intervals
- API host and port

Current behavior:

- `configs/loader.py` can load `configs/default.yaml` and bootstrap enabled connectors into a `NewsAgent`
- `api/routes.py` uses a FastAPI lifespan hook to attempt that bootstrap automatically when the app starts
- callers can still bypass auto-bootstrap and inject a prebuilt agent with `init_agent(...)` when embedding the app

## 10. Known Gaps and Follow-Up Work

The most important implementation gaps today are:

- contradiction detection is still heuristic and placeholder-heavy
- source credibility still depends on a curated YAML registry rather than external reputation data
- API bootstrap is intentionally simple: auto-bootstrap covers the common path, while richer dependency injection remains manual for embedded deployments

## 11. Validation Status

The repository's current test suite passes with:

```bash
pytest -q
```
