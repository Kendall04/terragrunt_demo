###############################################################
# Local environment settings (used across all child modules)
###############################################################
locals {
  # Global environment name (dev/prod) – overridable via env var 
  env = get_env("TG_ENV", "prod")

  # Default AWS region – overridable via env var
  aws_region = get_env("AWS_REGION", "us-east-1")

  # Local AWS CLI profile – overridable via env var
  aws_profile = get_env("AWS_PROFILE", "terraform-lab")

  tf_state_bucket = get_env("TF_STATE_BUCKET", "tfstate-demo-${local.env}")
  tf_state_table  = get_env("TF_STATE_TABLE", "tfstate-locks")

  github_owner = "Kendall04"
  github_repo  = "terragrunt_demo_lab" 

  project_name = "demo"

  alert_email = "kendallffernandez@gmail.com"
}

###############################################################
# Remote backend configuration (S3 + DynamoDB state locking)
###############################################################
remote_state {
  backend = "s3"

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }

  config = {
    bucket         = local.tf_state_bucket
    dynamodb_table = local.tf_state_table
    region         = local.aws_region

    key = "${path_relative_to_include()}/terraform.tfstate"
  }
}

###############################################################
# Global AWS provider for all modules
###############################################################
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite"

  contents = <<-EOT
    provider "aws" {
      region  = "${local.aws_region}"
    }

    data "aws_region" "current" {}
  EOT
}

###############################################################
# Global inputs injected into every Terraform module
###############################################################
inputs = {
  env         = local.env
  aws_region  = local.aws_region

  github_owner = local.github_owner
  github_repo  = local.github_repo

  project = local.project_name

  alert_email = local.alert_email
}
