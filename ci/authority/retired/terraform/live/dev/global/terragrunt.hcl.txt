# ============================================
# Inherit common settings from the parent root
# (remote state, provider, env, region, profile)
# ============================================
include "env" {
  path = find_in_parent_folders("root.hcl")
}

# Read parent locals (env)
locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# ---------- SHARED ----------
# Alerts Topic ARN
dependency "shared" {
  config_path = "../shared"

  mock_outputs = {
    alerts_topic_arn = "arn:aws::region:acct:/fake"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
  mock_outputs_merge_with_state           = true
}

# ============================================
# Terraform source for the "global" layer
# - VPC, subnets, NAT instances, ALB, SGs, etc.
# ============================================
terraform {
  source = "../../../infra//global"
}

# ============================================
# Module inputs for the global layer
# ============================================
inputs = {
  env     = local.parent.locals.env
  project = local.parent.locals.project_name

  alerts_topic_arn = dependency.shared.outputs.alerts_topic_arn
}
