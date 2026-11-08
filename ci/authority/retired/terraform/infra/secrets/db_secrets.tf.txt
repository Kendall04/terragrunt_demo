module "sql_sa_password" {
  source = "./modules/secret_metadata"

  name                    = "${var.project}/${var.env}/db/sql-sa-password"
  description             = "Password for the SQL Server SA login (${var.env})."
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = var.secret_recovery_window_in_days
  tags                    = local.tags
}

module "sql_app_password" {
  source = "./modules/secret_metadata"

  name                    = "${var.project}/${var.env}/db/sql-app-password"
  description             = "Password for the SQL Server application user (${var.env})."
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = var.secret_recovery_window_in_days
  tags                    = local.tags
}
