variable "name" {
  description = "Logical name for the ECS cluster."
  type        = string
}

variable "tags" {
  description = "Common tags applied to ECS resources."
  type        = map(string)
  default     = {}
}

variable "enable_capacity_providers" {
  type        = bool
  description = "Enable ECS capacity providers for Fargate and Fargate Spot."
  default     = true
}

variable "fargate_base" {
  type        = number
  description = "Base number of Fargate tasks before using Spot capacity."
  default     = 0
}
