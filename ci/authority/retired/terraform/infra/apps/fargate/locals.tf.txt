data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  name = "${var.project}-${var.env}-app"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }

  container_bootstrap_image = var.bootstrap_image

  api_blue_name  = "${local.name}-api-blue"
  api_green_name = "${local.name}-api-green"

  scale_down_lambda_name = "demo-${var.env}-scale-down-old-color"
  scale_down_rule_name   = "demo-${var.env}-scale-down-old-color-rule"
}
