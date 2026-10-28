variable "name" {
  description = "Base name for API Gateway resources."
  type        = string
}

variable "tags" {
  description = "Common tags applied to API Gateway resources."
  type        = map(string)
  default     = {}
}

variable "vpc_link_id" {
  description = "ID of the VPC Link used for ALB integration."
  type        = string
}

variable "alb_listener_arn" {
  description = "ARN of the ALB/NLB listener used as integration target."
  type        = string
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for browser clients. Empty list disables CORS responses."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for origin in var.cors_allowed_origins : !strcontains(origin, "*")])
    error_message = "cors_allowed_origins cannot contain wildcard values."
  }
}
