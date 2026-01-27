# ===========================================
# GitHub OIDC Provider
# ===========================================
data "tls_certificate" "github_actions" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    data.tls_certificate.github_actions.certificates[0].sha1_fingerprint,
  ]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

# ------------------------------------------------------------
# Trust Policy (GitHub OIDC -> IAM Role)
# ------------------------------------------------------------
data "aws_iam_policy_document" "github_oidc_trust" {
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
      values   = ["repo:${var.github_owner}/${var.github_repo}:*"]
    }
  }
}

# ============================================================
# IAM Role for GitHub OIDC (CI - mostly read-only)
# ============================================================
resource "aws_iam_role" "github_terragrunt_ci" {
  name               = "${var.name}-terragrunt-ci"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
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
# Extra policy: allow reading specific Secrets Manager secrets
# (solo GetSecretValue/DescribeSecret)
# ============================================================
data "aws_iam_policy_document" "ci_secrets_read" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    resources = [
      # Conn string 
      "arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:${var.project}/${var.env}/db/*",

      # SA password
      "arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:sql-sa-password-${var.project}-${var.env}-*",

      # App password
      "arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:sql-app-password-${var.project}-${var.env}-*",
    ]
  }
}

resource "aws_iam_role_policy" "ci_secrets_read" {
  name   = "${var.name}ci-secrets-read"
  role   = aws_iam_role.github_terragrunt_ci.id
  policy = data.aws_iam_policy_document.ci_secrets_read.json
}
