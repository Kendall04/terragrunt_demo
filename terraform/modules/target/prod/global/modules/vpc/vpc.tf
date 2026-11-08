resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name}-vpc" })
}
resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/${var.name}-flow-logs"
  retention_in_days = 30
  tags              = var.tags
}
resource "aws_flow_log" "vpc" {
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.vpc_flow_logs.arn
  iam_role_arn         = var.protected_flow_role

  traffic_type = "ALL" # aceptado, rechazado, todo

  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name}-vpc-flow-logs" })
}

variable "protected_flow_role" { type = string }
