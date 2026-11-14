terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # State lives in a GCS bucket you create once by hand (with versioning on):
  #   terraform init -backend-config="bucket=<your-tf-state-bucket>"
  backend "gcs" {
    prefix = "drug-safety-lakehouse/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
