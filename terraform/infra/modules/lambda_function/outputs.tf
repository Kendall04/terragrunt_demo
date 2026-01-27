# ---------------------------------------------------------------------------
# Outputs
# Exposes the Lambda function and role identifiers for other modules.
# ---------------------------------------------------------------------------

output "lambda_arn" {
  value       = aws_lambda_function.this.arn
  description = "ARN of the deployed Lambda function."
}

output "lambda_name" {
  value       = aws_lambda_function.this.function_name
  description = "Name of the deployed Lambda function."
}

output "role_arn" {
  value       = var.role_arn
  description = "Role ARN used by the Lambda."
}
