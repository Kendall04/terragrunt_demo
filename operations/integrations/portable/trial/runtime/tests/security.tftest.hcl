# Plans only, native provider schema and explicit mocked AWS ports; no backend.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" { defaults = { account_id = "341936017254" } }
  mock_data "aws_region" { defaults = { region = "us-east-1" } }
  mock_data "aws_kms_key" { defaults = { arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" } }
  mock_resource "aws_dynamodb_table" { defaults = { arn = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state" } }
  mock_resource "aws_sqs_queue" { defaults = { arn = "arn:aws:sqs:us-east-1:341936017254:ecs-portable-mock-queue" } }
  mock_resource "aws_cloudwatch_log_group" { defaults = { arn = "arn:aws:logs:us-east-1:341936017254:log-group:/aws/lambda/ecs-portable-mock" } }
  mock_resource "aws_s3_bucket" { defaults = { arn = "arn:aws:s3:::snt-ecs-portable-r20261026p1-341936017254-us-east-1", id = "snt-ecs-portable-r20261026p1-341936017254-us-east-1" } }
}
override_data {
  target = data.aws_kms_key.notices
  values = { arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
}
variables {
  config_path = "@CONFIG@"
  lambda_zip  = "@ZIP@"
  security = {
    archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444"
    notice_kms_key_arn  = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555"
    access_log_bucket   = "snt-logs-ecs-portable-r20261026p1-341936017254"
    starts_at           = "2026-10-28T00:00:00Z"
    expires_at          = "2026-10-28T08:00:00Z"
  }
}
run "encryption_logging_retention_and_default_fence" {
  command = plan
  assert {
    condition     = output.ecs_security_controls.archive_algorithm == "aws:kms" && output.ecs_security_controls.pitr_days == 1 && output.ecs_security_controls.table_encrypted && output.ecs_security_controls.deletion_protected && !one(aws_s3_bucket_server_side_encryption_configuration.archive.rule).bucket_key_enabled
    error_message = "Explicit key, object-context KMS, SSE, one-day PITR and default deletion fence required."
  }
  assert {
    condition     = !aws_s3_bucket.archive.force_destroy && !aws_s3_bucket.access_logs.force_destroy && output.ecs_security_controls.access_log_algorithm == "AES256" && aws_s3_bucket.access_logs.bucket == var.security.access_log_bucket && aws_s3_bucket_logging.archive.target_prefix == "sentinel/ecs-portable-r20261026p1/" && one(aws_s3_bucket_ownership_controls.access_logs.rule).object_ownership == "BucketOwnerEnforced"
    error_message = "Dedicated private SSE-S3 destination and explicit archive logging; no force-destroy."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.access_logs.block_public_acls && aws_s3_bucket_public_access_block.access_logs.ignore_public_acls && aws_s3_bucket_public_access_block.access_logs.block_public_policy && aws_s3_bucket_public_access_block.access_logs.restrict_public_buckets && one(one(aws_s3_bucket_lifecycle_configuration.access_logs.rule).expiration).days == 30 && local.config.auditRetentionDays == 7 && alltrue([for q in aws_sqs_queue.dead : q.message_retention_seconds == 1209600]) && aws_sqs_queue.reports.message_retention_seconds == 1209600 && alltrue([for g in aws_cloudwatch_log_group.runtime : g.retention_in_days == 30])
    error_message = "Audit 7d, queue 14d, logs 30d and all public-block controls required."
  }
  assert {
    condition     = aws_iam_policy.ecs_boundary["worker"].policy == aws_iam_role_policy.runtime["worker"].policy && length([for s in jsondecode(local.ecs_runtime_policies["worker"]).Statement : s if contains(s.Action, "kms:Decrypt")]) == 2 && alltrue([for k in ["ingestion", "watchdog", "cleanup"] : alltrue([for s in jsondecode(local.ecs_runtime_policies[k]).Statement : alltrue([for a in s.Action : !startswith(a, "kms:")])])])
    error_message = "Only the worker gains the mirrored two exact key capabilities."
  }
  assert {
    condition     = local.archive_kms_statement.Resource == var.security.archive_kms_key_arn && local.archive_kms_statement.Action == ["kms:GenerateDataKey", "kms:Decrypt"] && local.archive_kms_statement.Condition.StringEquals["kms:ViaService"] == "s3.us-east-1.amazonaws.com" && local.archive_kms_statement.Condition.StringLike["kms:EncryptionContext:aws:s3:arn"] == "${aws_s3_bucket.archive.arn}/sentinel/v3/*" && local.notice_kms_statement.Resource == var.security.notice_kms_key_arn && local.notice_kms_statement.Condition.StringEquals["kms:EncryptionContext:aws:sns:topicArn"] == local.config.topicArn && local.notice_kms_statement.Condition.StringEquals["kms:ViaService"] == "sns.us-east-1.amazonaws.com" && local.archive_kms_statement.Condition.DateLessThan["aws:CurrentTime"] == var.security.expires_at
    error_message = "Exact-key, service, object/topic context and expiring KMS rights required."
  }
  assert {
    condition     = length(jsondecode(aws_s3_bucket_policy.archive.policy).Statement) == 5 && jsondecode(aws_s3_bucket_policy.access_logs.policy).Statement[1].Principal.Service == "logging.s3.amazonaws.com" && jsondecode(aws_s3_bucket_policy.access_logs.policy).Statement[1].Condition.ArnEquals["aws:SourceArn"] == aws_s3_bucket.archive.arn && jsondecode(aws_s3_bucket_policy.access_logs.policy).Statement[1].Condition.StringEquals["aws:SourceAccount"] == "341936017254"
    error_message = "Explicit encryption override denies and exact-source log delivery policy required."
  }
  assert {
    condition     = output.ecs_kms_key_policy_requirements.archive.key_arn == var.security.archive_kms_key_arn && output.ecs_kms_key_policy_requirements.notices.key_arn == var.security.notice_kms_key_arn && one(output.ecs_kms_key_policy_requirements.archive.Statement).Principal.AWS == "arn:aws:iam::341936017254:role/ecs-portable-r20261026p1-worker" && one(output.ecs_kms_key_policy_requirements.archive.Statement).Resource == "*" && one(output.ecs_kms_key_policy_requirements.notices.Statement).Condition.StringEquals["kms:EncryptionContext:aws:sns:topicArn"] == local.config.topicArn
    error_message = "Review-only external key statements must bind their enclosing key, exact worker and exact service context."
  }

}
run "runtime_activation_preserves_protection" {
  command = plan
  variables { enabled = true }
  assert {
    condition     = aws_dynamodb_table.state.deletion_protection_enabled
    error_message = "Runtime activation never opens retirement."
  }
}
run "authorized_table_transition" {
  command = plan
  variables {
    retirement = {
      table_arn       = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state"
      approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state"
    }
  }
  assert {
    condition     = !aws_dynamodb_table.state.deletion_protection_enabled && !aws_lambda_event_source_mapping.reports.enabled
    error_message = "Exact explicit transition plans only the owned table fence change, with ingestion disabled."
  }
}

run "reject_alias_key" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:alias/ecs-archive", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_foreign_key_account" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:111122223333:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_foreign_key_region" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-west-2:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_same_key" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_eks_logging_bucket" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "cloud-native-platform-341936017254-dev-us-east-1-logs", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_logging_loop" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-ecs-portable-r20261026p1-341936017254-us-east-1", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_reversed_window" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-27T23:59:00Z" } }
  expect_failures = [var.security]
}

run "reject_excess_window" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "2026-10-28T00:00:00Z", expires_at = "2026-10-28T08:01:00Z" } }
  expect_failures = [var.security]
}

