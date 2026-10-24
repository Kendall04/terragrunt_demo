# Native Terraform schema/expression/mock plans only. No credentialed provider API.
# The text fixtures deliberately are NOT real ZIP/tar releases.
mock_provider "aws" {}

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
    artifact_path           = "tests/fixtures/mock-only.txt"
    artifact_manifest_path  = "tests/fixtures/lambda-manifest.json"
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
  observer = {
    ami_id               = "ami-00000000000000000"
    ebs_key_arn          = "arn:aws:kms:us-east-1:341936017254:key/33333333-3333-3333-3333-333333333333"
    availability_zone    = "us-east-1a"
    bundle_path          = "tests/fixtures/mock-only.txt"
    bundle_manifest_path = "tests/fixtures/host-manifest.json"
    bundle_sha256        = "a14897e7cba5178d477450275bc158f0b8e1f87257f179baa136468ec0f08712"
    bundle_source_commit = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    backup_bucket        = "offline-original-backup-bucket"
    backup_prefix        = "original/read-only"
    missing_prefix       = "sentinel-observer/ecs-sentinel-offline/empty"
    backup_key_arn       = "arn:aws:kms:us-east-1:341936017254:key/11111111-1111-1111-1111-111111111111"
    text_key_arn         = "arn:aws:kms:us-east-1:341936017254:key/22222222-2222-2222-2222-222222222222"
    database             = "DemoDb"
    max_age_hours        = 168
    cadence_seconds      = 60
    publish_attempts     = 3
  }
}

run "pipeline_default_off" {
  command = plan
  assert {
    condition     = output.observer == null
    error_message = "Observer must remain disabled by default."
  }
  assert {
    condition     = length(jsondecode(output.pipeline.distribution_policy_json).Statement) == 2
    error_message = "No distribution-reader exception unless observer explicitly selected."
  }
}

run "observer_scheduled" {
  command = plan
  override_data {
    target = module.observer[0].data.aws_ami.observer
    values = { id = "ami-00000000000000000" }
  }
  override_data {
    target = module.observer[0].data.aws_kms_key.ebs
    values = { key_manager = "AWS", arn = "arn:aws:kms:us-east-1:341936017254:key/33333333-3333-3333-3333-333333333333" }
  }
  variables {
    enable_observer              = true
    enable_dispatch_schedule     = true
    dispatch_schedule_expression = "rate(1 minute)"
  }
  assert {
    condition     = output.observer.timer_state == "INSTALLED_INERT_OPERATOR_START_AFTER_SNS_CONFIRMATION"
    error_message = "Creating the host must not start the producer."
  }
  assert {
    condition     = length(jsondecode(output.pipeline.distribution_policy_json).Statement) == 4
    error_message = "Host needs explicit deny outside artifact plus mutation deny."
  }
  assert {
    condition     = jsondecode(output.pipeline.distribution_policy_json).Statement[3].NotAction == ["s3:GetObjectVersion"]
    error_message = "Host distribution must never include latest reads or mutation."
  }
  assert {
    condition     = alltrue([for s in jsondecode(output.observer.runtime_policy_json).Statement : !contains(s.Action, "ec2:TerminateInstances") && !contains(s.Action, "sns:Publish") && !contains(s.Action, "s3:PutObject")])
    error_message = "Observer role cannot change infrastructure or publish notices."
  }
}
