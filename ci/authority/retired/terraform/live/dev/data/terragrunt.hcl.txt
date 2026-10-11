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
# - db_instance_sg_id: SG created for the DB instance in global
# =====================================================
dependency "global" {
  config_path = "../global"

  mock_outputs = {
    private_subnet_ids = ["subnet-aaa", "subnet-bbb"]
    db_instance_sg_id  = "sg-000000"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
  mock_outputs_merge_with_state           = true
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

# ---------- SECRETS ----------
# Secret containers and KMS key used by the SQL Server bootstrap user data.
dependency "secrets" {
  config_path = "../secrets"

  mock_outputs = {
    sql_sa_secret_arn  = "arn:aws:secretsmanager:region:acct:secret:fake-sa"
    sql_app_secret_arn = "arn:aws:secretsmanager:region:acct:secret:fake-app"
    secret_kms_key_arn = "arn:aws:kms:region:acct:key/fake"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
  mock_outputs_merge_with_state           = true
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
  env        = local.parent.locals.env
  aws_region = local.parent.locals.aws_region
  project    = local.parent.locals.project_name

  # From global
  private_subnet_ids = dependency.global.outputs.private_subnet_ids
  db_instance_sg_id  = dependency.global.outputs.db_instance_sg_id

  alerts_topic_arn = dependency.shared.outputs.alerts_topic_arn

  # From secrets
  sql_sa_secret_arn  = dependency.secrets.outputs.sql_sa_secret_arn
  sql_app_secret_arn = dependency.secrets.outputs.sql_app_secret_arn
  secret_kms_key_arn = dependency.secrets.outputs.secret_kms_key_arn
}
