variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "raw_retention_days" {
  type        = number
  default     = 1
  description = "Kept short in dev so the bucket can be torn down; prod would use years."
}
