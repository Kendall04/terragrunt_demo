terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.28, < 7.0" }
  }
}
variable "config_path" { type = string }
variable "lambda_zip" { type = string }
variable "enabled" {
  type    = bool
  default = false
}
variable "alarm_notices_enabled" {
  type    = bool
  default = false
}
locals {
  config              = jsondecode(file(var.config_path))
  name                = local.config.deployment
  archive_bucket_name = "snt-${lower(local.name)}-${local.config.account}-${local.config.region}"
  roles               = toset(["worker", "ingestion", "watchdog", "cleanup"])
  handlers = {
    worker = "Tick", ingestion = "Ingest", watchdog = "Watchdog", cleanup = "Cleanup"
  }
  schedules      = { worker = "rate(1 minute)", watchdog = "rate(1 minute)", cleanup = "rate(1 minute)" }
  modes          = { worker = "tick", watchdog = "watchdog", cleanup = "cleanup" }
  producers      = toset(flatten([for m in local.config.monitors : m.sources if contains(["report", "sql-backup"], m.kind)]))
  actions        = try(local.config.notificationsEnabled, false) && try(local.config.topicArn, null) != null ? [local.config.topicArn] : []
  archive_prefix = "sentinel/v3/*"
  read_actions = distinct(flatten([for m in local.config.monitors : lookup({
    ec2        = ["ec2:DescribeInstanceStatus"], asg = ["autoscaling:DescribeAutoScalingGroups"],
    alarm      = ["cloudwatch:DescribeAlarms"], aws-backup = ["backup:ListRecoveryPointsByResource"],
    rds-backup = ["rds:DescribeDBInstances"], aurora-backup = ["rds:DescribeDBClusters"]
  }, m.kind, [])]))
}
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
resource "aws_dynamodb_table" "state" {
  name                        = "${local.name}-state"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "PK"
  range_key                   = "SK"
  deletion_protection_enabled = var.retirement == null
  dynamic "attribute" {
    for_each = toset(["PK", "SK", "DuePK", "DueSK", "ActivePK", "ActiveSK", "CleanPK", "CleanSK"])
    content {
      name = attribute.value
      type = "S"
    }
  }
  dynamic "global_secondary_index" {
    for_each = { Due = "Due", Active = "Active", Cleanup = "Clean" }
    content {
      name            = global_secondary_index.key
      hash_key        = "${global_secondary_index.value}PK"
      range_key       = "${global_secondary_index.value}SK"
      projection_type = "ALL"
    }
  }
  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 1
  }
  server_side_encryption { enabled = true }
  lifecycle {
    precondition {
      condition     = data.aws_caller_identity.current.account_id == local.config.account && data.aws_region.current.region == local.config.region
      error_message = "Provider account/region must match the validated Sentinel manifest."
    }
  }
}
resource "aws_s3_bucket" "archive" {
  bucket        = local.archive_bucket_name
  force_destroy = false
  lifecycle {
    precondition {
      condition = length(local.archive_bucket_name) <= 63 && can(regex("^snt-[a-z0-9][a-z0-9-]*[a-z0-9]$", local.archive_bucket_name)) && alltrue([
        for suffix in ["-s3alias", "--ol-s3", "--x-s3", "--table-s3", "-an"] : !endswith(local.archive_bucket_name, suffix)
      ])
      error_message = "Sentinel archive requires the snt- namespace and a valid shared-namespace S3 name, at most 63 characters; no truncation or legacy bucket fallback."
    }
  }
}
resource "aws_s3_bucket_public_access_block" "archive" {
  bucket                  = aws_s3_bucket.archive.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id
  versioning_configuration { status = "Enabled" }
}


