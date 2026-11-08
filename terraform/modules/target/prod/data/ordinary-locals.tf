locals {
  name = "demo-prod-data"

  tags = {
    Project     = "demo"
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}

locals {
  sql_full_user_data = templatefile("${path.module}/../../../../infra/data/user_data.sh", {
    AWS_REGION            = var.region
    APP_DB                = var.app_db
    APP_USER              = var.app_user
    SA_SECRET_ARN         = local.expected["prod/sa"]
    APP_SECRET_ARN        = local.expected["prod/db-user"]
    SQL_SECURITY_PROFILE  = var.sql_database_security == null ? "legacy-v1" : "validated-v2"
    MIGRATION_USER        = var.sql_database_security == null ? "" : var.sql_database_security.migration_user
    MIGRATION_SECRET_ARN  = var.sql_database_security == null ? "" : var.sql_database_security.migration_secret_arn
    SQL_PRINCIPAL_HELPERS = var.sql_database_security == null ? "" : trimspace(file("${path.module}/../../../../infra/data/sql-principals.sh.gz.b64"))
    SQL_PRINCIPAL_SHA256  = filesha256("${path.module}/../../../../infra/data/sql-principals.sh")
  })
}
