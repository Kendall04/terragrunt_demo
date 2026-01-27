# Inherit base Terragrunt settings (remote state, provider, env, region, profile)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# =====================================================
# Dependency: read networking outputs from "global"
# - private_subnet_ids: where the EC2 DB will live (no public IP)
# - vpc_id: used for SG or future networking
# - db_instance_sg_id: SG created for the DB instance in global
# =====================================================
dependency "global" {
  config_path = "../global"

  mock_outputs = {
    private_subnet_ids = ["subnet-aaa", "subnet-bbb"]
    vpc_id             = "vpc-000000"
    db_instance_sg_id  = "sg-000000"
  }

  mock_outputs_merge_with_state = true
}

# ---------- SHARED ----------
# Alerts Topic ARN
dependency "shared" {
  config_path = "../shared"

  mock_outputs = {
    alerts_topic_arn  = "arn:aws::region:acct:/fake"
  }

  mock_outputs_merge_with_state = true
}

# =====================================================
# Terraform source for the "data" layer
# - Private EC2 instance with SQL Server + Secrets Manager
# =====================================================
terraform {
  source = "../../../infra/data"
}

# =====================================================
# Inputs for the data module
# =====================================================
inputs = {
  env         = local.parent.locals.env
  aws_region  = local.parent.locals.aws_region
  project = local.parent.locals.project_name
  
  # From global
  private_subnet_ids = dependency.global.outputs.private_subnet_ids
  vpc_id             = dependency.global.outputs.vpc_id
  db_instance_sg_id  = dependency.global.outputs.db_instance_sg_id

  alerts_topic_arn = dependency.shared.outputs.alerts_topic_arn
}
