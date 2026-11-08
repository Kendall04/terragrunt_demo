data "archive_file" "scale_down_old_color_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/scale_down_old_color.py"
  output_path = "${path.module}/lambda/scale_down_old_color.zip"
}

module "scale_down_lambda" {
  source = "../../modules/lambda_function"

  name = local.scale_down_lambda_name
  tags = local.tags

  role_arn = aws_iam_role.scale_down_lambda.arn

  # Deploy from local zip file 
  filename = data.archive_file.scale_down_old_color_zip.output_path

  runtime = "python3.12"
  handler = "scale_down_old_color.lambda_handler"

  memory_mb   = 128
  timeout_sec = 30

  # Optional env; cluster can be passed via payload,
  # but we can also have it here as a default.
  environment_variables = {
    CLUSTER_ARN        = var.cluster_arn
    SERVICE_BLUE_NAME  = module.demo_api_blue.service_name
    SERVICE_GREEN_NAME = module.demo_api_green.service_name
    LISTENER_ARN       = var.alb_listener_arn
    TG_BLUE_ARN        = var.demo_blue_tg_arn
    TG_GREEN_ARN       = var.demo_green_tg_arn
    EVENT_RULE_NAME    = local.scale_down_rule_name
  }

  invoke_permissions = [
    {
      statement_id = "AllowEventBridgeScaleDown"
      principal    = "events.amazonaws.com"
      source_arn   = "arn:aws:events:${var.aws_region}:${local.account_id}:rule/${local.scale_down_rule_name}"
    }
  ]
}
