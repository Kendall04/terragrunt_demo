resource "aws_sns_topic" "alerts" {
  name              = "${local.name}-alerts"
  kms_master_key_id = aws_kms_key.alerts.arn
  tags              = local.tags
}
resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email == null ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}


locals {
  alerts_topic_arn   = "arn:aws:sns:${var.region}:${var.account_id}:${local.name}-alerts"
  alerts_alarm_names = ["e1-nat-recovery-nat-dev-assign_eip-destination-failed", "e1-nat-recovery-nat-dev-change_rt-destination-failed", "e1-nat-recovery-nat-dev-disable_sdc-destination-failed", "e1-wp4-dev-nat-dlq-delivery-failed", "e1-wp4-dev-delivery-nat-failures", "e1-wp4-dev-execution-nat-failures", "demo-dev-nat-a-capacity-gap", "demo-dev-nat-a-inservice-low", "demo-dev-nat-b-capacity-gap", "demo-dev-nat-b-inservice-low", "demo-dev-tg-blue-5xx", "demo-dev-tg-blue-latency", "demo-dev-tg-green-5xx", "demo-dev-tg-green-latency"]
  alerts_alarm_arns  = [for name in local.alerts_alarm_names : "arn:aws:cloudwatch:${var.region}:${var.account_id}:alarm:${name}"]
  alerts_policy_base = jsondecode(var.alerts_topic_policy_base)
}

resource "aws_kms_key" "alerts" {
  description              = "Dedicated DEV shared CloudWatch notification encryption"
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false
  enable_key_rotation      = true
  deletion_window_in_days  = 30
  tags                     = merge(local.tags, { Name = "${local.name}-alerts", Role = "alerts" })
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ExactAdministrativeKeyManagement"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.account_id}:user/cnp-cert-admin" }
        Action = [
          "kms:DescribeKey", "kms:GetKeyPolicy", "kms:PutKeyPolicy",
          "kms:GetKeyRotationStatus", "kms:EnableKeyRotation", "kms:DisableKeyRotation",
          "kms:ListResourceTags", "kms:TagResource", "kms:UntagResource",
          "kms:UpdateKeyDescription", "kms:EnableKey", "kms:DisableKey",
          "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      },
      {
        Sid       = "ExactCloudWatchAlarmPublisherUse"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = ["kms:GenerateDataKey*", "kms:Decrypt"]
        Resource  = "*"
        Condition = {
          StringEquals = { "aws:SourceAccount" = var.account_id }
          ArnEquals    = { "aws:SourceArn" = local.alerts_alarm_arns }
        }
      }
    ]
  })
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn
  policy = jsonencode(merge(local.alerts_policy_base, {
    Statement = concat(local.alerts_policy_base.Statement, [{
      Sid       = "AllowExactEcsDevCloudWatchAlarms"
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = local.alerts_topic_arn
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id }
        ArnEquals    = { "aws:SourceArn" = local.alerts_alarm_arns }
      }
    }])
  }))
  lifecycle {
    precondition {
      condition = alltrue([
        for statement in local.alerts_policy_base.Statement :
        try(statement.Sid, "") != "AllowExactEcsDevCloudWatchAlarms"
      ])
      error_message = "Supply the reviewed original topic policy; do not duplicate the owned CloudWatch statement."
    }
  }
}
