terraform { required_version = ">= 1.13.4, < 2.0" }
variable "config_path" { type = string }
variable "lambda_zip" { type = string }
variable "security" {
  nullable = false
  type     = object({ archive_kms_key_arn = string, notice_kms_key_arn = string, access_log_bucket = string, starts_at = string, expires_at = string })
  validation {
    condition     = alltrue([for key in [var.security.archive_kms_key_arn, var.security.notice_kms_key_arn] : can(regex("^arn:aws:kms:${local.config.region}:${local.config.account}:key/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", key))]) && var.security.archive_kms_key_arn != var.security.notice_kms_key_arn
    error_message = "Two distinct explicit same-account regional CMK ARNs required."
  }
}
variable "retirement" {
  type    = object({ table_arn = string, approval_sha256 = string, acknowledgement = string })
  default = null
}
variable "alarm_notices_enabled" {
  type    = bool
  default = false
}
variable "enabled" {
  type    = bool
  default = false
}
variable "notice_email" {
  type = string
}
variable "package_manifest_path" {
  type = string
  validation {
    condition     = try(jsondecode(file(var.package_manifest_path)).zipSha256 == filesha256(var.lambda_zip) && jsondecode(file(var.package_manifest_path)).configSha256 == filesha256(var.config_path) && jsondecode(file(var.package_manifest_path)).upstreamCommit == "b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828" && jsondecode(file(var.package_manifest_path)).runtimeFactory == "Ecs.Backup.Portable.Host::Ecs.Backup.Portable.Host.Function" && jsondecode(file(var.package_manifest_path)).syntheticTrial == true, false)
    error_message = "Exact local trial package/config/identity receipt required. Hashes are not execution authority."
  }
}
locals { config = jsondecode(file(var.config_path)) }
data "aws_kms_key" "notices" { key_id = var.security.notice_kms_key_arn }
resource "aws_sns_topic" "notices" {
  name              = "${local.config.deployment}-notices"
  kms_master_key_id = var.security.notice_kms_key_arn
  lifecycle {
    precondition {
      condition     = data.aws_kms_key.notices.key_manager == "CUSTOMER" && data.aws_kms_key.notices.enabled && data.aws_kms_key.notices.key_spec == "SYMMETRIC_DEFAULT" && data.aws_kms_key.notices.key_usage == "ENCRYPT_DECRYPT" && data.aws_kms_key.notices.aws_account_id == local.config.account && data.aws_kms_key.notices.arn == var.security.notice_kms_key_arn
      error_message = "DescribeKey must prove the exact enabled same-account customer symmetric SNS key."
    }
    precondition {
      condition     = local.config.topicArn == "arn:aws:sns:${local.config.region}:${local.config.account}:${local.config.deployment}-notices"
      error_message = "The package must bind this exact owned SNS topic."
    }
  }
}
resource "aws_sns_topic_policy" "notices" {
  arn = aws_sns_topic.notices.arn
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Deny", Principal = "*", Action = "sns:*", Resource = aws_sns_topic.notices.arn, Condition = { Bool = { "aws:SecureTransport" = "false" } } },
    { Effect = "Allow", Principal = { Service = "cloudwatch.amazonaws.com" }, Action = "sns:Publish", Resource = aws_sns_topic.notices.arn, Condition = { StringEquals = { "aws:SourceAccount" = local.config.account }, ArnLike = { "aws:SourceArn" = "arn:aws:cloudwatch:${local.config.region}:${local.config.account}:alarm:${local.config.deployment}-*" } } }
  ] })
}
resource "aws_sns_topic_subscription" "owner" {
  topic_arn = aws_sns_topic.notices.arn
  protocol  = "email"
  endpoint  = var.notice_email
}
module "runtime" {
  source                = "./runtime"
  config_path           = var.config_path
  lambda_zip            = var.lambda_zip
  enabled               = var.enabled
  security              = var.security
  retirement            = var.retirement
  alarm_notices_enabled = var.alarm_notices_enabled
}
output "security_controls" { value = merge(module.runtime.ecs_security_controls, { notice_key_arn = aws_sns_topic.notices.kms_master_key_id }) }
output "external_key_policy_requirements" { value = module.runtime.ecs_kms_key_policy_requirements }
output "runtime_roles" { value = module.runtime.ecs_runtime_roles }
output "runtime_boundaries" { value = module.runtime.ecs_boundaries }
output "producer_policy_proposal" { value = module.runtime.producer_policies }
output "scope" { value = { deployment = local.config.deployment, account = local.config.account, region = local.config.region, bucket = module.runtime.archive_bucket, table = module.runtime.table_name, bus = module.runtime.event_bus_arn, topic = aws_sns_topic.notices.arn } }
output "package_manifest_sha256" { value = filesha256(var.package_manifest_path) }
