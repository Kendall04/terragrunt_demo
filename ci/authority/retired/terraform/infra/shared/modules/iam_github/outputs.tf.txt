output "github_role_terragrunt_ci_arn" {
  description = "IAM role ARN used by GitHub Actions for Terragrunt CI (plan only)"
  value       = aws_iam_role.github_terragrunt_ci.arn
}

output "github_role_terragrunt_cd_arn" {
  description = "IAM role ARN used by GitHub Actions for Terragrunt CD (apply)"
  value       = aws_iam_role.github_terragrunt_cd.arn
}

output "github_role_terragrunt_cd_high_risk_arn" {
  description = "IAM role ARN used by GitHub Actions for high-risk Terragrunt CD apply after approval"
  value       = aws_iam_role.github_terragrunt_cd_high_risk.arn
}

output "github_role_app_cd_arn" {
  description = "IAM role ARN used by GitHub Actions for ECS app deployments (blue/green)"
  value       = aws_iam_role.github_app_cd.arn
}

output "github_role_app_rollback_arn" {
  description = "IAM role ARN used by GitHub Actions for ECS app rollback (blue/green)"
  value       = aws_iam_role.github_app_rollback.arn
}

output "github_role_release_build_arn" {
  description = "IAM role ARN used by GitHub Actions for Demo API release builds"
  value       = try(aws_iam_role.github_release_build[0].arn, null)
}

output "github_role_dev_deploy_arn" {
  description = "IAM role ARN used by GitHub Actions for Demo API dev deploys"
  value       = try(aws_iam_role.github_dev_deploy[0].arn, null)
}

output "github_role_prod_promote_arn" {
  description = "IAM role ARN used by GitHub Actions for Demo API prod promotions"
  value       = try(aws_iam_role.github_prod_promote[0].arn, null)
}

output "github_oidc_provider_arn" {
  value = local.github_oidc_provider_arn
}
