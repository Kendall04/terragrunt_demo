# ===========================================
# IAM roles - artifact delivery split
# ===========================================

data "aws_iam_policy_document" "github_oidc_trust_release_build" {
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
      values   = local.github_release_build_subjects
    }
  }
}

data "aws_iam_policy_document" "github_oidc_trust_dev_deploy" {
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
      values   = local.github_dev_deploy_subjects
    }
  }
}

data "aws_iam_policy_document" "github_oidc_trust_prod_promote" {
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
      values   = local.github_prod_promote_subjects
    }
  }
}

#tfsec:ignore:aws-iam-no-policy-wildcards
# ECR auth tokens and selected ECS/ELBv2 describe/register APIs require Resource "*".
data "aws_iam_policy_document" "github_release_build" {
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
    sid    = "ECRAuthToken"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECRReadWriteArtifactRepos"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.release_build_ecr_repository_arns
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
      values   = local.release_artifacts_release_list_prefixes
    }
  }

  statement {
    sid    = "ReleaseArtifactsObjectsReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = local.release_artifacts_release_object_arns
  }
}

data "aws_iam_policy_document" "github_dev_deploy" {
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
      values   = local.release_artifacts_dev_deploy_list_prefixes
    }
  }

  statement {
    sid    = "ReleaseArtifactsObjectsRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = local.release_artifacts_dev_deploy_read_object_arns
  }

  statement {
    sid    = "DevDeploymentRecordsWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = local.release_artifacts_dev_deploy_write_object_arns
  }

  statement {
    sid    = "ECSDeployControl"
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

  statement {
    sid    = "ELBv2BlueGreenDiscovery"
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
    sid    = "ELBv2BlueGreenMutation"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_elbv2_blue_green_mutation_arns
  }

  statement {
    sid    = "IAMPassTaskRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_task_role_arns

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
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

data "aws_iam_policy_document" "github_prod_promote" {
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
      values   = local.release_artifacts_prod_promote_list_prefixes
    }
  }

  statement {
    sid    = "ReleaseArtifactsObjectsRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = local.release_artifacts_prod_promote_read_object_arns
  }

  statement {
    sid    = "ProdDeploymentRecordsWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = local.release_artifacts_prod_promote_write_object_arns
  }

  statement {
    sid    = "ECSDeployControl"
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

  statement {
    sid    = "ELBv2BlueGreenDiscovery"
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
    sid    = "ELBv2BlueGreenMutation"
    effect = "Allow"
    actions = [
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:ModifyRule",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_elbv2_blue_green_mutation_arns
  }

  statement {
    sid    = "IAMPassTaskRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.app_task_role_arns

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
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

resource "aws_iam_policy" "github_release_build" {
  count = var.env == "dev" ? 1 : 0

  name        = "${var.name}-release-build"
  description = "Build and publish Demo API release artifacts via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_release_build.json
}

resource "aws_iam_policy" "github_dev_deploy" {
  count = var.env == "dev" ? 1 : 0

  name        = "${var.name}-dev-deploy"
  description = "Deploy Demo API dev from release manifests via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_dev_deploy.json
}

resource "aws_iam_policy" "github_prod_promote" {
  count = var.env == "prod" ? 1 : 0

  name        = "${var.name}-prod-promote"
  description = "Promote existing Demo API release manifests to prod via GitHub Actions"
  policy      = data.aws_iam_policy_document.github_prod_promote.json
}

resource "aws_iam_role" "github_release_build" {
  count = var.env == "dev" ? 1 : 0

  name               = "${var.name}-release-build"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_release_build.json
}

resource "aws_iam_role" "github_dev_deploy" {
  count = var.env == "dev" ? 1 : 0

  name               = "${var.name}-dev-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_dev_deploy.json
}

resource "aws_iam_role" "github_prod_promote" {
  count = var.env == "prod" ? 1 : 0

  name               = "${var.name}-prod-promote"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_prod_promote.json
}

resource "aws_iam_role_policy_attachment" "github_release_build" {
  count = var.env == "dev" ? 1 : 0

  role       = aws_iam_role.github_release_build[0].name
  policy_arn = aws_iam_policy.github_release_build[0].arn
}

resource "aws_iam_role_policy_attachment" "github_dev_deploy" {
  count = var.env == "dev" ? 1 : 0

  role       = aws_iam_role.github_dev_deploy[0].name
  policy_arn = aws_iam_policy.github_dev_deploy[0].arn
}

resource "aws_iam_role_policy_attachment" "github_prod_promote" {
  count = var.env == "prod" ? 1 : 0

  role       = aws_iam_role.github_prod_promote[0].name
  policy_arn = aws_iam_policy.github_prod_promote[0].arn
}
