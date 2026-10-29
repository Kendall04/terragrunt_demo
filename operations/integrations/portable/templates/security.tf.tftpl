# Copied verbatim by prepare_module.py; external CMKs are never created here.
variable "security" {
  nullable = false
  type = object({
    archive_kms_key_arn = string
    notice_kms_key_arn  = string
    access_log_bucket   = string
    starts_at           = string
    expires_at          = string
  })
  validation {
    condition = alltrue([for key in [var.security.archive_kms_key_arn, var.security.notice_kms_key_arn] :
      can(regex("^arn:aws:kms:${local.config.region}:${local.config.account}:key/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", key))
    ]) && var.security.archive_kms_key_arn != var.security.notice_kms_key_arn
    error_message = "Two distinct explicit same-account regional key ARNs required; no alias or automatic key reuse."
  }
  validation {
    condition     = var.security.access_log_bucket == "snt-logs-${local.name}-${local.config.account}" && length(var.security.access_log_bucket) <= 63
    error_message = "The dedicated ECS logging bucket must use this deployment's exact snt-logs name."
  }
  validation {
    condition     = try(endswith(var.security.starts_at, "Z") && endswith(var.security.expires_at, "Z") && timecmp(var.security.starts_at, var.security.expires_at) < 0 && timecmp(var.security.expires_at, timeadd(var.security.starts_at, "8h")) <= 0, false)
    error_message = "Explicit ordered UTC grant window of at most eight hours required; timestamps do not grant execution authority."
  }
}

variable "retirement" {
  description = "Null keeps deletion protection. A separately authorized owner binds the reviewed transition to this state-managed table."
  type = object({
    table_arn       = string
    approval_sha256 = string
    acknowledgement = string
  })
  default = null
  validation {
    condition = var.retirement == null ? true : (
      var.retirement.table_arn == "arn:aws:dynamodb:${local.config.region}:${local.config.account}:table/${local.name}-state" &&
      can(regex("^[a-f0-9]{64}$", var.retirement.approval_sha256)) &&
      var.retirement.acknowledgement == "DISABLE DELETION PROTECTION ${var.retirement.table_arn}" &&
      !var.enabled && !var.alarm_notices_enabled
    )
    error_message = "Retirement needs the exact owned table ARN, reviewed approval hash and acknowledgement, with runtime and alarm actions disabled."
  }
}

data "aws_kms_key" "archive" { key_id = var.security.archive_kms_key_arn }
data "aws_kms_key" "notices" { key_id = var.security.notice_kms_key_arn }

resource "aws_s3_bucket_server_side_encryption_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id
  lifecycle {
    precondition {
      condition     = data.aws_kms_key.archive.key_manager == "CUSTOMER" && data.aws_kms_key.archive.enabled && data.aws_kms_key.archive.key_spec == "SYMMETRIC_DEFAULT" && data.aws_kms_key.archive.key_usage == "ENCRYPT_DECRYPT" && data.aws_kms_key.archive.aws_account_id == local.config.account && data.aws_kms_key.archive.arn == var.security.archive_kms_key_arn
      error_message = "DescribeKey must prove the exact enabled same-account customer symmetric archive key."
    }
  }
  rule {
    bucket_key_enabled = false
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.security.archive_kms_key_arn
    }
  }
}

