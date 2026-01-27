# ===========================================
# Shared IAM policy - ECS blue/green deploy
# Used by both "app CD" and "rollback" roles
# ===========================================
data "aws_iam_policy_document" "github_ecs_blue_green" {
  # ECS control: register task definitions and update services
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECSControl"
    effect = "Allow"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeTaskDefinitions",
      "ecs:UpdateService",
      "ecs:DescribeServices",
      "ecs:ListServices",
      "ecs:ListClusters",
      "ecs:DescribeClusters",
      "ecs:DescribeTasks",
      "ecs:ListTasks",
      "ecs:DescribeTaskSets",
      "ecs:UpdateServicePrimaryTaskSet"
    ]
    resources = ["*"]
  }

  # ALB / NLB v2: needed for blue/green listener + rule switching
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ELBv2BlueGreen"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule"
    ]
    resources = ["*"]
  }

  # Pass only the ECS task/execution roles used by the services
  statement {
    sid    = "IAMPassTaskRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/demo-*-app-api-*-exec-role",
      "arn:aws:iam::${local.account_id}:role/demo-*-app-api-*-task-role",
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # Optional: ECR read-only (validate images, digests, etc.)
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECRReadOnly"
    effect = "Allow"
    actions = [
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetAuthorizationToken",
      "ecr:BatchGetImage"
    ]
    resources = ["*"]
  }

  # ECR write
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECRWriteDemoRepos"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:ListImages",
    ]

    resources = ["*"]
  }

  # Optional: CloudWatch Logs read-only (debugging, health checks)
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "CloudWatchLogsRead"
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
      "logs:GetLogEvents",
    ]
    resources = ["*"]
  }

  # EventBridge: schedule delayed scale-down Lambda
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "EventBridgeScaleDown"
    effect = "Allow"
    actions = [
      "events:PutRule",
      "events:PutTargets",
    ]
    resources = ["*"]
  }

}

resource "aws_iam_policy" "github_ecs_blue_green" {
  name        = "${var.name}-ecs-blue-green"
  description = "Minimal policy for ECS blue/green deploy via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_ecs_blue_green.json
}



# ===========================================
# IAM Role for GitHub OIDC (App CD - deploy)
# ===========================================
resource "aws_iam_role" "github_app_cd" {
  name               = "${var.name}-app-cd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
}

resource "aws_iam_role_policy_attachment" "github_app_cd_ecs" {
  role       = aws_iam_role.github_app_cd.name
  policy_arn = aws_iam_policy.github_ecs_blue_green.arn
}


# ===========================================
# IAM Role for GitHub OIDC (App rollback)
# ===========================================
resource "aws_iam_role" "github_app_rollback" {
  name               = "${var.name}-app-rollback"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
}

resource "aws_iam_role_policy_attachment" "github_app_rollback_ecs" {
  role       = aws_iam_role.github_app_rollback.name
  policy_arn = aws_iam_policy.github_ecs_blue_green.arn
}