resource "aws_sqs_queue" "dead" {
  for_each                  = toset(["reports", "operations"])
  name                      = "${local.name}-${each.key}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "reports" {
  name                       = "${local.name}-reports"
  visibility_timeout_seconds = 360
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dead["reports"].arn, maxReceiveCount = 5 })
}
resource "aws_cloudwatch_event_bus" "reports" { name = local.name }
resource "aws_cloudwatch_event_rule" "reports" {
  name           = "${local.name}-reports"
  event_bus_name = aws_cloudwatch_event_bus.reports.name
  state          = var.enabled ? "ENABLED" : "DISABLED"
  event_pattern  = jsonencode({ source = [for p in local.producers : "sentinel.report.${p}"], "detail-type" = ["Sentinel Observation v1"], account = [local.config.account], region = [local.config.region] })
  count          = length(local.producers) > 0 ? 1 : 0
}
resource "aws_cloudwatch_event_target" "reports" {
  count          = length(local.producers) > 0 ? 1 : 0
  rule           = aws_cloudwatch_event_rule.reports[0].name
  event_bus_name = aws_cloudwatch_event_bus.reports.name
  arn            = aws_sqs_queue.reports.arn
  dead_letter_config { arn = aws_sqs_queue.dead["operations"].arn }
  retry_policy {
    maximum_event_age_in_seconds = 3600
    maximum_retry_attempts       = 3
  }
}
resource "aws_sqs_queue_policy" "reports" {
  count     = length(local.producers) > 0 ? 1 : 0
  queue_url = aws_sqs_queue.reports.id
  policy    = jsonencode({ Version = "2012-10-17", Statement = length(local.producers) > 0 ? [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sqs:SendMessage", Resource = aws_sqs_queue.reports.arn, Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudwatch_event_rule.reports[0].arn } } }] : [] })
}
resource "aws_iam_role" "runtime" {
  for_each             = local.roles
  name                 = "${local.name}-${each.key}"
  permissions_boundary = aws_iam_policy.ecs_boundary[each.key].arn
  tags                 = { Project = local.config.project, Deployment = local.name, ManagedBy = "Terraform", Component = "sentinel-portable" }
  assume_role_policy   = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_cloudwatch_log_group" "runtime" {
  for_each          = local.roles
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = 30
}
locals {
  ecs_runtime_policies = { for component in local.roles : component => jsonencode({ Version = "2012-10-17", Statement = concat([
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.runtime[component].arn}:*" },
    { Effect = "Allow", Action = component == "watchdog" ? ["dynamodb:GetItem"] : ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:ConditionCheckItem"], Resource = [aws_dynamodb_table.state.arn, "${aws_dynamodb_table.state.arn}/index/*"] },
    { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.dead["operations"].arn }
    ], component == "ingestion" ? [
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.reports.arn }
    ] : [], component == "worker" ? [
    { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject"], Resource = "${aws_s3_bucket.archive.arn}/${local.archive_prefix}" }
    ] : [], component == "worker" ? [local.archive_kms_statement
    ] : [], component == "worker" && length(local.read_actions) > 0 ? [
    { Effect = "Allow", Action = local.read_actions, Resource = "*", Condition = { StringEquals = { "aws:RequestedRegion" = local.config.region } } }
    ] : [], component == "worker" && length([for m in local.config.monitors : m if m.kind == "s3-object"]) > 0 ? [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = [for m in local.config.monitors : "${m.resource}/${m.selector}" if m.kind == "s3-object"] }
    ] : [], component == "worker" && length(local.actions) > 0 ? [
    { Effect = "Allow", Action = ["sns:Publish"], Resource = local.actions }
    ] : [], component == "worker" && length(local.actions) > 0 ? [local.notice_kms_statement
  ] : []) }) }
}
resource "aws_iam_role_policy" "runtime" {
  for_each = local.roles
  role     = aws_iam_role.runtime[each.key].id
  policy   = local.ecs_runtime_policies[each.key]
}
resource "aws_lambda_function" "runtime" {
  for_each                       = local.roles
  function_name                  = "${local.name}-${each.key}"
  role                           = aws_iam_role.runtime[each.key].arn
  filename                       = var.lambda_zip
  source_code_hash               = filebase64sha256(var.lambda_zip)
  runtime                        = "dotnet10"
  architectures                  = ["x86_64"]
  handler                        = "Ecs.Backup.Portable.Host::Ecs.Backup.Portable.Host.Function::${local.handlers[each.key]}"
  timeout                        = 60
  memory_size                    = 512
  reserved_concurrent_executions = each.key == "ingestion" ? 2 : 1
  publish                        = true
  environment { variables = { SENTINEL_TABLE = aws_dynamodb_table.state.name, SENTINEL_ARCHIVE = aws_s3_bucket.archive.id, SENTINEL_QUEUE_ARN = aws_sqs_queue.reports.arn } }
  depends_on = [aws_iam_role_policy.runtime]
}
resource "aws_lambda_alias" "live" {
  for_each         = local.roles
  name             = "live"
  function_name    = aws_lambda_function.runtime[each.key].function_name
  function_version = aws_lambda_function.runtime[each.key].version
}
resource "aws_lambda_event_source_mapping" "reports" {
  event_source_arn        = aws_sqs_queue.reports.arn
  function_name           = aws_lambda_alias.live["ingestion"].arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
  enabled                 = var.enabled
}
resource "aws_cloudwatch_event_rule" "tick" {
  for_each            = local.schedules
  name                = "${local.name}-${each.key}"
  schedule_expression = each.value
  state               = var.enabled ? "ENABLED" : "DISABLED"
}
resource "aws_cloudwatch_event_target" "tick" {
  for_each = local.schedules
  rule     = aws_cloudwatch_event_rule.tick[each.key].name
  arn      = aws_lambda_alias.live[each.key].arn
  input    = jsonencode({ Deployment = local.name, Mode = local.modes[each.key] })
  retry_policy {
    maximum_event_age_in_seconds = 60
    maximum_retry_attempts       = 0
  }
  dead_letter_config { arn = aws_sqs_queue.dead["operations"].arn }
}
resource "aws_lambda_permission" "tick" {
  for_each       = local.schedules
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.runtime[each.key].function_name
  qualifier      = aws_lambda_alias.live[each.key].name
  principal      = "events.amazonaws.com"
  source_arn     = aws_cloudwatch_event_rule.tick[each.key].arn
  source_account = local.config.account
}
resource "aws_lambda_function_event_invoke_config" "runtime" {
  for_each                     = local.schedules
  function_name                = aws_lambda_function.runtime[each.key].function_name
  qualifier                    = aws_lambda_alias.live[each.key].name
  maximum_event_age_in_seconds = 60
  maximum_retry_attempts       = 0
  destination_config {
    on_failure { destination = aws_sqs_queue.dead["operations"].arn }
  }
}
resource "aws_sqs_queue_policy" "operations" {
  queue_url = aws_sqs_queue.dead["operations"].id
  policy    = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "events.amazonaws.com" }, Action = "sqs:SendMessage", Resource = aws_sqs_queue.dead["operations"].arn, Condition = { ArnEquals = { "aws:SourceArn" = concat([for r in aws_cloudwatch_event_rule.tick : r.arn], aws_cloudwatch_event_rule.reports[*].arn) } } }] })
}
resource "aws_cloudwatch_log_metric_filter" "health" {
  name           = "${local.name}-health"
  log_group_name = aws_cloudwatch_log_group.runtime["watchdog"].name
  pattern        = "{ $.type = \"SentinelHealth\" }"
  metric_transformation {
    name      = "Health"
    namespace = "Sentinel/${local.name}"
    value     = "$.healthy"
  }
}
resource "aws_cloudwatch_metric_alarm" "health" {
  alarm_name          = "${local.name}-health"
  namespace           = "Sentinel/${local.name}"
  metric_name         = "Health"
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 3
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
  actions_enabled     = var.enabled && var.alarm_notices_enabled
  alarm_actions       = local.actions
  ok_actions          = local.actions
}
resource "aws_cloudwatch_metric_alarm" "dead" {
  for_each            = aws_sqs_queue.dead
  alarm_name          = "${local.name}-${each.key}-dead"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = each.value.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  actions_enabled     = var.enabled && var.alarm_notices_enabled
  alarm_actions       = local.actions
}
resource "aws_cloudwatch_metric_alarm" "errors" {
  for_each            = local.roles
  alarm_name          = "${local.name}-${each.key}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.runtime[each.key].function_name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  actions_enabled     = var.enabled && var.alarm_notices_enabled
  alarm_actions       = local.actions
}
output "event_bus_arn" { value = aws_cloudwatch_event_bus.reports.arn }
output "table_name" { value = aws_dynamodb_table.state.name }
output "archive_bucket" { value = aws_s3_bucket.archive.id }
output "producer_policies" {
  description = "Attach each policy only to its authorized producer role; the source is bound to that identity."
  value       = { for producer in local.producers : producer => jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "events:PutEvents", Resource = aws_cloudwatch_event_bus.reports.arn, Condition = { StringEquals = { "events:source" = "sentinel.report.${producer}", "events:detail-type" = "Sentinel Observation v1" } } }] }) }
}

resource "aws_iam_policy" "ecs_boundary" {
  for_each = local.roles
  name     = "${local.name}-${each.key}-boundary"
  policy   = local.ecs_runtime_policies[each.key]
  lifecycle {
    precondition {
      condition     = each.key != "worker" || (data.aws_kms_key.notices.key_manager == "CUSTOMER" && data.aws_kms_key.notices.enabled && data.aws_kms_key.notices.key_spec == "SYMMETRIC_DEFAULT" && data.aws_kms_key.notices.key_usage == "ENCRYPT_DECRYPT" && data.aws_kms_key.notices.aws_account_id == local.config.account && data.aws_kms_key.notices.arn == var.security.notice_kms_key_arn)
      error_message = "DescribeKey must prove the exact enabled same-account customer symmetric notice key."
    }
  }
}
