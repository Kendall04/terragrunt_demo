variable "env" { type = string }

variable "project" { type = string }

variable "aws_region" {
  type        = string
  description = "AWS region for deterministic ARNs/URLs exposed by this shared layer."
}

variable "create_github_oidc_provider" {
  type    = bool
  default = false
}

variable "github_oidc_provider_arn" {
  type        = string
  default     = null
  description = "Existing GitHub Actions OIDC provider ARN to adopt instead of creating or looking up by URL."
}

variable "tf_state_bucket_name" {
  type        = string
  description = "Terraform/Terragrunt remote state S3 bucket name. Used for scoping GitHub CD permissions."
}

variable "tf_state_lock_table_name" {
  type        = string
  description = "Terraform/Terragrunt DynamoDB lock table name. Used for scoping GitHub CD permissions."
}

variable "github_owner" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "alert_email" {
  type        = string
  description = "Email to receive CloudWatch alarms"
}

variable "create_release_artifacts_bucket" {
  type        = bool
  default     = false
  description = "Create the account-level release artifacts bucket from this shared layer."
}

variable "release_artifacts_bucket_name" {
  type        = string
  default     = null
  description = "Optional override for the account-level release artifacts bucket name."
}

variable "create_shared_artifact_ecr_repository" {
  type        = bool
  default     = false
  description = "Create the account-level, environment-neutral ECR artifact repository from this shared layer."
}

variable "shared_artifact_ecr_repository_name" {
  type        = string
  default     = null
  description = "Optional override for the account-level, environment-neutral ECR artifact repository name."
}