run "reject_malformed_window" {
  command = plan
  variables { security = { archive_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", notice_kms_key_arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", access_log_bucket = "snt-logs-ecs-portable-r20261026p1-341936017254", starts_at = "tomorrow", expires_at = "2026-10-28T08:00:00Z" } }
  expect_failures = [var.security]
}

run "reject_retirement_foreign_table" {
  command = plan
  variables {
    retirement = { table_arn = "arn:aws:dynamodb:us-east-1:341936017254:table/cloud-native-platform-terraform-locks", approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state" }
  }
  expect_failures = [var.retirement]
}

run "reject_retirement_missing_approval" {
  command = plan
  variables {
    retirement = { table_arn = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state", approval_sha256 = "", acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state" }
  }
  expect_failures = [var.retirement]
}

run "reject_retirement_missing_ack" {
  command = plan
  variables {
    retirement = { table_arn = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state", approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", acknowledgement = "" }
  }
  expect_failures = [var.retirement]
}

run "reject_retirement_active_runtime" {
  command = plan
  variables {
    retirement = { table_arn = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state", approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state" }
    enabled    = true
  }
  expect_failures = [var.retirement]
}

run "reject_retirement_active_alarms" {
  command = plan
  variables {
    retirement            = { table_arn = "arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state", approval_sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", acknowledgement = "DISABLE DELETION PROTECTION arn:aws:dynamodb:us-east-1:341936017254:table/ecs-portable-r20261026p1-state" }
    alarm_notices_enabled = true
  }
  expect_failures = [var.retirement]
}

run "reject_aws_managed_archive" {
  command = plan
  override_data {
    target = data.aws_kms_key.archive
    values = { key_manager = "AWS", arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", enabled = true, key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
  }
  expect_failures = [aws_s3_bucket_server_side_encryption_configuration.archive]
}

run "reject_disabled_archive" {
  command = plan
  override_data {
    target = data.aws_kms_key.archive
    values = { enabled = false, arn = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444", key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
  }
  expect_failures = [aws_s3_bucket_server_side_encryption_configuration.archive]
}

run "reject_asymmetric_notice" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { key_spec = "RSA_2048", arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
  }
  expect_failures = [aws_iam_policy.ecs_boundary["worker"]]
}

run "reject_foreign_notice_owner" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { aws_account_id = "111122223333", arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT" }
  }
  expect_failures = [aws_iam_policy.ecs_boundary["worker"]]
}

run "reject_notice_signing_usage" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { key_usage = "SIGN_VERIFY", arn = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555", enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", aws_account_id = "341936017254" }
  }
  expect_failures = [aws_iam_policy.ecs_boundary["worker"]]
}
