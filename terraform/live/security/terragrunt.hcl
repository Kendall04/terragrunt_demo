# Admin-only neutral root. Backend must already be separately bootstrapped.
# Bucket/region are external partial-backend inputs; see the security root README.
terraform {
  source = "../../infra/security"
}

inputs = {
  aws_account_id               = get_env("E1_SECURITY_ACCOUNT_ID")
  aws_region                   = get_env("E1_SECURITY_AWS_REGION")
  security_admin_principal_arn = get_env("E1_SECURITY_ADMIN_PRINCIPAL_ARN")
}
