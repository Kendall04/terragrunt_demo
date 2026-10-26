resource "aws_instance" "db" {
  ami                         = var.protected_sql_ami
  instance_type               = var.instance_type
  subnet_id                   = coalesce(var.recovery_target_subnet_id, var.private_subnet_ids[0])
  vpc_security_group_ids      = [var.db_instance_sg_id]
  iam_instance_profile        = split("/", local.expected["dev/sql-profile"])[1]
  key_name                    = var.key_name
  associate_public_ip_address = false

  credit_specification {
    cpu_credits = var.cpu_credits
  }

  metadata_options {
    http_tokens = "required"
  }

  # Null preserves the original bootstrap bytes. No timer is enabled by default.
  user_data = var.sql_backup_cohost == null ? local.sql_base_user_data : join("\n", [
    local.sql_base_user_data,
    templatefile("${path.module}/../../../../infra/data/cohost-bootstrap.sh.tftpl", {
      cohost_config = base64encode(jsonencode(var.sql_backup_cohost))
    })
  ])

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.volume_size_gb
    encrypted             = true
    kms_key_id            = null
    delete_on_termination = true
    tags                  = merge(local.tags, { Role = "root-ebs" })
  }

  tags = merge(local.tags, {
    Name = "${local.name}-sql-instance"
  })

  lifecycle {
    ignore_changes = [ami]
  }
}
resource "aws_cloudwatch_metric_alarm" "statuscheck_failed" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name}-statuscheck-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0

  dimensions = {
    InstanceId = aws_instance.db.id
  }

  alarm_description  = "EC2 instance status check failed"
  treat_missing_data = "missing"

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = local.tags
}
resource "aws_cloudwatch_metric_alarm" "cpu_credit_low" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name}-cpucredit-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CPUCreditBalance"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 20

  dimensions = {
    InstanceId = aws_instance.db.id
  }

  alarm_description  = "Low CPU credits for T instance"
  treat_missing_data = "missing"

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = local.tags
}
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${local.name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    InstanceId = aws_instance.db.id
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = local.tags
}
