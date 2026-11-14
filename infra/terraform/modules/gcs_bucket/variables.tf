variable "name" {
  type = string
}

variable "project_id" {
  type = string
}

variable "location" {
  type = string
}

variable "retention_days" {
  type        = number
  default     = 0
  description = "Minimum days an object must be kept. 0 disables the retention policy."
}

variable "coldline_after_days" {
  type    = number
  default = 90
}

variable "force_destroy" {
  type    = bool
  default = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
