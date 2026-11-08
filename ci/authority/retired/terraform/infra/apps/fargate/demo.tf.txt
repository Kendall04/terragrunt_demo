# ─────────────────────────────────────────────────────────────
# BLUE/GREEN ECS Services for Demo API
#
# This configuration defines two independent ECS Fargate services:
#
#   - BLUE  : One deployable service color
#   - GREEN : The other deployable service color
#
# Each service points to its own ALB target group.
# Only one of them receives traffic at a time.
#
# desired_count:
#   - Both colors are created at 0 by Terraform.
#   - CI/CD owns task definition revisions, active color, and runtime scale.
#
# CI/CD will:
#   1. Register a task definition with an immutable ECR digest
#   2. Validate health
#   3. Promote the inactive color (switch ALB listeners)
#   4. Optionally scale the old color down
# ─────────────────────────────────────────────────────────────


# ===============================================================
# BLUE SERVICE — Active Production
# ===============================================================
module "demo_api_blue" {
  source = "./modules/ecs_service"

  name        = local.api_blue_name
  cluster_arn = var.cluster_arn

  subnet_ids         = var.private_subnet_ids
  security_group_ids = [var.demo_sg_id]

  container_name = local.api_blue_name
  image          = local.container_bootstrap_image

  port_mappings = [{
    containerPort = 8080
    protocol      = "tcp"
  }]

  # BLUE target group
  load_balancers = [{
    target_group_arn = var.demo_blue_tg_arn
    container_name   = local.api_blue_name
    container_port   = 8080
  }]

  environment = {
    AWS_REGION = var.aws_region
    APP_ENV    = var.env
    DEPLOYMENT = "blue"
    KMS_KEY_ID = var.kms_key_id
  }

  secrets = {
    DB_CONN_STRING = var.db_secret_arn
  }

  desired_count = 0 # Runtime scale is owned by the app deployment pipeline.
  task_cpu      = "256"
  task_memory   = "512"

  task_policy_arns = [
    aws_iam_policy.task_use_kms.arn
  ]

  execution_policy_arns = [
    aws_iam_policy.exec_read_db_secret.arn
  ]

  tags = merge(local.tags, { Deployment = "Blue" })

  alerts_topic_arn = var.alerts_topic_arn
  enable_alarms    = true
}


# ===============================================================
# GREEN SERVICE — Deployment Candidate
# ===============================================================
module "demo_api_green" {
  source = "./modules/ecs_service"

  name        = local.api_green_name
  cluster_arn = var.cluster_arn

  subnet_ids         = var.private_subnet_ids
  security_group_ids = [var.demo_sg_id]

  container_name = local.api_green_name
  image          = local.container_bootstrap_image

  port_mappings = [{
    containerPort = 8080
    protocol      = "tcp"
  }]

  # GREEN target group
  load_balancers = [{
    target_group_arn = var.demo_green_tg_arn
    container_name   = local.api_green_name
    container_port   = 8080
  }]

  environment = {
    AWS_REGION = var.aws_region
    APP_ENV    = var.env
    DEPLOYMENT = "green"
    KMS_KEY_ID = var.kms_key_id
  }

  secrets = {
    DB_CONN_STRING = var.db_secret_arn
  }

  desired_count = 0 # Runtime scale is owned by the app deployment pipeline.
  task_cpu      = "256"
  task_memory   = "512"

  task_policy_arns = [
    aws_iam_policy.task_use_kms.arn
  ]

  execution_policy_arns = [
    aws_iam_policy.exec_read_db_secret.arn
  ]

  tags = merge(local.tags, { Deployment = "Green" })

  alerts_topic_arn = var.alerts_topic_arn
  enable_alarms    = true
}


# ===============================================================
# IAM: Allow ECS execution role to read DB Secret
# ===============================================================
resource "aws_iam_policy" "exec_read_db_secret" {
  name        = "demo-${var.env}-api-exec-read-db-secret"
  description = "Allow ECS execution role to read DB connection string"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "ReadDbSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.db_secret_arn
      },
      {
        Sid    = "DecryptDbSecret"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}


# ===============================================================
# IAM: Allow ECS task role to use KMS for field-level encryption
# ===============================================================
resource "aws_iam_policy" "task_use_kms" {
  name        = "demo-${var.env}-api-task-use-kms"
  description = "Allow ECS task to encrypt/decrypt data using KMS"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "AllowKmsEncryptDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt"
        ]
        Resource = var.kms_key_arn
      }
    ]
  })
}
