output "sql_sa_secret_arn" {
  description = "ARN of the Secrets Manager secret storing the SQL Server SA password."
  value       = module.sql_sa_password.arn
}

output "sql_sa_secret_name" {
  description = "Name of the Secrets Manager secret storing the SQL Server SA password."
  value       = module.sql_sa_password.name
}

output "sql_app_secret_arn" {
  description = "ARN of the Secrets Manager secret storing the SQL Server app user password."
  value       = module.sql_app_password.arn
}

output "sql_app_secret_name" {
  description = "Name of the Secrets Manager secret storing the SQL Server app user password."
  value       = module.sql_app_password.name
}

output "db_secret_arn" {
  description = "ARN of the Secrets Manager secret storing the demo API DB connection string."
  value       = module.demo_api_db_connection_string.arn
}

output "db_secret_name" {
  description = "Name of the Secrets Manager secret storing the demo API DB connection string."
  value       = module.demo_api_db_connection_string.name
}

output "secret_kms_key_arn" {
  description = "KMS key ARN or ID used for Secrets Manager encryption."
  value       = var.kms_key_id
}
