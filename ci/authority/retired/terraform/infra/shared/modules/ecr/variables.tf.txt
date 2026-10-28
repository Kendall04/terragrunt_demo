variable "repo_names" {
  description = "List of ECR repositories to create."
  type        = list(string)
}

variable "scan_on_push" {
  description = "Enable vulnerability scanning when images are pushed."
  type        = bool
  default     = true
}

variable "immutable_tags" {
  description = "If true, tags are immutable; otherwise they are mutable."
  type        = bool
  default     = true
}

variable "lifecycle_keep" {
  description = "Number of images to retain per repository."
  type        = number
  default     = 15
}

variable "tags" {
  description = "Map of common tags for all created resources."
  type        = map(string)
  default     = {}
}
