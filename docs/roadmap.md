# Roadmap

Each phase ends with something demo-able and documented. Ship phases 1–2 well before starting the rest.

## Phase 1 — Foundation and batch ingestion (weeks 1–2)
- [ ] GCP project, billing alert, Terraform state bucket
- [ ] Terraform: buckets (raw/curated), BigQuery datasets, service accounts, Pub/Sub topic
- [x] openFDA client with paging, retries, checksums, and audit records (`src/drug_safe/ingestion`)
- [ ] Load raw JSONL into `raw.openfda_adverse_events` (BigQuery load job)
- [ ] dbt staging models + tests (reports, drugs, reactions) with version de-duplication
- [ ] CI green: ruff, pytest, terraform fmt/validate

## Phase 2 — Streaming and master data (weeks 3–4)
- [ ] Cloud Run poller publishes new reports to Pub/Sub
- [ ] Dataflow (Beam) pipeline: Pub/Sub → validation → raw table, dead-letter topic for bad records
- [ ] Drug master: map free-text `medicinalproduct` → RxNorm (golden record, match confidence)
- [ ] Airflow DAG for FAERS quarterly files + historical backfill

## Phase 3 — Governance, PHI, and regulated controls (weeks 5–6)
- [ ] Synthea → FHIR → OMOP CDM transformation on Dataproc Serverless (PySpark)
- [ ] BigQuery policy tags + column-level masking for PHI
- [ ] Lineage (OpenLineage / Dataplex) and data catalog entries
- [ ] Audit table + Iceberg time travel "reproduce as of date" demo
- [ ] Validation plan executed: requirements → tests traceability matrix

## Phase 4 — Signal detection and AI (weeks 7–8)
- [ ] Disproportionality metrics (PRR, ROR) mart in dbt
- [ ] Signal-scoring model tracked in MLflow, containerized
- [ ] RAG safety assistant on Vertex AI with citations to source reports
- [ ] Looker Studio dashboard
- [ ] Final README polish, architecture diagram, 3-minute demo video
