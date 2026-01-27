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

  ecr_repo_demo = "demo-${var.env}-shared-demo-ms"
  ecr_repo_base = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.ecr_repo_demo}"

  container_image = var.image_digest != "" ? "${local.ecr_repo_base}@${var.image_digest}" : "${local.ecr_repo_base}:latest"

  api_blue_name  = "${local.name}-api-blue"
  api_green_name = "${local.name}-api-green"

  scale_down_lambda_name = "demo-${var.env}-scale-down-old-color"
  scale_down_rule_name   = "demo-${var.env}-scale-down-old-color-rule"
}
