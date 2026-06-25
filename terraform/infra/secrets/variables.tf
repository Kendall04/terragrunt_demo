variable "env" {
  type        = string
  description = "Deployment environment (e.g., dev, prod)."
}

variable "project" {
  type        = string
  description = "Project name used for resource naming."
}

variable "kms_key_id" {
  description = "Optional KMS key ID or ARN used to encrypt Secrets Manager secrets."
  type        = string
  default     = null
}

variable "secret_recovery_window_in_days" {
  description = "Secrets Manager recovery window. Use 0 for immediate deletion in this disposable demo."
  type        = number
  default     = 0

  validation {
    condition     = var.secret_recovery_window_in_days == 0 || (var.secret_recovery_window_in_days >= 7 && var.secret_recovery_window_in_days <= 30)
    error_message = "secret_recovery_window_in_days must be 0, or between 7 and 30."
  }
}
