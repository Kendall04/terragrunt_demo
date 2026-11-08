data "aws_region" "current" {}

# CloudWatch Log Group for ECS container logs
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/ecs/${var.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}
