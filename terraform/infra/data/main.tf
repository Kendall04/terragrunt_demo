# ------------------------------------------------------------
# AMI Lookup: Ubuntu 22.04 LTS (Jammy)
# - Fetches the latest official Canonical AMI for x86_64
# ------------------------------------------------------------
data "aws_ami" "ubuntu_2204" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

# ------------------------------------------------------------
# IAM Role for SSM-enabled EC2 instance
# - Grants SSM access + SecretsManager read (SA and APP secrets)
# - EC2 uses this role via instance profile
# ------------------------------------------------------------
data "aws_iam_policy" "ssm_core" {
  arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role" "ec2_role" {
  name = "${local.name}-sql-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "ec2.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ssm_attach" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = data.aws_iam_policy.ssm_core.arn
}

# Extra inline policy for reading DB credentials from Secrets Manager
resource "aws_iam_role_policy" "secrets_access" {
  name = "${local.name}-sql-ec2-secrets-access"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.sql_sa_secret_arn,
          var.sql_app_secret_arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = var.secret_kms_key_arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${local.name}-sql-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ------------------------------------------------------------
# Private EC2 Instance (SQL Server)
# - Runs inside private subnet
# - Uses SSM (no SSH)
# - Reads secrets for SA/app users
# - Bootstrapped via user_data templatefile
# ------------------------------------------------------------
resource "aws_instance" "db" {
  ami                         = data.aws_ami.ubuntu_2204.id
  instance_type               = var.instance_type
  subnet_id                   = var.private_subnet_ids[0]
  vpc_security_group_ids      = [var.db_instance_sg_id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  key_name                    = var.key_name
  associate_public_ip_address = false

  credit_specification {
    cpu_credits = var.cpu_credits
  }

  metadata_options {
    http_tokens = "required"
  }

  # Provision SQL Server through cloud-init template
  user_data = templatefile("${path.module}/user_data.sh", {
    AWS_REGION     = var.aws_region
    APP_DB         = var.app_db
    APP_USER       = var.app_user
    SA_SECRET_ARN  = var.sql_sa_secret_arn
    APP_SECRET_ARN = var.sql_app_secret_arn
  })

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.volume_size_gb
    encrypted             = true
    kms_key_id            = var.kms_key_id
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

# ---------- DB EC2 Alarm: Status check failed ----------
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

# ---------- DB EC2 Alarm: CPU credits low ----------
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
  treat_missing_data = "notBreaching"

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
