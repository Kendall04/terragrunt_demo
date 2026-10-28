mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" { defaults = { account_id = "341936017254" } }
  mock_data "aws_region" { defaults = { region = "us-east-1" } }
  mock_resource "aws_iam_policy" { defaults = { arn = "arn:aws:iam::341936017254:policy/mock-boundary" } }
  mock_resource "aws_dynamodb_table" { defaults = { arn = "arn:aws:dynamodb:us-east-1:341936017254:table/mock-state" } }
  mock_resource "aws_s3_bucket" { defaults = { arn = "arn:aws:s3:::mock-archive", id = "mock-archive" } }
  mock_resource "aws_sqs_queue" { defaults = { arn = "arn:aws:sqs:us-east-1:341936017254:mock-queue", id = "https://sqs.us-east-1.amazonaws.com/341936017254/mock-queue" } }
  mock_resource "aws_cloudwatch_log_group" { defaults = { arn = "arn:aws:logs:us-east-1:341936017254:log-group:mock" } }
  mock_resource "aws_sns_topic" { defaults = { arn = "arn:aws:sns:us-east-1:341936017254:ecs-portable-r20261026p1-notices" } }
}
variables {
  config_path           = "@CONFIG@"
  lambda_zip            = "@ZIP@"
  notice_email          = "owner@example.invalid"
  package_manifest_path = "@RECEIPT@"
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
    condition     = alltrue([for p in module.runtime.ecs_runtime_policy_documents : alltrue([for s in jsondecode(p).Statement : alltrue([for a in s.Action : contains(["dynamodb", "logs", "sqs", "s3", "sns"], split(":", a)[0])])])])
    error_message = "No EC2/SSM/IAM/secrets/KMS/NAT runtime permission."
  }
}
run "activation_is_separate" {
  command = plan
  variables { enabled = true }
  assert {
    condition     = module.runtime.ecs_ingestion_enabled && module.runtime.ecs_schedule_states["worker"] == "ENABLED" && alltrue([for v in module.runtime.ecs_alarm_actions_enabled : !v])
    error_message = "Activation is a separate explicit input."
  }
}
run "zip_drift_refuses_plan" {
  command = plan
  variables { lambda_zip = "@BADZIP@" }
  expect_failures = [var.package_manifest_path]
}
