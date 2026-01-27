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
  env         = local.parent.locals.env

  github_owner = local.parent.locals.github_owner
  github_repo  = local.parent.locals.github_repo
  create_github_oidc_provider = true

  project = local.parent.locals.project_name

  alert_email = local.parent.locals.alert_email
}
