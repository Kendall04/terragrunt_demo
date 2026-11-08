output "arn" {
  description = "Secret ARN."
  value       = aws_secretsmanager_secret.this.arn
}

output "id" {
  description = "Secret ID."
  value       = aws_secretsmanager_secret.this.id
}

output "name" {
  description = "Secret name."
  value       = aws_secretsmanager_secret.this.name
}
