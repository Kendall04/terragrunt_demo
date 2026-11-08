# ==========================================================
# KMS MODULE
# ==========================================================
# Creates a customer-managed KMS key used for encryption operations
# across the demo microservice. This key supports Encrypt/Decrypt
# actions for sensitive payloads stored in the database or handled
# by internal services. The alias is attached to simplify referencing
# the key across environments.
module "kms" {
  source = "./modules/kms_key"

  name        = "${local.name}-kms"
  alias       = "${var.env}-kms-service"
  description = "KMS for the encryption microservice"
  tags        = local.tags
}

# ==========================================================
# ECR MODULE
# ==========================================================
# Creates one or more ECR repositories for the demo microservices.
# - scan_on_push: enables vulnerability scanning
# - immutable_tags: prevents image tag overwrites (disabled here)
# - lifecycle_keep: controls how many untagged images are kept
# Useful for CI/CD pipelines and image versioning.
module "ecr" {
  source = "./modules/ecr"

  repo_names = concat(
    [
      "${local.name}-demo-ms",
    ],
    var.create_shared_artifact_ecr_repository ? [local.shared_artifact_ecr_repository_name] : [],
  )

  scan_on_push   = true
  immutable_tags = true
  lifecycle_keep = 15
  tags           = local.tags
}

# ==========================================================
# IAM GITHUB OIDC MODULE
# ==========================================================
# Provisions an IAM role dedicated to GitHub Actions CI/CD.
# This role uses an OpenID Connect (OIDC) trust relationship
# with GitHub’s identity provider, allowing secure token-based
# access without long-lived AWS credentials.
#
# The attached inline policy grants the minimum required 
# permissions for Terraform/Terragrunt backend operations:
# - Read/Write access to the S3 remote state bucket
# - CRUD operations on the DynamoDB state lock table 
module "iam_github" {
  source = "./modules/iam_github"

  name    = "${local.name}-github"
  project = var.project
  env     = var.env

  github_owner = var.github_owner
  github_repo  = var.github_repo

  create_github_oidc_provider = var.create_github_oidc_provider
  github_oidc_provider_arn    = var.github_oidc_provider_arn

  tf_state_bucket_name     = var.tf_state_bucket_name
  tf_state_lock_table_name = var.tf_state_lock_table_name

  release_artifacts_bucket_name       = local.release_artifacts_bucket_name
  shared_artifact_ecr_repository_name = local.shared_artifact_ecr_repository_name
}




# Reason:
# - Using AWS-managed SNS KMS key (alias/aws/sns) is acceptable for this demo
#    This environment does not require advanced key management, rotation policies
#    or fine-grained CMK permissions. Encryption at rest is still enabled and meets
#    the intended security posture for a non-production workload
#tfsec:ignore:aws-sns-topic-encryption-use-cmk
resource "aws_sns_topic" "alerts" {
  name              = "${local.name}-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = local.tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
