# Pure provider mock plans; no backend, grants, real keys or API requests.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_kms_key" {
    defaults = { enabled = true, key_manager = "CUSTOMER", key_spec = "SYMMETRIC_DEFAULT", key_usage = "ENCRYPT_DECRYPT", aws_account_id = "341936017254" }
  }
}
variables {
  config = {
    account                 = "341936017254"
    region                  = "us-east-1"
    run_id                  = "ecs-sentinel-offline"
    project                 = "ecs-demo"
    subject                 = "sql-backup"
    scope                   = "observer-trial"
    owner                   = "Kendall"
    mode                    = "observer-check"
    starts_at               = "2026-10-24T00:00:00Z"
    expires_at              = "2026-10-25T00:00:00Z"
    sender_label            = "ECS Backup Check Trial"
    notification_mode       = "EscalationAndRecovery"
    email                   = "not-a-recipient@example.invalid"
    sender_role_arn         = "arn:aws:iam::341936017254:role/ecs-sentinel-offline-observer"
    lifecycle_principal_arn = "arn:aws:iam::341936017254:role/TerragruntDemoDevOperator"
    artifact_path           = "../../tests/fixtures/mock-only.txt"
    artifact_manifest_path  = "../../tests/fixtures/lambda-manifest.json"
    artifact_sha256         = "a14897e7cba5178d477450275bc158f0b8e1f87257f179baa136468ec0f08712"
    source_commit           = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    upstream_commit         = "0e8fc55333ddde3b9816885915310a7e69f3de45"
    evidence_seconds        = 600
    budget_seconds          = 120
    check_seconds           = 60
    hold_seconds            = 60
    dedup_seconds           = 86400
    signal_age_seconds      = 600
    audit_seconds           = 86400
    effect_seconds          = 86400
    log_retention_days      = 1
    queue_retention_seconds = 86400
    dlq_retention_seconds   = 86400
    watchdog_seconds        = 180
    observer_expected_up    = true
  }
  security = {
    archive_kms_key_arn       = "arn:aws:kms:us-east-1:341936017254:key/44444444-4444-4444-8444-444444444444"
    notice_kms_key_arn        = "arn:aws:kms:us-east-1:341936017254:key/55555555-5555-4555-8555-555555555555"
    access_log_bucket         = "snt-logs-ecs-sentinel-offline-341936017254"
    access_log_prefix         = "sentinel/ecs-sentinel-offline/"
    access_log_retention_days = 1
  }
}
run "customer_keys_and_controls" {
  command = plan
  assert {
    condition     = output.security_controls.archive_algorithm == "aws:kms" && output.security_controls.table_pitr_enabled && output.security_controls.table_pitr_days == 1
    error_message = "Real planned security controls required."
  }
}

run "reject_aws_managed_archive" {
  command = plan
  override_data {
    target = data.aws_kms_key.archive
    values = { key_manager = "AWS" }
  }
  expect_failures = [aws_s3_bucket_server_side_encryption_configuration.archive]
}

run "reject_disabled_archive" {
  command = plan
  override_data {
    target = data.aws_kms_key.archive
    values = { enabled = false }
  }
  expect_failures = [aws_s3_bucket_server_side_encryption_configuration.archive]
}

run "reject_asymmetric_notice" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { key_spec = "RSA_2048" }
  }
  expect_failures = [aws_sns_topic.notices]
}

run "reject_foreign_notice_owner" {
  command = plan
  override_data {
    target = data.aws_kms_key.notices
    values = { aws_account_id = "111122223333" }
  }
  expect_failures = [aws_sns_topic.notices]
}
