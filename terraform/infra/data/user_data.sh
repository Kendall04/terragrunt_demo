#!/bin/bash
# ==============================================================
# cloud-init bootstrap script
# Ubuntu 22.04 + SQL Server 2022 Express + application DB setup
# ==============================================================
# Do not enable shell tracing here. This script handles DB passwords fetched
# from Secrets Manager, and tracing would leak them into cloud-init logs.
set -euo pipefail

# ------------------------------
# Environment variables injected
# ------------------------------
REGION="${AWS_REGION}"

APP_DB='${APP_DB}'
APP_USER='${APP_USER}'

SA_SECRET_ARN='${SA_SECRET_ARN}'
APP_SECRET_ARN='${APP_SECRET_ARN}'

export DEBIAN_FRONTEND=noninteractive

# ---------------------------------------
# 1) Install base packages and AWS CLI
# ---------------------------------------
apt-get update -y
apt-get install -y curl ca-certificates gnupg lsb-release software-properties-common awscli

# -----------------------------------------------------
# Retrieve SA and application passwords from Secrets Manager
# -----------------------------------------------------
get_secret_value() {
  local secret_id="$1"
  local label="$2"
  local attempts=360
  local delay_seconds=10

  for attempt in $(seq 1 "$attempts"); do
    if value=$(aws secretsmanager get-secret-value \
      --secret-id "$secret_id" \
      --region "$REGION" \
      --query SecretString \
      --output text 2>/tmp/sql-secret-fetch-error.log); then
      if [ -n "$value" ] && [ "$value" != "None" ]; then
        printf '%s' "$value"
        return 0
      fi
    fi

    echo "Waiting for $label secret value to be available ($${attempt}/$${attempts})..." >&2
    sleep "$delay_seconds"
  done

  echo "ERROR: $label secret value was not available in Secrets Manager." >&2
  if [ -s /tmp/sql-secret-fetch-error.log ]; then
    sed 's/[[:cntrl:]]//g' /tmp/sql-secret-fetch-error.log >&2
  fi
  return 1
}

SA_PASS="$(get_secret_value "$SA_SECRET_ARN" "SQL SA")"
APP_PASS="$(get_secret_value "$APP_SECRET_ARN" "SQL app user")"

# -----------------------------------------------------
# 2) Configure Microsoft repositories securely (keyrings)
# -----------------------------------------------------
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
  | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg

# SQL Server 2022 + tools repositories
echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy main" \
  > /etc/apt/sources.list.d/mssql-server-2022.list

echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" \
  > /etc/apt/sources.list.d/msprod.list

apt-get update -y

# ------------------------------
# 3) Install SQL Server engine
# ------------------------------
ACCEPT_EULA=Y apt-get install -y mssql-server

# ----------------------------------------------
# 4) Non-interactive SQL Server setup (Express)
# ----------------------------------------------
ACCEPT_EULA=Y MSSQL_PID=Express MSSQL_SA_PASSWORD="$SA_PASS" \
  /opt/mssql/bin/mssql-conf -n setup

# ------------------------------
# 5) Start SQL Server service
# ------------------------------
systemctl enable --now mssql-server

# -------------------------------------------------
# 6) Install sqlcmd tools + export PATH for system
# -------------------------------------------------
ACCEPT_EULA=Y apt-get install -y mssql-tools18 unixodbc-dev

echo 'export PATH=$PATH:/opt/mssql-tools18/bin' > /etc/profile.d/mssql-tools.sh
export PATH=$PATH:/opt/mssql-tools18/bin

# -------------------------------------------
# 7) Wait a bit for SQL to become fully ready
# -------------------------------------------
sleep 10

# -------------------------------------------
# 8) Create database if it does not exist
# -------------------------------------------
SQLCMDPASSWORD="$SA_PASS" sqlcmd -S localhost -C -U SA -b -Q \
  "IF DB_ID('$APP_DB') IS NULL CREATE DATABASE [$APP_DB];"

# ----------------------------------------------------
# 9) Create login and grant DB permissions to the user
# ----------------------------------------------------
APP_PASS_SQL="$(printf '%s' "$APP_PASS" | sed "s/'/''/g")"

SQLCMDPASSWORD="$SA_PASS" sqlcmd -S localhost -C -U SA -b -d "$APP_DB" <<SQL
IF NOT EXISTS (SELECT * FROM sys.sql_logins WHERE name = N'$APP_USER')
  CREATE LOGIN [$APP_USER] WITH PASSWORD = N'$APP_PASS_SQL', CHECK_POLICY = OFF;

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = N'$APP_USER')
  CREATE USER [$APP_USER] FOR LOGIN [$APP_USER];

ALTER ROLE db_owner ADD MEMBER [$APP_USER];
SQL

# ----------------------------------------------------
# Done
# ----------------------------------------------------
echo "SQL Server 2022 Express is ready with DB '$APP_DB' and user '$APP_USER'." \
  > /var/log/sql_install_done

unset SA_PASS APP_PASS
unset APP_PASS_SQL
