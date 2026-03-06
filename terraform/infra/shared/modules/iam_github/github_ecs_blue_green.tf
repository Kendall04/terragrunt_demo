# ===========================================
# Shared IAM policy - ECS blue/green deploy
# Used by both "app CD" and "rollback" roles
# ===========================================
data "aws_iam_policy_document" "github_ecs_blue_green" {
  # ECS read-only APIs used by deployment and rollback scripts.
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECSReadOnly"
    effect = "Allow"
    actions = [
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeTasks",
      "ecs:ListTasks",
      "ecs:ListServices",
      "ecs:ListClusters",
      "ecs:DescribeClusters"
    ]
    resources = ["*"]
  }

  # ECS mutable actions scoped to this demo platform.
  statement {
    sid    = "ECSWriteScoped"
    effect = "Allow"
    actions = [
      "ecs:UpdateService"
    ]
    resources = [
      "arn:aws:ecs:${local.aws_region}:${local.account_id}:service/demo-*-platform-main-cluster/demo-*-app-api-*-svc",
    ]
  }

  # RegisterTaskDefinition is required by deployments and uses wildcard scope.
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECSRegisterTaskDefinition"
    effect = "Allow"
    actions = [
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  # ELBv2 read-only calls.
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ELBv2ReadOnly"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetHealth",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeRules"
    ]
    resources = ["*"]
  }

  # ELBv2 mutable calls scoped to demo ALBs/listeners/rules.
  statement {
    sid    = "ELBv2WriteScoped"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule"
    ]
    resources = [
      "arn:aws:elasticloadbalancing:${local.aws_region}:${local.account_id}:listener/app/demo-*-internal-alb/*/*",
      "arn:aws:elasticloadbalancing:${local.aws_region}:${local.account_id}:listener-rule/app/demo-*-internal-alb/*/*/*",
      "arn:aws:elasticloadbalancing:${local.aws_region}:${local.account_id}:rule/app/demo-*-internal-alb/*/*/*",
    ]
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
  statement {
    sid    = "ECRReadOnly"
    effect = "Allow"
    actions = [
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:BatchGetImage"
    ]
    resources = [
      "arn:aws:ecr:${local.aws_region}:${local.account_id}:repository/demo-*-shared-demo-ms",
    ]
  }

  # ECR auth token must stay wildcard.
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "ECRAuthToken"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  # ECR write on demo repositories only.
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

    resources = [
      "arn:aws:ecr:${local.aws_region}:${local.account_id}:repository/demo-*-shared-demo-ms",
    ]
  }

  # Optional: CloudWatch Logs group listing (requires wildcard scope).
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "CloudWatchLogGroupsRead"
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }

  # Optional: CloudWatch Logs read-only (debugging, health checks)
  statement {
    sid    = "CloudWatchLogsStreamsRead"
    effect = "Allow"
    actions = [
      "logs:DescribeLogStreams",
      "logs:GetLogEvents",
    ]
    resources = [
      "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ecs/demo-*",
      "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ecs/demo-*:log-stream:*",
    ]
  }

  # Read scale-down lambda ARN during deploy discovery.
  statement {
    sid    = "LambdaReadScaleDown"
    effect = "Allow"
    actions = [
      "lambda:GetFunction",
    ]
    resources = [
      "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:demo-*-scale-down-old-color-lambda",
    ]
  }

  # EventBridge: schedule delayed scale-down Lambda
  statement {
    sid    = "EventBridgeScaleDown"
    effect = "Allow"
    actions = [
      "events:PutRule",
      "events:PutTargets",
    ]
    resources = [
      "arn:aws:events:${local.aws_region}:${local.account_id}:rule/demo-*-scale-down-old-color-rule",
    ]
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
