output "kms_key_id" {
  description = "ID of the KMS Key."
  value       = aws_kms_key.kms_microservice.key_id
}

output "kms_key_arn" {
  description = "ARN of the KMS Key."
  value       = aws_kms_key.kms_microservice.arn
}

output "kms_alias_name" {
  description = "Alias name (including alias/ prefix)."
  value       = aws_kms_alias.alias.name
}

output "kms_alias_arn" {
  description = "ARN of the KMS alias."
  value       = aws_kms_alias.alias.arn
}
