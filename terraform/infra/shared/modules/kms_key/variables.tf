variable "name" {
  description = "Logical name used to tag the KMS Key."
  type        = string
}

variable "alias" {
  description = "Alias name without the 'alias/' prefix."
  type        = string
}

variable "description" {
  description = "Optional description for the KMS Key."
  type        = string
  default     = "KMS key for encryption/decryption operations."
}

variable "tags" {
  description = "Common tags to apply to all resources."
  type        = map(string)
  default     = {}
}

variable "enable_key_rotation" {
  description = "Enable annual rotation for the KMS Key."
  type        = bool
  default     = true
}

variable "deletion_window_in_days" {
  description = "Waiting period (7–30 days) before key deletion."
  type        = number
  default     = 30
}

variable "multi_region" {
  description = "Creates a multi-region key if true."
  type        = bool
  default     = false
}
