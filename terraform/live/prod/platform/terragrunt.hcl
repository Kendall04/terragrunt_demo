# Inherit environment settings (remote state, provider, locals)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  # Parent config exposes env, region and profile
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# ============================================
# Terraform source for the "platform" layer
# - ECS cluster + capacity providers (if enabled)
# ============================================
terraform {
  source = "../../../infra/platform"
}

# ============================================
# Inputs sent to the platform module
# ============================================
inputs = {
  env         = local.parent.locals.env
  project = local.parent.locals.project_name
}
