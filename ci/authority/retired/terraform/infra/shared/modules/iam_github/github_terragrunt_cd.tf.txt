# ===========================================
# IAM Role for GitHub OIDC (Terragrunt CD)
# ===========================================
data "aws_iam_policy_document" "github_oidc_trust_terragrunt_cd" {
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
      values   = local.github_terragrunt_cd_subjects
    }
  }
}

resource "aws_iam_role" "github_terragrunt_cd" {
  name               = "${var.name}-terragrunt-cd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_terragrunt_cd.json
}

data "aws_iam_policy_document" "github_oidc_trust_terragrunt_cd_high_risk" {
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
      values   = local.github_terragrunt_cd_high_risk_subjects
    }
  }
}

resource "aws_iam_role" "github_terragrunt_cd_high_risk" {
  name               = "${var.name}-terragrunt-cd-high-risk"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_terragrunt_cd_high_risk.json
}

#tfsec:ignore:aws-iam-no-policy-wildcards
# Terragrunt CD manages env-scoped infrastructure; wildcard API scopes are constrained by GitHub OIDC and explicit secret/GitHub-role denies.
# TODO(security): OIDC provider mutation, release bucket policy/delete,
# Secrets Manager resource policies/deletes, kms:*, and broad IAM mutation plus
# PassRole are bootstrap/shared-admin candidates. Keep them here until the
# bootstrap/high-risk split is tested, because moving them can break Terragrunt
# apply for shared or high-risk layers.
data "aws_iam_policy_document" "terragrunt_cd" {
  statement {
    sid    = "DenyGitHubOIDCRoleMutation"
    effect = "Deny"
    actions = [
      "iam:AttachRolePolicy",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
      "iam:UpdateRoleDescription",
    ]
    resources = local.github_oidc_role_arns
  }

  statement {
    sid    = "DenyGitHubOIDCPolicyMutation"
    effect = "Deny"
    actions = [
      "iam:CreatePolicyVersion",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:SetDefaultPolicyVersion",
      "iam:TagPolicy",
      "iam:UntagPolicy",
    ]
    resources = local.github_oidc_policy_arns
  }

  statement {
    sid    = "TerraformStateBucket"
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [local.state_bucket_arn]
  }

  statement {
    sid    = "TerraformStateObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [local.state_bucket_objects]
  }

  statement {
    sid    = "ReleaseArtifactsBucketLifecycle"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:DeleteBucketEncryption",
      "s3:DeleteBucketOwnershipControls",
      "s3:DeleteBucketPolicy",
      "s3:DeleteBucketPublicAccessBlock",
      "s3:GetAccelerateConfiguration",
      "s3:GetBucketAcl",
      "s3:GetBucketCORS",
      "s3:GetBucketLocation",
      "s3:GetBucketLogging",
      "s3:GetBucketObjectLockConfiguration",
      "s3:GetBucketOwnershipControls",
      "s3:GetBucketPolicy",
      "s3:GetBucketPublicAccessBlock",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketTagging",
      "s3:GetBucketVersioning",
      "s3:GetBucketWebsite",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPolicy",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketTagging",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = [local.release_artifacts_bucket_arn]
  }

  statement {
    sid    = "ReleaseArtifactsObjectLifecycle"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = [local.release_artifacts_bucket_objects]
  }

  statement {
    sid    = "TerraformStateLocks"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    resources = [local.state_lock_table_arn]
  }

  statement {
    sid    = "WorkloadRoleLifecycle"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRole",
      "iam:UpdateRoleDescription",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.terraform_managed_workload_role_arns
  }

  statement {
    sid    = "WorkloadManagedPolicyLifecycle"
    effect = "Allow"
    actions = [
      "iam:CreatePolicy",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:SetDefaultPolicyVersion",
      "iam:TagPolicy",
      "iam:UntagPolicy",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.terraform_managed_policy_arns
  }

  statement {
    sid    = "AttachApprovedPoliciesToWorkloadRoles"
    effect = "Allow"
    actions = [
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.terraform_managed_workload_role_arns

    condition {
      test     = "ArnLike"
      variable = "iam:PolicyARN"
      values   = local.attachable_workload_policy_arns
    }
  }

  statement {
    sid    = "WorkloadInstanceProfileLifecycle"
    effect = "Allow"
    actions = [
      "iam:AddRoleToInstanceProfile",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:GetInstanceProfile",
      "iam:ListInstanceProfilesForRole",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:TagInstanceProfile",
      "iam:UntagInstanceProfile",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = concat(local.terraform_managed_instance_profile_arns, local.terraform_managed_workload_role_arns)
  }

  statement {
    sid    = "PassWorkloadServiceRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.passable_service_role_arns

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values = [
        "ec2.amazonaws.com",
        "ecs-tasks.amazonaws.com",
        "lambda.amazonaws.com",
        "vpc-flow-logs.amazonaws.com",
      ]
    }
  }

  statement {
    sid    = "GitHubOIDCProviderManagement"
    effect = "Allow"
    actions = [
      "iam:AddClientIDToOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:GetOpenIDConnectProvider",
      "iam:RemoveClientIDFromOpenIDConnectProvider",
      "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com",
    ]
  }

  statement {
    sid    = "IAMReadOnlyDiscovery"
    effect = "Allow"
    #tfsec:ignore:aws-iam-no-policy-wildcards
    actions = [
      "iam:Get*",
      "iam:List*",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = ["*"]
  }

  # Many Terraform-managed EC2/VPC, ELB, ECS, API Gateway, Auto Scaling,
  # CloudWatch, Lambda, and KMS APIs either require Resource "*" or create
  # resources whose final ARN is unknown until after the API call.
  statement {
    sid    = "DemoInfrastructureLifecycle"
    effect = "Allow"
    #tfsec:ignore:aws-iam-no-policy-wildcards
    actions = [
      "apigateway:*",
      "autoscaling:*",
      "cloudwatch:*",
      "ec2:*",
      "ecr:*",
      "ecs:*",
      "elasticloadbalancing:*",
      "events:*",
      "kms:*",
      "lambda:*",
      "logs:*",
      "sns:*",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = ["*"]
  }

  statement {
    sid    = "SecretsManagerMetadataOnly"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:PutResourcePolicy",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource",
    ]
    #tfsec:ignore:aws-iam-no-policy-wildcards
    resources = local.scoped_secret_arns
  }

  statement {
    sid    = "SecretsManagerList"
    effect = "Allow"
    actions = [
      "secretsmanager:ListSecrets",
    ]
    resources = ["*"]
  }

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
}

resource "aws_iam_role_policy" "terragrunt_cd" {
  name   = "${var.name}-terragrunt-cd"
  role   = aws_iam_role.github_terragrunt_cd.id
  policy = data.aws_iam_policy_document.terragrunt_cd.json
}

# High-risk dev infra uses the current Terragrunt CD permissions initially,
# but the trust boundary is narrowed to the protected dev-infra-approval
# GitHub Environment. Future hardening can split this policy by layer.
resource "aws_iam_role_policy" "terragrunt_cd_high_risk" {
  name   = "${var.name}-terragrunt-cd-high-risk"
  role   = aws_iam_role.github_terragrunt_cd_high_risk.id
  policy = data.aws_iam_policy_document.terragrunt_cd.json
}
