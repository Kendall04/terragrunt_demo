# ==========================================================
# KMS OUTPUTS
# ==========================================================

# ARN of the customer-managed KMS key used by the demo microservices.
# Required when attaching IAM permissions to ECS tasks or Lambda.
output "kms_key_arn" {
  description = "ARN of the KMS Key used by microservices."
  value       = module.kms.kms_key_arn
}

# The unique KMS Key ID (not the ARN), useful for low-level API calls.
output "kms_key_id" {
  description = "ID of the KMS Key."
  value       = module.kms.kms_key_id
}

# ARN of the alias attached to the KMS Key, used to reference the key
# in IAM permissions and encryption calls with a stable identifier.
output "kms_alias_arn" {
  description = "ARN of the KMS key alias."
  value       = module.kms.kms_alias_arn
}

# ==========================================================
# ECR OUTPUTS
# ==========================================================

# List of all ECR repository ARNs created for this environment.
output "ecr_repository_arns" {
  description = "ARNs of ECR repositories created in the shared layer."
  value       = module.ecr.repository_arns
}

# List of full ECR repository URLs (e.g., 1234.dkr.ecr.us-east-1.amazonaws.com/repo)
# consumed by CI/CD pipelines and Terraform ECS modules.
output "ecr_repository_urls" {
  description = "Full repository URLs for all ECR repositories."
  value       = module.ecr.repository_urls
}

output "ecr_repository_url" {
  description = "Full repository URL for a single ECR repository (used by the demo image)."
  value       = module.ecr.repository_urls["${local.name}-demo-ms"]
}

output "shared_artifact_ecr_repository_name" {
  description = "Environment-neutral ECR repository name for promoted Demo API artifacts."
  value       = local.shared_artifact_ecr_repository_name
}

output "shared_artifact_ecr_repository_arn" {
  description = "Deterministic ARN of the environment-neutral ECR artifact repository."
  value       = "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${local.shared_artifact_ecr_repository_name}"
}

output "shared_artifact_ecr_repository_url" {
  description = "Deterministic URL of the environment-neutral ECR artifact repository."
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.shared_artifact_ecr_repository_name}"
}



# ============================================================
# Re-expose GitHub IAM roles so environments (dev/prod)
# and CI/CD workflows can access them cleanly.
# ============================================================

output "github_role_terragrunt_ci_arn" {
  description = "IAM role ARN for Terragrunt CI (lint + plan)"
  value       = module.iam_github.github_role_terragrunt_ci_arn
}

output "github_role_terragrunt_cd_arn" {
  description = "IAM role ARN for Terragrunt CD (apply)"
  value       = module.iam_github.github_role_terragrunt_cd_arn
}

output "github_role_terragrunt_cd_high_risk_arn" {
  description = "IAM role ARN for high-risk Terragrunt CD apply after approval"
  value       = module.iam_github.github_role_terragrunt_cd_high_risk_arn
}

output "github_role_app_cd_arn" {
  description = "IAM role ARN for ECS App CD (blue/green deploy)"
  value       = module.iam_github.github_role_app_cd_arn
}

output "github_role_app_rollback_arn" {
  description = "IAM role ARN for ECS App rollback"
  value       = module.iam_github.github_role_app_rollback_arn
}

output "github_role_release_build_arn" {
  description = "IAM role ARN for Demo API release-build"
  value       = module.iam_github.github_role_release_build_arn
}

output "github_role_dev_deploy_arn" {
  description = "IAM role ARN for Demo API dev deploy"
  value       = module.iam_github.github_role_dev_deploy_arn
}

output "github_role_prod_promote_arn" {
  description = "IAM role ARN for Demo API prod promotion"
  value       = module.iam_github.github_role_prod_promote_arn
}


output "alerts_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "SNS topic ARN for CloudWatch alarm notifications"
}

output "release_artifacts_bucket_name" {
  description = "Account-level S3 bucket used for durable release manifests and deployment records."
  value       = local.release_artifacts_bucket_name
}

output "release_artifacts_bucket_arn" {
  description = "ARN of the account-level release artifacts bucket."
  value       = "arn:aws:s3:::${local.release_artifacts_bucket_name}"
}
