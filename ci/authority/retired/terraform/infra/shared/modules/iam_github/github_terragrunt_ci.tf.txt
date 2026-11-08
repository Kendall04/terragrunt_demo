# ===========================================
# GitHub OIDC Provider
# ===========================================
data "tls_certificate" "github_actions" {
  count = var.create_github_oidc_provider ? 1 : 0
  url   = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    data.tls_certificate.github_actions[0].certificates[0].sha1_fingerprint,
  ]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider || var.github_oidc_provider_arn != null ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

# ------------------------------------------------------------
# Trust Policy (GitHub OIDC -> CI IAM Role)
# ------------------------------------------------------------
data "aws_iam_policy_document" "github_oidc_trust_ci" {
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
      values   = local.github_ci_subjects
    }
  }
}

# ============================================================
# IAM Role for GitHub OIDC (CI - mostly read-only)
# ============================================================
resource "aws_iam_role" "github_terragrunt_ci" {
  name               = "${var.name}-terragrunt-ci"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust_ci.json
}

# ============================================================
# Attach AWS-managed ReadOnlyAccess for the rest of AWS
# (EC2/ECS/ECR/IAM/Logs/Events/KMS/etc.)
# ============================================================
resource "aws_iam_role_policy_attachment" "ci_readonly_access" {
  role       = aws_iam_role.github_terragrunt_ci.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# ============================================================
# Explicitly deny reading or mutating secret values in CI.
#
# The CI role can plan infrastructure, but secret values are bootstrapped
# outside Terraform and must not be readable by PR validation.
# ============================================================
data "aws_iam_policy_document" "ci_deny_secret_values" {
  statement {
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

resource "aws_iam_role_policy" "ci_deny_secret_values" {
  name   = "${var.name}-ci-deny-secret-values"
  role   = aws_iam_role.github_terragrunt_ci.id
  policy = data.aws_iam_policy_document.ci_deny_secret_values.json
}
