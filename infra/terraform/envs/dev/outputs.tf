output "raw_bucket" {
  value = module.raw_bucket.name
}

output "curated_bucket" {
  value = module.curated_bucket.name
}

output "ingestion_service_account" {
  value = google_service_account.ingestion.email
}

output "dbt_service_account" {
  value = google_service_account.dbt.email
}

output "adverse_events_topic" {
  value = google_pubsub_topic.adverse_events.id
}
