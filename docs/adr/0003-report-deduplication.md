# ADR-0003 — Report versioning and de-duplication

- **Status:** Accepted
- **Date:** 2026-11-14

## Context
Adverse event reports are amended over time (follow-up information, corrections). Each case has a
`safetyreportid` and a `safetyreportversion`. The same case can also arrive more than once across
API pulls and quarterly files. Counting duplicates would inflate safety signals.

## Decision
- **raw** keeps every version and every duplicate exactly as received.
- **staging** keeps the latest version per `safetyreportid`
  (highest `safetyreportversion`, ties broken by latest `_fetched_at`).
- A dbt test asserts `safetyreportid` is unique in staging.

## Alternatives considered
- De-duplicate at ingestion: rejected, because it loses the original record (violates *Original*).
- Keep all versions in curated as SCD Type 2: deferred. Useful for "what did we know on date X" questions
  and may be added in Phase 3.

## Consequences
Signal counts reflect unique cases. Full version history stays available in raw for audit.
