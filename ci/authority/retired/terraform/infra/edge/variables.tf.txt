variable "env" {
  type = string
}

variable "project" { type = string }

# ALB listener ARN used by the VPC Link integration
variable "alb_listener_arn" {
  type = string
}

# Private subnets where VPC Link ENIs will be placed
variable "private_subnet_ids" {
  type = list(string)
}

# Security Group ID used by the VPC Link ENIs
variable "vpc_link_sg_id" {
  type = string
}

variable "cors_allowed_origins" {
  description = "Allowed browser origins for API Gateway CORS responses."
  type        = list(string)
  default     = []
}
