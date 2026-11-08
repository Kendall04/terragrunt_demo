# ===========================================
# IAM policy - ECS blue/green deploy
# ===========================================
data "aws_iam_policy_document" "github_oidc_trust_app_cd" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.github_app_cd_subjects
    }
  }
}

#tfsec:ignore:aws-iam-no-policy-wildcards
# Wildcards are limited to this demo env's ECS/ALB/log naming conventions, and some read/register APIs require Resource "*".
data "aws_iam_policy_document" "github_app_cd" {
  statement {
    sid    = "DenySecretAndParameterReadsAndWrites"
    effect = "Deny"
    actions = [
      "kms:Decrypt",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:UpdateSecretVersionStage",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECSDeployControl"
    effect = "Allow"
    actions = [
      "ecs:DescribeClusters",
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeTaskSets",
      "ecs:DescribeTasks",
      "ecs:ListTasks",
      "ecs:RegisterTaskDefinition",
      "ecs:UpdateService",
      "ecs:UpdateServicePrimaryTaskSet",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = concat(
      [local.app_ecs_cluster_arn],
      local.app_ecs_service_arns,
      local.app_ecs_task_definition_arns,
      local.app_ecs_task_arns,
      local.app_ecs_container_instance_arns,
    )
  }

  # ECS task definition registration and some describe/list APIs do not support
  # complete resource scoping across all request shapes used by the deploy action.
  statement {
    sid    = "ECSDeployDiscovery"
    effect = "Allow"
    actions = [
      "ecs:DescribeTaskDefinition",
      "ecs:ListClusters",
      "ecs:ListServices",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  # ELBv2 describe APIs do not consistently support resource-level scoping.
  statement {
    sid    = "ELBv2BlueGreenDiscovery"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeRules",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ELBv2BlueGreenMutation"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule"
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_elbv2_blue_green_mutation_arns
  }

  statement {
    sid    = "IAMPassTaskRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_task_role_arns

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # ECR authorization tokens must use Resource "*".
  statement {
    sid    = "ECRAuthToken"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECRReadWriteAppRepo"
    effect = "Allow"

    actions = [
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]

    resources = [local.app_ecr_repository_arn]
  }

  statement {
    sid    = "ReleaseArtifactsBucketLocation"
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
    ]
    resources = [local.release_artifacts_bucket_arn]
  }

  statement {
    sid    = "ReleaseArtifactsBucketList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [local.release_artifacts_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = local.release_artifacts_app_list_prefixes
    }
  }

  statement {
    sid    = "ReleaseArtifactsObjectsReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = local.release_artifacts_app_object_arns
  }

  statement {
    sid    = "CloudWatchLogsRead"
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
      "logs:GetLogEvents",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_log_group_arns
  }

  statement {
    sid    = "EventBridgeScaleDown"
    effect = "Allow"
    actions = [
      "events:DescribeRule",
      "events:ListTargetsByRule",
      "events:PutRule",
      "events:PutTargets",
    ]
    resources = [local.app_scale_down_rule_arn]
  }

  statement {
    sid    = "DeploymentReadinessChecks"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "lambda:GetFunction",
    ]
    resources = concat(local.app_task_role_arns, [local.app_scale_down_lambda_arn])
  }

}

resource "aws_iam_policy" "github_app_cd" {
  name        = "${var.name}-app-cd"
  description = "Minimal policy for ECS blue/green deploy via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_app_cd.json
}



# ===========================================
# IAM Role for GitHub OIDC (App CD - deploy)
# ===========================================
resource "aws_iam_role" "github_app_cd" {
  name               = "${var.name}-app-cd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_app_cd.json
}

resource "aws_iam_role_policy_attachment" "github_app_cd" {
  role       = aws_iam_role.github_app_cd.name
  policy_arn = aws_iam_policy.github_app_cd.arn
}


# ===========================================
# IAM Role for GitHub OIDC (App rollback)
# ===========================================
data "aws_iam_policy_document" "github_oidc_trust_app_rollback" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.github_app_rollback_subjects
    }
  }
}

#tfsec:ignore:aws-iam-no-policy-wildcards
# Rollback needs the same blue/green scoped ECS/ALB ARN patterns; secret value access is explicitly denied.
data "aws_iam_policy_document" "github_app_rollback" {
  statement {
    sid    = "DenySecretAndParameterReadsAndWrites"
    effect = "Deny"
    actions = [
      "kms:Decrypt",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:UpdateSecretVersionStage",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECSRollbackControl"
    effect = "Allow"
    actions = [
      "ecs:DescribeClusters",
      "ecs:DescribeServices",
      "ecs:DescribeTaskSets",
      "ecs:DescribeTasks",
      "ecs:ListTasks",
      "ecs:UpdateService",
      "ecs:UpdateServicePrimaryTaskSet",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = concat(
      [local.app_ecs_cluster_arn],
      local.app_ecs_service_arns,
      local.app_ecs_task_arns,
      local.app_ecs_container_instance_arns,
    )
  }

  statement {
    sid    = "ECSRollbackDiscovery"
    effect = "Allow"
    actions = [
      "ecs:ListClusters",
      "ecs:ListServices",
    ]
    resources = ["*"]
  }

  # ELBv2 describe APIs do not consistently support resource-level scoping.
  statement {
    sid    = "ELBv2BlueGreenRollbackDiscovery"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ELBv2BlueGreenRollbackMutation"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_elbv2_blue_green_mutation_arns
  }

  statement {
    sid    = "EventBridgeScaleDown"
    effect = "Allow"
    actions = [
      "events:PutRule",
      "events:PutTargets",
    ]
    resources = [local.app_scale_down_rule_arn]
  }
}

resource "aws_iam_policy" "github_app_rollback" {
  name        = "${var.name}-app-rollback"
  description = "Minimal policy for ECS blue/green rollback via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_app_rollback.json
}

resource "aws_iam_role" "github_app_rollback" {
  name               = "${var.name}-app-rollback"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_app_rollback.json
}

resource "aws_iam_role_policy_attachment" "github_app_rollback" {
  role       = aws_iam_role.github_app_rollback.name
  policy_arn = aws_iam_policy.github_app_rollback.arn
}
