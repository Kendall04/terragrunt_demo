# Inherit base config (remote state, provider, env, region, profile)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# =====================================================
# Dependency: read outputs from "global"
# - We need: ALB listener, private subnets and SG for VPC Link
# =====================================================
dependency "global" {
  config_path = "../global"

  # Mock values used only for the very first plan, before global exists
  mock_outputs = {
    alb_listener_arn   = "arn:aws:elasticloadbalancing:region:acct:listener/mock"
    private_subnet_ids = ["subnet-aaa", "subnet-bbb"]
    vpc_link_sg_id     = "sg-aaaa"
  }

  # When state exists, merge real outputs with mock values
  mock_outputs_merge_with_state = true
}

# =====================================================
# Terraform source for the "edge" layer
# - API Gateway HTTP + VPC Link integration to internal ALB
# =====================================================
terraform {
  source = "../../../infra/edge"
}

# =====================================================
# Inputs for the edge module
# =====================================================
inputs = {
  env         = local.parent.locals.env
  project = local.parent.locals.project_name

  # From global: ALB listener used by API Gateway VPC Link
  alb_listener_arn   = dependency.global.outputs.alb_listener_arn
  private_subnet_ids = dependency.global.outputs.private_subnet_ids
  vpc_link_sg_id     = dependency.global.outputs.vpc_link_sg_id
  # CORS is disabled by default. Add explicit trusted origins when needed.
  cors_allowed_origins = []
}
