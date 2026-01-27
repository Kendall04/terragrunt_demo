output "github_role_terragrunt_ci_arn" {
  description = "IAM role ARN used by GitHub Actions for Terragrunt CI (plan only)"
  value       = aws_iam_role.github_terragrunt_ci.arn
}

output "github_role_terragrunt_cd_arn" {
  description = "IAM role ARN used by GitHub Actions for Terragrunt CD (apply)"
  value       = aws_iam_role.github_terragrunt_cd.arn
}

output "github_role_app_cd_arn" {
  description = "IAM role ARN used by GitHub Actions for ECS app deployments (blue/green)"
  value       = aws_iam_role.github_app_cd.arn
}

output "github_role_app_rollback_arn" {
  description = "IAM role ARN used by GitHub Actions for ECS app rollback (blue/green)"
  value       = aws_iam_role.github_app_rollback.arn
}

output "github_oidc_provider_arn" {
  value = local.github_oidc_provider_arn
}
