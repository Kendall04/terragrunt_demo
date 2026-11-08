
data "aws_kms_key" "archive" { key_id = var.security.archive_kms_key_arn }
data "aws_kms_key" "notices" { key_id = var.security.notice_kms_key_arn }

# Source-only managed security controls. Existing resource addresses are preserved.
# External keys/log destination are required references, never created or inferred here.

resource "aws_dynamodb_table" "state" {
  name                        = local.name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "PK"
  range_key                   = "SK"
  deletion_protection_enabled = !var.allow_data_retirement
  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "DuePK"
    type = "S"
  }
  attribute {
    name = "DueSK"
    type = "S"
  }
  attribute {
    name = "ActivePK"
    type = "S"
  }
  attribute {
    name = "ActiveSK"
    type = "S"
  }
  attribute {
    name = "CleanPK"
    type = "S"
  }
  attribute {
    name = "CleanSK"
    type = "S"
  }
  global_secondary_index {
    name            = "Due"
    hash_key        = "DuePK"
    range_key       = "DueSK"
    projection_type = "KEYS_ONLY"
  }
  global_secondary_index {
    name            = "Active"
    hash_key        = "ActivePK"
    range_key       = "ActiveSK"
    projection_type = "KEYS_ONLY"
  }
  global_secondary_index {
    name            = "Cleanup"
    hash_key        = "CleanPK"
    range_key       = "CleanSK"
    projection_type = "KEYS_ONLY"
  }
  tags = local.tags
  server_side_encryption {
    enabled = true
  }
  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 1
  }
}

resource "aws_s3_bucket" "archive" {
  bucket        = local.bucket_name
  force_destroy = false
  tags          = local.tags
}

resource "aws_s3_bucket_versioning" "archive" {
  bucket = aws_s3_bucket.archive.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  lifecycle {
    precondition {
      condition     = data.aws_kms_key.archive.key_manager == "CUSTOMER" && data.aws_kms_key.archive.enabled && data.aws_kms_key.archive.key_spec == "SYMMETRIC_DEFAULT" && data.aws_kms_key.archive.key_usage == "ENCRYPT_DECRYPT" && data.aws_kms_key.archive.aws_account_id == var.config.account
      error_message = "DescribeKey must prove an enabled same-account customer-managed symmetric encryption key; ARN shape alone is not proof."
    }
  }

  bucket = aws_s3_bucket.archive.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.security.archive_kms_key_arn
    }
    bucket_key_enabled = false
  }
}

resource "aws_sns_topic" "notices" {
  lifecycle {
    precondition {
      condition     = data.aws_kms_key.notices.key_manager == "CUSTOMER" && data.aws_kms_key.notices.enabled && data.aws_kms_key.notices.key_spec == "SYMMETRIC_DEFAULT" && data.aws_kms_key.notices.key_usage == "ENCRYPT_DECRYPT" && data.aws_kms_key.notices.aws_account_id == var.config.account
      error_message = "DescribeKey must prove an enabled same-account customer-managed symmetric encryption key; ARN shape alone is not proof."
    }
  }

  name              = "${local.name}-notices"
  tags              = local.tags
  kms_master_key_id = var.security.notice_kms_key_arn
}

resource "aws_s3_bucket_logging" "archive" {
  bucket                = aws_s3_bucket.archive.id
  expected_bucket_owner = var.config.account
  target_bucket         = var.security.access_log_bucket
  target_prefix         = var.security.access_log_prefix
}
