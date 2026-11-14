# ADR-0002 — Medallion layers with an immutable raw zone

- **Status:** Accepted
- **Date:** 2026-11-14

## Context
Regulated data must be traceable to its original source (ALCOA+: *Original*, *Attributable*).
We must be able to answer: "What exactly did we receive, when, from where, and what did we do to it?"

## Decision
Three layers, each in its own BigQuery dataset and access boundary:

| Layer | Contents | Rules |
|---|---|---|
| **raw** | Source payloads exactly as received, plus ingestion metadata (`_ingest_id`, `_source_url`, `_fetched_at`, `_sha256`) | Append-only. No updates or deletes. GCS bucket has versioning + a retention policy. |
| **staging** | Typed, de-duplicated, one model per source entity | Rebuilt from raw at any time. No business logic. |
| **curated** | Conformed dimensions, facts, signal metrics | Business logic lives here, fully tested. |

A separate **audit** dataset records every ingestion and transformation run.

## Consequences
- Any curated number can be traced back to the exact raw files that produced it.
- Storage grows because raw is never pruned; lifecycle rules move old objects to cheaper storage classes.
- Fixing a bug means fixing code and rebuilding downstream layers, never editing data by hand.
