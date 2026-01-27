variable "env" {
  type        = string
  description = "Deployment environment (e.g., dev, prod)."
}

variable "project" { type = string }

variable "aws_region" {
  type        = string
  description = "AWS region where resources will be deployed."
}

variable "instance_type" {
  description = "EC2 instance type for the SQL server."
  type        = string
  default     = "t3a.small"
}

variable "cpu_credits" {
  description = "CPU credit mode for T family instances: standard | unlimited."
  type        = string
  default     = "standard"
  validation {
    condition     = contains(["standard", "unlimited"], var.cpu_credits)
    error_message = "cpu_credits must be 'standard' or 'unlimited'."
  }
}

variable "volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
  default     = 30
}

variable "kms_key_id" {
  description = "Optional KMS key for EBS encryption (null => default aws/ebs key)."
  type        = string
  default     = null
}

variable "key_name" {
  description = "Optional EC2 KeyPair for emergency SSH access."
  type        = string
  default     = null
}

variable "app_db" {
  description = "Name of the application's database."
  type        = string
  default     = "demodb"
}

variable "app_user" {
  description = "SQL user for the application."
  type        = string
  default     = "fargate_user"
}

variable "enable_alarms" {
  description = "Whether to create basic CloudWatch alarms for the EC2 instance."
  type        = bool
  default     = true
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs where the EC2 instance will run."
  type        = list(string)
}

variable "db_instance_sg_id" {
  description = "Security Group ID applied to the SQL Server EC2 instance."
  type        = string
}

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for alarm notifications"
}
