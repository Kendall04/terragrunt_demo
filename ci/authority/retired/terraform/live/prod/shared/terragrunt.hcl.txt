# Inherit environment settings (remote state, provider, locals)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# ============================================
# Terraform source for the "shared" layer
# - KMS key and ECR repositories shared by apps
# ============================================
terraform {
  source = "../../../infra/shared"
}

# ============================================
# Inputs for the shared module
# (no direct dependency on VPC resources here)
# ============================================
inputs = {
  env = local.parent.locals.env

  github_owner = local.parent.locals.github_owner
  github_repo  = local.parent.locals.github_repo
  # Account singleton consumer: adopt the GitHub OIDC provider created by dev/shared.
  create_github_oidc_provider = false

  tf_state_bucket_name     = local.parent.locals.tf_state_bucket
  tf_state_lock_table_name = local.parent.locals.tf_state_table

  project = local.parent.locals.project_name

  alert_email = local.parent.locals.alert_email

  # Same-account demo: release artifacts are environment-neutral and created by
  # dev/shared to avoid bucket name collisions when prod is bootstrapped later.
  create_release_artifacts_bucket = false

  # Same-account demo: shared artifact ECR is environment-neutral and created by
  # dev/shared to avoid duplicate repository creation when prod is bootstrapped.
  create_shared_artifact_ecr_repository = false
}
