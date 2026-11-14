# ALCOA+ data integrity controls

ALCOA+ is the data integrity framework used by FDA and MHRA to assess GxP records.
This table maps each principle to the technical control that implements it in this platform.

| Principle | Meaning | Control in this platform | Status |
|---|---|---|---|
| **Attributable** | Who/what created or changed the data | Each pipeline runs as its own service account; every run writes an audit record with `actor` and `run_id` | Partial |
| **Legible** | Readable for the record's lifetime | Open formats (JSONL, Parquet/Iceberg); documented schemas in dbt | Partial |
| **Contemporaneous** | Recorded when it happened | System-generated UTC timestamps (`_fetched_at`, audit `started_at`/`ended_at`) | Done |
| **Original** | The first capture is preserved | Append-only raw zone; GCS versioning + retention policy | Partial |
| **Accurate** | Correct and verified | SHA-256 checksum per raw file; dbt tests; row-count reconciliation in audit | Partial |
| **Complete** | Nothing missing | Expected-vs-received counts per pull (`meta.results.total`); dead-letter for rejected records | Planned |
| **Consistent** | Same process every time | Code in Git, CI, Terraform; no manual changes in prod | Partial |
| **Enduring** | Lasts for the retention period | GCS retention policy; lifecycle to archive storage | Planned |
| **Available** | Retrievable for review | Audit dataset queryable; Iceberg time travel to reproduce past states | Planned |

## 21 CFR Part 11 notes (electronic records)
- **Audit trails:** `audit.pipeline_runs` (append-only) plus Cloud Audit Logs for admin actions.
- **Access control:** least-privilege IAM per service account; humans get read-only access in prod.
- **Change control:** every change goes through a pull request with review and passing CI.
- **Electronic signatures:** out of scope for this project (no human approval workflows).
