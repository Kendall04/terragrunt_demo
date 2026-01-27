# ===========================================
# IAM Role for GitHub OIDC (Terragrunt CD)
# Full Terraform apply for the demo account
# ===========================================
resource "aws_iam_role" "github_terragrunt_cd" {
  name               = "${var.name}-terragrunt-cd"
  assume_role_policy = data.aws_iam_policy_document.github_oidc_trust.json
}

# For this demo environment we keep it simple and grant full admin.
# In a real-world setup you would scope this down to specific resources
# or move "prod" to a dedicated account with stricter roles.
resource "aws_iam_role_policy_attachment" "terragrunt_cd_admin" {
  role       = aws_iam_role.github_terragrunt_cd.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
