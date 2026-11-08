# Optional external backup verifier. Reuses this owner's bus and monitor identities.
variable "backup_retention_enabled" {
  type    = bool
  default = false
  validation {
    condition     = !var.backup_retention_enabled || try(var.backup_observer.prefix == "terragrunt-demo/dev/sql-backups/v2-20261106", false)
    error_message = "Retention may enroll only the new approved DEV prefix."
  }
}
variable "backup_observer" {
  type = object({
    zip_path = string, zip_sha256 = string, bucket = string, prefix = string,
    database = string, backup_key_arn = string, text_key_arn = string, expires_at = string
  })
  default = null
  validation {
    condition = var.backup_observer == null ? true : (
      var.backup_observer.bucket == "terragrunt-demo-sql-backup-341936017254-fa48a32dc9" &&
      can(regex("^terragrunt-demo/dev/sql-backups/v2-[0-9]{8}$", var.backup_observer.prefix)) &&
      var.backup_observer.database == "demodb" &&
      var.backup_observer.backup_key_arn == var.security.archive_kms_key_arn &&
      can(regex("^arn:aws:kms:us-east-1:341936017254:key/[a-f0-9-]{36}$", var.backup_observer.text_key_arn)) &&
      filesha256(var.backup_observer.zip_path) == var.backup_observer.zip_sha256 &&
      try(timecmp(var.backup_observer.expires_at, var.security.starts_at) > 0 && timecmp(var.backup_observer.expires_at, var.security.expires_at) <= 0, false)
    )
    error_message = "Exact DEV backup namespace, keys, package and expiry required."
  }
}
locals {
  backup_observers = var.backup_observer == null ? {} : { sql = var.backup_observer }
  observer_name    = "${local.config.deployment}-backup-observer"
  observer_policies = { for name, c in local.backup_observers : name => jsonencode({
    Version = "2012-10-17", Statement = concat([
      { Effect = "Allow", Action = "s3:ListBucket", Resource = "arn:aws:s3:::${c.bucket}", Condition = { StringEquals = { "s3:prefix" = "${c.prefix}/runs/" }, NumericLessThanEquals = { "s3:max-keys" = "1000" }, DateLessThan = { "aws:CurrentTime" = c.expires_at } } },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = "arn:aws:s3:::${c.bucket}/${c.prefix}/runs/*", Condition = { DateLessThan = { "aws:CurrentTime" = c.expires_at } } },
      { Effect = "Allow", Action = "kms:Decrypt", Resource = c.backup_key_arn, Condition = { StringEquals = { "kms:ViaService" = "s3.${local.config.region}.amazonaws.com", "kms:CallerAccount" = local.config.account }, StringLike = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::${c.bucket}/${c.prefix}/runs/*" }, DateLessThan = { "aws:CurrentTime" = c.expires_at } } },
      { Effect = "Allow", Action = "events:PutEvents", Resource = module.runtime.event_bus_arn, Condition = { StringEquals = { "events:source" = "sentinel.report.sql-observer", "events:detail-type" = "Sentinel Observation v1" }, DateLessThan = { "aws:CurrentTime" = c.expires_at } } },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:${local.config.region}:${local.config.account}:log-group:/aws/lambda/${local.observer_name}:*" }
      ], local.nat_observer_statements, var.backup_retention_enabled ? [
      { Effect = "Allow", Action = ["s3:ListBucketVersions"], Resource = "arn:aws:s3:::${c.bucket}", Condition = { StringEquals = { "s3:prefix" = "${c.prefix}/runs/" }, NumericLessThanEquals = { "s3:max-keys" = "1000" }, DateLessThan = { "aws:CurrentTime" = c.expires_at } } },
      { Effect = "Allow", Action = ["s3:GetObjectVersionTagging", "s3:PutObjectVersionTagging"], Resource = "arn:aws:s3:::${c.bucket}/${c.prefix}/runs/*", Condition = { DateLessThan = { "aws:CurrentTime" = c.expires_at } } }
    ] : [])
  }) }
}
resource "aws_iam_policy" "backup_observer_boundary" {
  for_each = local.backup_observers
  name     = "${local.observer_name}-boundary"
  policy   = local.observer_policies[each.key]
}
resource "aws_iam_role" "backup_observer" {
  for_each             = local.backup_observers
  name                 = local.observer_name
  permissions_boundary = aws_iam_policy.backup_observer_boundary[each.key].arn
  assume_role_policy   = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
  tags                 = { Project = "demo", Environment = "dev", ManagedBy = "Terraform", Component = "sql-backup-observer" }
}
resource "aws_iam_role_policy" "backup_observer" {
  for_each = local.backup_observers
  role     = aws_iam_role.backup_observer[each.key].id
  name     = "read-backup-and-report"
  policy   = local.observer_policies[each.key]
}
resource "aws_cloudwatch_log_group" "backup_observer" {
  for_each          = local.backup_observers
  name              = "/aws/lambda/${local.observer_name}"
  retention_in_days = 7
}
resource "aws_lambda_function" "backup_observer" {
  for_each                       = local.backup_observers
  function_name                  = local.observer_name
  role                           = aws_iam_role.backup_observer[each.key].arn
  runtime                        = "python3.13"
  handler                        = "storage_observer.handler"
  filename                       = each.value.zip_path
  source_code_hash               = filebase64sha256(each.value.zip_path)
  timeout                        = 120
  memory_size                    = 256
  reserved_concurrent_executions = 1
  environment {
    variables = { BACKUP_OBSERVER_CONFIG = jsonencode({
      bucket       = each.value.bucket, prefix = each.value.prefix, database = each.value.database,
      backupKeyArn = each.value.backup_key_arn, textKeyArn = each.value.text_key_arn,
      maxBytes     = 536870912, expiresAt = each.value.expires_at, bus = local.config.deployment,
      monitors     = [for m in local.config.monitors : { id = m.id, kind = m.kind, resource = m.resource, generation = m.generation } if m.sources == ["sql-observer"]]
      nat          = local.nat_observer_config, retentionEnabled = var.backup_retention_enabled
    }) }
  }
  depends_on = [aws_cloudwatch_log_group.backup_observer, aws_iam_role_policy.backup_observer]
  lifecycle {
    precondition {
      condition     = length([for m in local.config.monitors : m if m.sources == ["sql-observer"] && contains(["sql-backup", "report"], m.kind)]) == 2 && length(local.config.monitors) == (var.nat_observer == null ? 2 : 3)
      error_message = "Preserve the two existing SQL monitor identities; no new journal identities."
    }
  }
}
resource "aws_lambda_function_event_invoke_config" "backup_observer" {
  for_each                     = local.backup_observers
  function_name                = aws_lambda_function.backup_observer[each.key].function_name
  maximum_retry_attempts       = 0
  maximum_event_age_in_seconds = 60
}
resource "aws_cloudwatch_event_rule" "backup_observer" {
  for_each            = local.backup_observers
  name                = local.observer_name
  schedule_expression = "rate(15 minutes)"
  state               = var.enabled ? "ENABLED" : "DISABLED"
}
resource "aws_cloudwatch_event_target" "backup_observer" {
  for_each = local.backup_observers
  rule     = aws_cloudwatch_event_rule.backup_observer[each.key].name
  arn      = aws_lambda_function.backup_observer[each.key].arn
  retry_policy {
    maximum_event_age_in_seconds = 60
    maximum_retry_attempts       = 0
  }
}
resource "aws_lambda_permission" "backup_observer" {
  for_each       = local.backup_observers
  statement_id   = "OwnBackupObservationSchedule"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.backup_observer[each.key].function_name
  principal      = "events.amazonaws.com"
  source_account = local.config.account
  source_arn     = aws_cloudwatch_event_rule.backup_observer[each.key].arn
}
output "backup_observer_role" { value = { for k, r in aws_iam_role.backup_observer : k => r.arn } }
