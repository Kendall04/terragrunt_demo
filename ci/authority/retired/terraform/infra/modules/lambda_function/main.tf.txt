# ---------------------------------------------------------------------------
# LAMBDA FUNCTION (generic submodule)
# Creates a Lambda function from an S3 artifact.
# Features:
#  - Fully generic naming
#  - Optional VPC networking
#  - Optional environment variables
#  - Reusable role (from iam_role.tf)
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "this" {
  function_name = "${var.name}-lambda"
  role          = var.role_arn

  # If filename is provided, we deploy from local zip.
  # Otherwise, we fall back to S3 artifact configuration.
  filename          = var.filename
  source_code_hash  = var.filename == null ? null : filebase64sha256(var.filename)
  s3_bucket         = var.filename == null ? var.s3_bucket : null
  s3_key            = var.filename == null ? var.s3_key : null
  s3_object_version = var.filename == null ? var.s3_object_version : null

  runtime       = var.runtime
  handler       = var.handler
  architectures = ["x86_64"]
  memory_size   = var.memory_mb
  timeout       = var.timeout_sec
  publish       = true
  tags          = var.tags

  # Optional VPC networking
  # Only applied if both subnet IDs and SG ID are provided
  dynamic "vpc_config" {
    for_each = var.private_subnet_ids != null && var.lambda_sg_id != null ? [1] : []
    content {
      subnet_ids         = var.private_subnet_ids
      security_group_ids = [var.lambda_sg_id]
    }
  }

  # Optional environment variables
  dynamic "environment" {
    for_each = var.environment_variables != null ? [1] : []
    content {
      variables = var.environment_variables
    }
  }
}

resource "aws_lambda_permission" "invoke" {
  for_each = {
    for idx, perm in var.invoke_permissions : idx => perm
  }

  statement_id  = each.value.statement_id
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = each.value.principal
  source_arn    = each.value.source_arn
}
