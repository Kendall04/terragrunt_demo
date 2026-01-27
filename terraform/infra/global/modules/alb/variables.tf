# Port exposed by the ALB listener and forwarded to the target group
variable "demo_port" {
  type        = number
  default     = 8080
  description = "HTTP port used by the ALB listener and ECS targets."
}

# Health check path used by the ALB to validate service health
variable "demo_health_path" {
  type        = string
  default     = "/health"
  description = "HTTP health check path for ECS service targets."
}

variable "vpc_id" {
  type        = string
  description = "VPC where the ALB and Target Group will be created."
}

variable "sg_id" {
  type        = string
  description = "Security Group ID attached to the ALB."
}

variable "name" {
  type        = string
  description = "Name prefix used across ALB resources."
}

variable "tags" {
  type        = map(string)
  description = "Common set of tags applied to all resources."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnets where the ALB will be deployed."
}

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for alarm notifications"
}
