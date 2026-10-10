variable "name" {
  description = "Base name used for the VPC Link (e.g., demo-edge-dev)."
  type        = string
}

variable "tags" {
  description = "Common tags applied to all VPC Link resources."
  type        = map(string)
  default     = {}
}

variable "security_group_ids" {
  description = "List of Security Group IDs attached to the VPC Link ENIs."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs where the VPC Link ENIs will be created."
  type        = list(string)
}
