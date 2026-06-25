variable "name" { type = string }

variable "env" { type = string }

variable "project" { type = string }

variable "github_owner" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "create_github_oidc_provider" {
  type        = bool
  default     = false
  description = "Create the account-level GitHub Actions OIDC provider in this root. Enable in exactly one selected root per AWS account; all other roots should adopt by ARN or lookup."
}

variable "github_oidc_provider_arn" {
  type        = string
  default     = null
  description = "Existing GitHub Actions OIDC provider ARN to adopt. Leave null to look up the singleton provider by URL when create_github_oidc_provider is false."

  validation {
    condition     = !(var.create_github_oidc_provider && var.github_oidc_provider_arn != null)
    error_message = "Do not set github_oidc_provider_arn when create_github_oidc_provider is true."
  }
}

variable "tf_state_bucket_name" {
  type        = string
  description = "Terraform/Terragrunt remote state S3 bucket name. Used only for scoping CI/CD IAM permissions."
}

variable "tf_state_lock_table_name" {
  type        = string
  description = "Terraform/Terragrunt DynamoDB lock table name. Used only for scoping CI/CD IAM permissions."
}

variable "release_artifacts_bucket_name" {
  type        = string
  description = "Account-level S3 bucket name used for release manifests and deployment records."
}

variable "shared_artifact_ecr_repository_name" {
  type        = string
  description = "Account-level, environment-neutral ECR repository name for promoted application artifacts."
}
