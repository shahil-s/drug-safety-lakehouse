# A locked-down bucket: no public access, uniform IAM, object versioning,
# optional retention policy (objects cannot be deleted or overwritten before it expires),
# and lifecycle rules that move old objects to cheaper storage.

resource "google_storage_bucket" "this" {
  name                        = var.name
  project                     = var.project_id
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy
  labels                      = var.labels

  versioning {
    enabled = true
  }

  dynamic "retention_policy" {
    for_each = var.retention_days > 0 ? [1] : []
    content {
      retention_period = var.retention_days * 86400
      is_locked        = false # lock only in prod, after QA sign-off: locking is irreversible
    }
  }

  lifecycle_rule {
    condition {
      age = var.coldline_after_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}
