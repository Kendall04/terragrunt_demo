# Inherit environment settings (remote state, provider, locals)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# ---------- SHARED ----------
# KMS key used to encrypt Secrets Manager secret values.
dependency "shared" {
  config_path = "../shared"

  mock_outputs = {
    kms_key_arn = "arn:aws:kms:region:acct:key/fake"
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
  mock_outputs_merge_with_state           = true
}

terraform {
  source = "../../../infra/secrets"
}

inputs = {
  env     = local.parent.locals.env
  project = local.parent.locals.project_name

  kms_key_id = dependency.shared.outputs.kms_key_arn
}
