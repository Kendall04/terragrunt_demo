mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" { defaults = { account_id = "341936017254" } }
  mock_data "aws_region" { defaults = { region = "us-east-1" } }
  mock_data "aws_kms_key" { defaults = { arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" } }
  mock_resource "aws_iam_policy" { defaults = { arn = "arn:aws:iam::341936017254:policy/mock-boundary" } }
  mock_resource "aws_dynamodb_table" { defaults = { arn = "arn:aws:dynamodb:us-east-1:341936017254:table/mock-state" } }
  mock_resource "aws_s3_bucket" { defaults = { arn = "arn:aws:s3:::mock-archive", id = "mock-archive" } }
  mock_resource "aws_sqs_queue" { defaults = { arn = "arn:aws:sqs:us-east-1:341936017254:mock-queue", id = "https://sqs.us-east-1.amazonaws.com/341936017254/mock-queue" } }
  mock_resource "aws_cloudwatch_log_group" { defaults = { arn = "arn:aws:logs:us-east-1:341936017254:log-group:mock" } }
  mock_resource "aws_sns_topic" { defaults = { arn = "arn:aws:sns:us-east-1:341936017254:ecs-portable-r20261026p1-notices" } }
}
override_data {
  target = data.aws_kms_key.notices
  values = { arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
}
override_data {
  target = module.runtime.data.aws_kms_key.notices
  values = { arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
}
variables {
  config_path           = "@CONFIG@"
  lambda_zip            = "@ZIP@"
  notice_email          = "owner@example.invalid"
  package_manifest_path = "@RECEIPT@"
  security = {
    archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444"
    notice_kms_key_arn  = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555"
    access_log_bucket   = "snt-logs-ecs-portable-r20261026p1-341936017254"
    starts_at           = "2026-10-28T00:00:00Z"
    expires_at          = "2026-10-28T08:00:00Z"
  }
}
run "closed_input_output" {
  command = plan
  assert {
    condition     = !module.runtime.ecs_ingestion_enabled && alltrue([for s in module.runtime.ecs_schedule_states : s == "DISABLED"])
    error_message = "No runtime activation by install."
  }
  assert {
    condition     = length(module.runtime.ecs_runtime_roles) == 4 && length(module.runtime.ecs_boundaries) == 4 && module.runtime.ecs_policy_pairs_equal
    error_message = "Every role must have the exact matching boundary."
  }
  assert {
    condition     = alltrue([for h in module.runtime.ecs_handlers : startswith(h, "Ecs.Backup.Portable.Host::")])
    error_message = "Connect the actual consumer factory."
  }
  assert {
    condition     = output.package_manifest_sha256 == filesha256(var.package_manifest_path)
    error_message = "Expose the exact admitted receipt identity without exposing its contents."
  }
  assert {
    condition     = local.config.topicArn == aws_sns_topic.notices.arn && jsondecode(file(var.package_manifest_path)).configSha256 == filesha256(var.config_path)
    error_message = "SNS/config/ZIP receipt must be the same package."
  }
  assert {
    condition     = alltrue([for p in module.runtime.ecs_runtime_policy_documents : alltrue([for s in jsondecode(p).Statement : alltrue([for a in s.Action : contains(["dynamodb", "logs", "sqs", "s3", "sns", "kms"], split(":", a)[0])])])]) && alltrue([for component, p in module.runtime.ecs_runtime_policy_documents : component == "worker" || alltrue([for s in jsondecode(p).Statement : alltrue([for a in s.Action : !startswith(a, "kms:")])])])
    error_message = "Only the worker may acquire the separately constrained archive/SNS key rights; no EC2/SSM/IAM/secrets/NAT permissions."
  }
  assert {
    condition     = output.security_controls.archive_algorithm == "aws:kms" && output.security_controls.notice_key_arn == var.security.notice_kms_key_arn && output.security_controls.deletion_protected && output.security_controls.pitr_days == 1
    error_message = "Root must forward enforced security and safe retirement defaults."
  }
}
run "activation_is_separate" {
  command = plan
  variables { enabled = true }
  assert {
    condition     = module.runtime.ecs_ingestion_enabled && module.runtime.ecs_schedule_states["worker"] == "ENABLED" && alltrue([for v in module.runtime.ecs_alarm_actions_enabled : !v]) && output.security_controls.deletion_protected
    error_message = "Activation is a separate explicit input."
  }
}
run "explicit_owned_retirement" {
  command = plan
  variables {
    retirement = {
      table_arn       = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state"
      approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state"
    }
  }
  assert {
    condition     = !output.security_controls.deletion_protected && !module.runtime.ecs_ingestion_enabled
    error_message = "Only the explicit owned transition may plan unprotection; no execution occurs."
  }
}
run "reject_native_notice_metadata" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { enabled = false, arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
  }
  expect_failures = [aws_sns_topic.notices]
}
run "zip_drift_refuses_plan" {
  command = plan
  variables { lambda_zip = "@BADZIP@" }
  expect_failures = [var.package_manifest_path]
}
