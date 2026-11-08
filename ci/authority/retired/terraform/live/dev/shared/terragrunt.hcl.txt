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
  # Account singleton owner: create the GitHub OIDC provider here only.
  create_github_oidc_provider = true

  tf_state_bucket_name     = local.parent.locals.tf_state_bucket
  tf_state_lock_table_name = local.parent.locals.tf_state_table

  project = local.parent.locals.project_name

  alert_email = local.parent.locals.alert_email

  # Account-level artifact bucket. Dev/shared owns creation in the same-account
  # demo; prod/shared references the deterministic name without creating it.
  create_release_artifacts_bucket = true

  # Account-level artifact repository. Dev/shared owns creation in this
  # same-account demo; prod/shared references the deterministic name.
  create_shared_artifact_ecr_repository = true
}
