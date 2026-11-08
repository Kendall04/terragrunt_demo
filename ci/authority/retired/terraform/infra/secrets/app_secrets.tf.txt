module "demo_api_db_connection_string" {
  source = "./modules/secret_metadata"

  name                    = "${var.project}/${var.env}/app/db-connection-string"
  description             = "Connection string for demo API SQL Server. Value is bootstrapped outside Terraform."
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = var.secret_recovery_window_in_days
  tags                    = local.tags
}
