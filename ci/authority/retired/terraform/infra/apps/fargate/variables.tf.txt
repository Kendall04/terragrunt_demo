# Environment (dev / prod)
variable "env" {
  type        = string
  description = "Deployment environment (dev or prod)."
}

variable "project" { type = string }

variable "aws_region" {
  type        = string
  description = "AWS region where the service is deployed."
}

# Networking
variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnets used for Fargate tasks."
}

variable "alb_listener_arn" {
  type        = string
  description = "ARN of the listener of the ALB."
}

variable "demo_sg_id" {
  type        = string
  description = "Security Group ID applied to the demo Fargate service."
}

variable "demo_blue_tg_arn" {
  type        = string
  description = "ARN of the target group used by the ALB (demo)."
}
variable "demo_green_tg_arn" {
  type        = string
  description = "ARN of the target group used by the ALB (candidate)."
}

# ECS cluster settings
variable "cluster_arn" {
  type        = string
  description = "ARN of the ECS cluster where tasks will run."
}

variable "cluster_name" {
  type        = string
  description = "Name of the ECS cluster where tasks will run."
}

# Secrets Manager
variable "db_secret_arn" {
  type        = string
  description = "ARN of the Secret containing the DB connection string."
}

variable "bootstrap_image" {
  type        = string
  description = "Placeholder image used only for Terraform-created bootstrap task definitions. Real app releases are registered by the deployment pipeline with immutable ECR digests."
  default     = "public.ecr.aws/docker/library/nginx:stable-alpine"
}

# KMS
variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS Key used to store encrypted text in the Database."
}

variable "kms_key_id" {
  type        = string
  description = "ID of the KMS Key used to store encrypted text in the Database."
}

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for ECS service alarms"
}
