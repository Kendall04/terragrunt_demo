variable "name" {
  description = "Secrets Manager secret name."
  type        = string
}

variable "description" {
  description = "Secrets Manager secret description."
  type        = string
}

variable "kms_key_id" {
  description = "Optional KMS key ID or ARN used to encrypt the secret."
  type        = string
  default     = null
}

variable "recovery_window_in_days" {
  description = "Secrets Manager recovery window. Use 0 for immediate deletion in this disposable demo."
  type        = number
  default     = 0

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0, or between 7 and 30."
  }
}

variable "tags" {
  description = "Common tags to apply to the secret."
  type        = map(string)
  default     = {}
}
