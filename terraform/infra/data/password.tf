########################################
# 1) Randomly generated passwords
########################################

resource "random_password" "sql_sa_pwd" {
  length           = 24
  special          = true
  override_special = "!#$%&()*+,-./:<=>?@[]^_{|}~"
}

resource "random_password" "sql_app_pwd" {
  length           = 24
  special          = true
  override_special = "!#$%&()*+,-./:<=>?@[]^_{|}~"
}


########################################
# 2) Secrets for SA and APP users
########################################

# SA user password
resource "aws_secretsmanager_secret" "sql_sa" {
  name        = "sql-sa-password-${local.name}"
  description = "Password for the SQL Server SA login (${var.env})."
}

resource "aws_secretsmanager_secret_version" "sql_sa_val" {
  secret_id     = aws_secretsmanager_secret.sql_sa.id
  secret_string = random_password.sql_sa_pwd.result
}


# Application user password
resource "aws_secretsmanager_secret" "sql_app" {
  name        = "sql-app-password-${local.name}"
  description = "Password for the SQL Server application user (${var.env})."
}

resource "aws_secretsmanager_secret_version" "sql_app_val" {
  secret_id     = aws_secretsmanager_secret.sql_app.id
  secret_string = random_password.sql_app_pwd.result
}
