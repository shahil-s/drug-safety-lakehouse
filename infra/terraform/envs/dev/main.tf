locals {
  labels = {
    app         = "drug-safety-lakehouse"
    env         = var.env
    managed_by  = "terraform"
    data_domain = "pharmacovigilance"
  }

  datasets = {
    raw     = "Source payloads exactly as received. Append-only."
    staging = "Typed, de-duplicated source entities. Rebuilt by dbt."
    curated = "Conformed, tested business models and signal metrics."
    audit   = "Pipeline run audit trail. Append-only."
  }
}

# ---------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "dataflow.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Storage: raw zone (immutable) and curated zone
# ---------------------------------------------------------------------------
module "raw_bucket" {
  source         = "../../modules/gcs_bucket"
  name           = "${var.project_id}-raw-${var.env}"
  project_id     = var.project_id
  location       = var.region
  retention_days = var.raw_retention_days
  force_destroy  = true # dev only
  labels         = merge(local.labels, { layer = "raw" })
}

module "curated_bucket" {
  source        = "../../modules/gcs_bucket"
  name          = "${var.project_id}-curated-${var.env}"
  project_id    = var.project_id
  location      = var.region
  force_destroy = true # dev only
  labels        = merge(local.labels, { layer = "curated" })
}

# ---------------------------------------------------------------------------
# BigQuery datasets (one per layer = one access boundary per layer)
# ---------------------------------------------------------------------------
resource "google_bigquery_dataset" "layers" {
  for_each                   = local.datasets
  dataset_id                 = each.key
  location                   = var.bq_location
  description                = each.value
  delete_contents_on_destroy = true # dev only
  labels                     = merge(local.labels, { layer = each.key })
  depends_on                 = [google_project_service.apis]
}

resource "google_bigquery_table" "raw_openfda_adverse_events" {
  dataset_id          = google_bigquery_dataset.layers["raw"].dataset_id
  table_id            = "openfda_adverse_events"
  description         = "openFDA drug adverse event payloads, append-only."
  deletion_protection = false # true in prod
  labels              = local.labels

  time_partitioning {
    type  = "DAY"
    field = "_fetched_at"
  }

  schema = jsonencode([
    { name = "_ingest_id", type = "STRING", mode = "REQUIRED", description = "Ingestion run ID" },
    { name = "_source_url", type = "STRING", mode = "NULLABLE", description = "Source API request" },
    { name = "_fetched_at", type = "TIMESTAMP", mode = "REQUIRED", description = "UTC fetch time" },
    { name = "payload", type = "JSON", mode = "NULLABLE", description = "Source record as received" },
  ])
}

resource "google_bigquery_table" "audit_pipeline_runs" {
  dataset_id          = google_bigquery_dataset.layers["audit"].dataset_id
  table_id            = "pipeline_runs"
  description         = "One row per pipeline run: who, what, when, counts, output checksums."
  deletion_protection = false # true in prod
  labels              = local.labels

  time_partitioning {
    type  = "DAY"
    field = "started_at"
  }

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED" },
    { name = "pipeline", type = "STRING", mode = "REQUIRED" },
    { name = "actor", type = "STRING", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "NULLABLE" },
    { name = "parameters", type = "JSON", mode = "NULLABLE" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "ended_at", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "records_expected", type = "INT64", mode = "NULLABLE" },
    { name = "records_received", type = "INT64", mode = "NULLABLE" },
    { name = "records_rejected", type = "INT64", mode = "NULLABLE" },
    { name = "reconciled", type = "BOOL", mode = "NULLABLE" },
    { name = "output_files", type = "JSON", mode = "NULLABLE" },
    { name = "error", type = "STRING", mode = "NULLABLE" },
  ])
}

# ---------------------------------------------------------------------------
# Pub/Sub: new-report events, with a dead-letter topic for poison messages
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "adverse_events" {
  name                       = "openfda-adverse-events-${var.env}"
  message_retention_duration = "604800s" # 7 days, allows replay
  labels                     = local.labels
  depends_on                 = [google_project_service.apis]
}

resource "google_pubsub_topic" "adverse_events_dlq" {
  name   = "openfda-adverse-events-dlq-${var.env}"
  labels = local.labels
}

# Note: the Pub/Sub service agent also needs publisher on the DLQ topic and
# subscriber on this subscription for dead-lettering to work. Add in Phase 2.
resource "google_pubsub_subscription" "adverse_events_dataflow" {
  name                 = "openfda-adverse-events-dataflow-${var.env}"
  topic                = google_pubsub_topic.adverse_events.id
  ack_deadline_seconds = 60
  labels               = local.labels

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.adverse_events_dlq.id
    max_delivery_attempts = 5
  }
}

# ---------------------------------------------------------------------------
# Service accounts: one per pipeline, least privilege (ALCOA+: Attributable)
# ---------------------------------------------------------------------------
resource "google_service_account" "ingestion" {
  account_id   = "sa-ingestion-${var.env}"
  display_name = "Ingestion pipelines (${var.env})"
}

resource "google_service_account" "dbt" {
  account_id   = "sa-dbt-${var.env}"
  display_name = "dbt transformations (${var.env})"
}

# Ingestion can CREATE raw objects but not delete or overwrite them.
resource "google_storage_bucket_iam_member" "ingestion_raw_create" {
  bucket = module.raw_bucket.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_raw_write" {
  dataset_id = google_bigquery_dataset.layers["raw"].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_audit_write" {
  dataset_id = google_bigquery_dataset.layers["audit"].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_pubsub_topic_iam_member" "ingestion_publish" {
  topic  = google_pubsub_topic.adverse_events.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

# dbt reads raw and writes only to staging and curated.
resource "google_bigquery_dataset_iam_member" "dbt_raw_read" {
  dataset_id = google_bigquery_dataset.layers["raw"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_write" {
  for_each   = toset(["staging", "curated"])
  dataset_id = google_bigquery_dataset.layers[each.value].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_project_iam_member" "job_users" {
  for_each = {
    ingestion = google_service_account.ingestion.email
    dbt       = google_service_account.dbt.email
  }
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${each.value}"
}
