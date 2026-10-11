data "aws_caller_identity" "current" {}

# ------------------------------------------------------------
# KMS Key for encryption/decryption operations
# - Key usage: ENCRYPT_DECRYPT (symmetric)
# - Delegated access model: IAM policies from the account control usage
# ------------------------------------------------------------
resource "aws_kms_key" "kms_microservice" {
  description             = var.description
  key_usage               = "ENCRYPT_DECRYPT"
  is_enabled              = true
  enable_key_rotation     = var.enable_key_rotation
  deletion_window_in_days = var.deletion_window_in_days
  multi_region            = var.multi_region

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableIAMUserPermissions"
        Effect    = "Allow"
        Principal = { AWS = local.account_root_arn }
        Action    = "kms:*"
        Resource  = "*"
      }
    ]
  })

  tags = merge(var.tags, { Name = var.name })
}

# ------------------------------------------------------------
# KMS Alias
# - Provides a stable and readable reference to the KMS key.
# ------------------------------------------------------------
resource "aws_kms_alias" "alias" {
  name          = "alias/${var.alias}"
  target_key_id = aws_kms_key.kms_microservice.key_id
}
