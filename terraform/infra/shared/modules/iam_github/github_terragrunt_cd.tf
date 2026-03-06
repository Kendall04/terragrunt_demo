# ===========================================
# IAM Role for GitHub OIDC (Terragrunt CD)
# Scoped Terraform apply for this demo platform
# ===========================================
resource "aws_iam_role" "github_terragrunt_cd" {
  name               = "${var.name}-terragrunt-cd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
}

# Broad infra management without unrestricted IAM/admin APIs.
resource "aws_iam_role_policy_attachment" "terragrunt_cd_power_user" {
  role       = aws_iam_role.github_terragrunt_cd.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

data "aws_iam_policy_document" "terragrunt_cd_iam_scoped" {
  # Terraform remote state backend access.
  statement {
    sid    = "TerraformStateS3"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::tfstate-demo-${var.env}-${local.account_id}",
      "arn:aws:s3:::tfstate-demo-${var.env}-${local.account_id}/*",
    ]
  }

  statement {
    sid    = "TerraformStateLockTable"
    effect = "Allow"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    resources = [
      "arn:aws:dynamodb:${local.aws_region}:${local.account_id}:table/tfstate-locks-${local.account_id}",
    ]
  }

  # IAM operations required by modules in this repository.
  statement {
    sid    = "ManageDemoIamResources"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:GetRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:CreatePolicy",
      "iam:DeletePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion",
      "iam:SetDefaultPolicyVersion",
      "iam:CreateInstanceProfile",
      "iam:DeleteInstanceProfile",
      "iam:GetInstanceProfile",
      "iam:ListInstanceProfilesForRole",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider",
      "iam:GetOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint",
      "iam:PassRole",
    ]
    resources = [
      "arn:aws:iam::${local.account_id}:role/demo-*",
      "arn:aws:iam::${local.account_id}:policy/demo-*",
      "arn:aws:iam::${local.account_id}:instance-profile/demo-*",
      "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com",
    ]
  }

  # Read AWS-managed policies attached to demo roles
  # (e.g. SSM, Lambda basic execution, ECS execution role policy).
  statement {
    sid    = "ReadAwsManagedPolicies"
    effect = "Allow"
    actions = [
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
    ]
    resources = [
      "arn:aws:iam::aws:policy/ReadOnlyAccess",
      "arn:aws:iam::aws:policy/PowerUserAccess",
      "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
      "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
      "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    ]
  }

  # Read/list APIs and service-linked roles require "*".
  #tfsec:ignore:aws-iam-no-policy-wildcards
  statement {
    sid    = "IamReadAndServiceLinkedRole"
    effect = "Allow"
    actions = [
      "iam:ListRoles",
      "iam:ListRoleTags",
      "iam:ListPolicies",
      "iam:ListPolicyTags",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
      "iam:ListPolicyVersions",
      "iam:ListOpenIDConnectProviders",
      "iam:ListOpenIDConnectProviderTags",
      "iam:ListInstanceProfilesForRole",
      "iam:ListInstanceProfileTags",
      "iam:CreateServiceLinkedRole",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "terragrunt_cd_iam_scoped" {
  name        = "${var.name}-terragrunt-cd-iam-scoped"
  description = "Scoped IAM + Terraform backend permissions for Terragrunt CD"
  policy      = data.aws_iam_policy_document.terragrunt_cd_iam_scoped.json
}

resource "aws_iam_role_policy_attachment" "terragrunt_cd_iam_scoped_attach" {
  role       = aws_iam_role.github_terragrunt_cd.name
  policy_arn = aws_iam_policy.terragrunt_cd_iam_scoped.arn
}
