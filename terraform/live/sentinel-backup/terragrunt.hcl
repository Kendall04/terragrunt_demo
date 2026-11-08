# Isolated administrator-owned integration root; not an ordinary TARGET apply.
# No credentials/recipient/backend defaults. Files contain metadata only, no secret values.
terraform {
  source = "../../infra/sentinel-backup"
}
remote_state {
  backend = "s3"
  config = {
    bucket               = get_env("SENTINEL_STATE_BUCKET")
    key                  = "sentinel-backup/${get_env("SENTINEL_STATE_ID")}/terraform.tfstate"
    region               = get_env("SENTINEL_STATE_REGION")
    encrypt              = true
    use_lockfile         = true
    workspace_key_prefix = "sentinel-backup/${get_env("SENTINEL_STATE_ID")}/workspaces"
  }
}
inputs = jsondecode(file(get_env("SENTINEL_INPUTS_FILE")))
