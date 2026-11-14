# Streaming pipeline (Phase 2)

**Build this one yourself.** It is the piece interviewers are most likely to dig into.

## Target design
```
Pub/Sub (openfda-adverse-events)
  → Parse JSON
  → Validate (has safetyreportid, receivedate parses)
      ├─ valid   → add ingestion metadata → BigQuery raw.openfda_adverse_events (append)
      └─ invalid → Pub/Sub DLQ / GCS dead-letter files, with the error reason
  → Per-window counts → audit.pipeline_runs
```

## Questions to be ready for
- Why Beam/Dataflow over Cloud Functions? (Scale, windowing, exactly-once sinks, back-pressure)
- How do you handle duplicates? (Raw keeps everything; staging de-duplicates. See ADR-0003)
- What happens to a malformed message? (Dead-letter with reason; never silently dropped)
- How do you replay? (Topic retention 7 days + raw is the replay source after that)

## Suggested files
- `pipeline.py` — Beam pipeline with `--streaming`
- `transforms.py` — pure functions (parse, validate, enrich), unit tested without Beam
- `tests/test_transforms.py`
