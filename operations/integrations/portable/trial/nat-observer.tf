# Private probe A performs one fixed HTTPS request. Regional observer remains
# outside the VPC, so NAT loss cannot hide the worker or its notification path.
variable "nat_observer" {
  type    = object({ zip_path = string, zip_sha256 = string, route_table = string, allocation_id = string, expected_eip = string })
  default = null
  validation {
    condition = var.nat_observer == null ? true : (
      filesha256(var.nat_observer.zip_path) == var.nat_observer.zip_sha256 &&
      can(regex("^rtb-[a-f0-9]{17}$", var.nat_observer.route_table)) &&
      can(regex("^eipalloc-[a-f0-9]{17}$", var.nat_observer.allocation_id)) &&
      can(cidrhost("${var.nat_observer.expected_eip}/32", 0)) && var.backup_observer != null
    )
    error_message = "Exact DEV A routing, EIP and probe package required."
  }
}
locals {
  nat_probes        = var.nat_observer == null ? {} : { a = var.nat_observer }
  probe_name        = "${local.config.deployment}-nat-probe-a"
  probe_arn         = "arn:aws:lambda:${local.config.region}:${local.config.account}:function:${local.probe_name}"
  probe_eni_actions = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DescribeSubnets", "ec2:DeleteNetworkInterface", "ec2:AssignPrivateIpAddresses", "ec2:UnassignPrivateIpAddresses"]
  probe_policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = local.probe_eni_actions, Resource = "*", Condition = { StringEquals = { "aws:RequestedRegion" = local.config.region }, DateLessThan = { "aws:CurrentTime" = var.security.expires_at } } },
    { Effect = "Deny", Action = concat(local.probe_eni_actions, ["ec2:DetachNetworkInterface"]), Resource = "*", Condition = { ArnEquals = { "lambda:SourceFunctionArn" = local.probe_arn } } },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:${local.config.region}:${local.config.account}:log-group:/aws/lambda/${local.probe_name}:*" }
  ] })
  nat_observer_statements = var.nat_observer == null ? [] : [
    { Effect = "Allow", Action = ["ec2:DescribeInstances", "ec2:DescribeRouteTables", "ec2:DescribeAddresses", "autoscaling:DescribeAutoScalingGroups"], Resource = "*", Condition = { StringEquals = { "aws:RequestedRegion" = local.config.region }, DateLessThan = { "aws:CurrentTime" = var.security.expires_at } } },
    { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = local.probe_arn, Condition = { DateLessThan = { "aws:CurrentTime" = var.security.expires_at } } },
    { Effect = "Allow", Action = ["events:PutEvents"], Resource = module.runtime.event_bus_arn, Condition = { StringEquals = { "events:source" = "sentinel.report.nat-observer", "events:detail-type" = "Sentinel Observation v1" }, DateLessThan = { "aws:CurrentTime" = var.security.expires_at } } }
  ]
  nat_observer_config = var.nat_observer == null ? null : {
    asg          = "demo-dev-asg-nat-a", vpc = "vpc-00faf317507b09b03", publicSubnet = "subnet-0f05b78bed53665ce",
    lt           = "lt-04ab8d2ec1f975f96", routeTable = var.nat_observer.route_table,
    allocationId = var.nat_observer.allocation_id, expectedEip = var.nat_observer.expected_eip,
    probeArn     = local.probe_arn, expiresAt = var.security.expires_at, bus = local.config.deployment
  }
}
resource "aws_security_group" "nat_probe" {
  for_each    = local.nat_probes
  name        = local.probe_name
  description = "Bounded private HTTPS egress observation, no ingress"
  vpc_id      = "vpc-00faf317507b09b03"
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Fixed HTTPS probe endpoint"
  }
  tags = { Project = "demo", Environment = "dev", Component = "sentinel-nat-probe" }
}
resource "aws_iam_policy" "nat_probe_boundary" {
  for_each = local.nat_probes
  name     = "${local.probe_name}-boundary"
  policy   = local.probe_policy
}
resource "aws_iam_role" "nat_probe" {
  for_each             = local.nat_probes
  name                 = local.probe_name
  permissions_boundary = aws_iam_policy.nat_probe_boundary[each.key].arn
  assume_role_policy   = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "nat_probe" {
  for_each = local.nat_probes
  role     = aws_iam_role.nat_probe[each.key].id
  name     = "private-https-and-service-eni-only"
  policy   = local.probe_policy
}
resource "aws_cloudwatch_log_group" "nat_probe" {
  for_each          = local.nat_probes
  name              = "/aws/lambda/${local.probe_name}"
  retention_in_days = 7
}
resource "aws_lambda_function" "nat_probe" {
  for_each                       = local.nat_probes
  function_name                  = local.probe_name
  role                           = aws_iam_role.nat_probe[each.key].arn
  runtime                        = "python3.13"
  handler                        = "nat_probe.handler"
  filename                       = each.value.zip_path
  source_code_hash               = filebase64sha256(each.value.zip_path)
  timeout                        = 10
  memory_size                    = 128
  reserved_concurrent_executions = 1
  environment { variables = { EXPIRES_AT = var.security.expires_at } }
  vpc_config {
    subnet_ids         = ["subnet-0cc3c5f388072d13d"]
    security_group_ids = [aws_security_group.nat_probe[each.key].id]
  }
  depends_on = [aws_iam_role_policy.nat_probe, aws_cloudwatch_log_group.nat_probe]
}
resource "aws_cloudwatch_event_rule" "nat_observer" {
  for_each            = local.nat_probes
  name                = "${local.config.deployment}-nat-observer"
  schedule_expression = "rate(1 minute)"
  state               = var.enabled ? "ENABLED" : "DISABLED"
}
resource "aws_cloudwatch_event_target" "nat_observer" {
  for_each = local.nat_probes
  rule     = aws_cloudwatch_event_rule.nat_observer[each.key].name
  arn      = aws_lambda_function.backup_observer["sql"].arn
  retry_policy {
    maximum_event_age_in_seconds = 60
    maximum_retry_attempts       = 0
  }
}
resource "aws_lambda_permission" "nat_observer" {
  for_each       = local.nat_probes
  statement_id   = "OwnNatObservationSchedule"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.backup_observer["sql"].function_name
  principal      = "events.amazonaws.com"
  source_account = local.config.account
  source_arn     = aws_cloudwatch_event_rule.nat_observer[each.key].arn
}
