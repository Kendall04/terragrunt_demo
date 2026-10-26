locals {
  name = "demo-dev-data"

  tags = {
    Project     = "demo"
    Environment = "dev"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}

locals {
  sql_base_user_data = templatefile("${path.module}/../../../../infra/data/user_data.sh", {
    AWS_REGION     = var.region
    APP_DB         = var.app_db
    APP_USER       = var.app_user
    SA_SECRET_ARN  = local.expected["dev/sa"]
    APP_SECRET_ARN = local.expected["dev/db-user"]
  })
}