resource "aws_s3_bucket_policy" "archive" {
  bucket = aws_s3_bucket.archive.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.archive.arn, "${aws_s3_bucket.archive.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } } },
    { Sid = "RejectExplicitNonKmsEncryption", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.archive.arn}/*", Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption" = "aws:kms" }, Null = { "s3:x-amz-server-side-encryption" = "false" } } },
    { Sid = "RejectForeignExplicitKmsKey", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.archive.arn}/*", Condition = { StringNotEquals = { "s3:x-amz-server-side-encryption-aws-kms-key-id" = var.security.archive_kms_key_arn }, Null = { "s3:x-amz-server-side-encryption-aws-kms-key-id" = "false" } } },
    { Sid = "RequireKeyForExplicitKms", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.archive.arn}/*", Condition = { StringEquals = { "s3:x-amz-server-side-encryption" = "aws:kms" }, Null = { "s3:x-amz-server-side-encryption-aws-kms-key-id" = "true" } } },
    { Sid = "RejectCustomerProvidedEncryption", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = "${aws_s3_bucket.archive.arn}/*", Condition = { Null = { "s3:x-amz-server-side-encryption-customer-algorithm" = "false" } } }
  ] })
}

locals {
  access_log_prefix = "sentinel/${local.name}/"
  archive_kms_statement = {
    Sid = "OwnArchiveKmsThroughS3", Effect = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = var.security.archive_kms_key_arn
    Condition = {
      StringEquals          = { "aws:RequestedRegion" = local.config.region, "kms:CallerAccount" = local.config.account, "kms:ViaService" = "s3.${local.config.region}.amazonaws.com" }
      StringLike            = { "kms:EncryptionContext:aws:s3:arn" = "${aws_s3_bucket.archive.arn}/${local.archive_prefix}" }
      DateGreaterThanEquals = { "aws:CurrentTime" = var.security.starts_at }
      DateLessThan          = { "aws:CurrentTime" = var.security.expires_at }
    }
  }
  notice_kms_statement = {
    Sid = "OwnNoticeKmsThroughSns", Effect = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = var.security.notice_kms_key_arn
    Condition = {
      StringEquals          = { "aws:RequestedRegion" = local.config.region, "kms:CallerAccount" = local.config.account, "kms:ViaService" = "sns.${local.config.region}.amazonaws.com", "kms:EncryptionContext:aws:sns:topicArn" = local.config.topicArn }
      DateGreaterThanEquals = { "aws:CurrentTime" = var.security.starts_at }
      DateLessThan          = { "aws:CurrentTime" = var.security.expires_at }
    }
  }
}

resource "aws_s3_bucket" "access_logs" {
  bucket        = "snt-logs-${local.name}-${local.config.account}"
  force_destroy = false
  tags          = { Project = "ecs-demo", Deployment = local.name, Component = "sentinel-access-logs" }
  lifecycle {
    precondition {
      condition     = local.config.account == "341936017254" && local.config.region == "us-east-1" && local.config.project == "ecs-demo" && local.config.environment == "dev" && local.config.auditRetentionDays == 7 && startswith(local.name, "ecs-portable-") && data.aws_caller_identity.current.account_id == local.config.account && data.aws_region.current.region == local.config.region
      error_message = "This portable integration only manages the admitted ECS DEV account/region/deployment, never EKS."
    }
  }
}
resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    id     = "owned-access-logs-30-days"
    status = "Enabled"
    filter { prefix = local.access_log_prefix }
    expiration { days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}
resource "aws_s3_bucket_policy" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.access_logs.arn, "${aws_s3_bucket.access_logs.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false", "aws:PrincipalIsAWSService" = "false" } } },
    { Effect = "Allow", Principal = { Service = "logging.s3.amazonaws.com" }, Action = "s3:PutObject", Resource = "${aws_s3_bucket.access_logs.arn}/${local.access_log_prefix}*", Condition = { StringEquals = { "aws:SourceAccount" = local.config.account }, ArnEquals = { "aws:SourceArn" = aws_s3_bucket.archive.arn } } }
  ] })
}
resource "aws_s3_bucket_logging" "archive" {
  bucket                = aws_s3_bucket.archive.id
  expected_bucket_owner = local.config.account
  target_bucket         = aws_s3_bucket.access_logs.id
  target_prefix         = local.access_log_prefix
  depends_on            = [aws_s3_bucket_policy.access_logs, aws_s3_bucket_ownership_controls.access_logs, aws_s3_bucket_server_side_encryption_configuration.access_logs, aws_s3_bucket_public_access_block.access_logs]
}

output "ecs_security_controls" {
  value = {
    archive_key_arn      = var.security.archive_kms_key_arn
    archive_algorithm    = one(one(aws_s3_bucket_server_side_encryption_configuration.archive.rule).apply_server_side_encryption_by_default).sse_algorithm
    pitr_days            = one(aws_dynamodb_table.state.point_in_time_recovery).recovery_period_in_days
    table_encrypted      = one(aws_dynamodb_table.state.server_side_encryption).enabled
    deletion_protected   = aws_dynamodb_table.state.deletion_protection_enabled
    access_log_bucket    = aws_s3_bucket.access_logs.bucket
    access_log_prefix    = aws_s3_bucket_logging.archive.target_prefix
    access_log_algorithm = one(one(aws_s3_bucket_server_side_encryption_configuration.access_logs.rule).apply_server_side_encryption_by_default).sse_algorithm
    table_arn            = "arn:aws:dynamodb:${local.config.region}:${local.config.account}:table/${local.name}-state"
  }
}
output "ecs_kms_key_policy_requirements" {
  description = "Review-only statements for the external key owner, not a replacement policy. Resource * means only the enclosing key_arn; preserve administration and existing Denies."
  value = {
    archive                                = { key_arn = var.security.archive_kms_key_arn, Statement = [merge(local.archive_kms_statement, { Resource = "*", Principal = { AWS = "arn:aws:iam::${local.config.account}:role/${local.name}-worker" } })] }
    notices                                = { key_arn = var.security.notice_kms_key_arn, Statement = [merge(local.notice_kms_statement, { Resource = "*", Principal = { AWS = "arn:aws:iam::${local.config.account}:role/${local.name}-worker" } })] }
    cloudwatch_if_alarm_notices_authorized = { key_arn = var.security.notice_kms_key_arn, Statement = [{ Sid = "OwnAlarmsOnly", Effect = "Allow", Principal = { Service = "cloudwatch.amazonaws.com" }, Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = "*", Condition = { StringEquals = { "aws:SourceAccount" = local.config.account }, ArnLike = { "aws:SourceArn" = "arn:aws:cloudwatch:${local.config.region}:${local.config.account}:alarm:${local.name}-*" }, DateGreaterThanEquals = { "aws:CurrentTime" = var.security.starts_at }, DateLessThan = { "aws:CurrentTime" = var.security.expires_at } } }] }
  }
}
