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
