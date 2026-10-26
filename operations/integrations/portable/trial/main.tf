terraform { required_version = ">= 1.13.4, < 2.0" }
variable "config_path" { type = string }
variable "lambda_zip" { type = string }
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
resource "aws_sns_topic" "notices" { name = "${local.config.deployment}-notices" }
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
  source      = "./runtime"
  config_path = var.config_path
  lambda_zip  = var.lambda_zip
  enabled     = var.enabled
}
output "runtime_roles" { value = module.runtime.ecs_runtime_roles }
output "runtime_boundaries" { value = module.runtime.ecs_boundaries }
output "producer_policy_proposal" { value = module.runtime.producer_policies }
output "scope" { value = { deployment = local.config.deployment, account = local.config.account, region = local.config.region, bucket = module.runtime.archive_bucket, table = module.runtime.table_name, bus = module.runtime.event_bus_arn, topic = aws_sns_topic.notices.arn } }
