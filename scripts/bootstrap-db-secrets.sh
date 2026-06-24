#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap-db-secrets.sh [options]

Bootstraps or rotates demo DB secret values outside Terraform.
Terraform creates only the Secrets Manager secret containers.
Direct execution is blocked unless --confirm-secret-value-bootstrap is passed.

Options:
  --env ENV              Environment name. Default: dev
  --project PROJECT      Project name. Default: demo; must match Terragrunt project_name
  --region REGION        AWS region. Default: us-east-1
  --profile PROFILE      Optional AWS CLI profile
  --use-instance-role    Use the default AWS credential chain / EC2 instance role
  --db-host HOST         SQL Server host/private IP for DB_CONN_STRING
  --db-name NAME         Application database name. Default: demodb
  --db-user USER         Application database user. Default: fargate_user
  --rotate              Rotate SQL passwords and DB connection string
  --force-update-db-conn Update an existing DB connection-string secret even
                         when it already has a different non-empty value
  --skip-db-conn        Do not create/update the DB connection string secret
  --confirm-prod        Required with --env prod
  --confirm-secret-value-bootstrap
                         Required acknowledgement because this script reads and
                         writes secret values without printing them
  -h, --help            Show this help

The script never prints generated secret values.
EOF
}

ENV_NAME="dev"
PROJECT="demo"
AWS_REGION="us-east-1"
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
DB_HOST=""
DB_NAME="demodb"
DB_USER="fargate_user"
ROTATE="false"
FORCE_UPDATE_DB_CONN="false"
SKIP_DB_CONN="false"
CONFIRM_PROD="false"
CONFIRM_SECRET_VALUE_BOOTSTRAP="false"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env)
      ENV_NAME="$2"
      shift 2
      ;;
    --project)
      PROJECT="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --profile)
      AWS_PROFILE_NAME="$2"
      USE_INSTANCE_ROLE="false"
      shift 2
      ;;
    --use-instance-role)
      AWS_PROFILE_NAME=""
      USE_INSTANCE_ROLE="true"
      shift
      ;;
    --db-host)
      DB_HOST="$2"
      shift 2
      ;;
    --db-name)
      DB_NAME="$2"
      shift 2
      ;;
    --db-user)
      DB_USER="$2"
      shift 2
      ;;
    --rotate)
      ROTATE="true"
      shift
      ;;
    --force-update-db-conn)
      FORCE_UPDATE_DB_CONN="true"
      shift
      ;;
    --skip-db-conn)
      SKIP_DB_CONN="true"
      shift
      ;;
    --confirm-prod)
      CONFIRM_PROD="true"
      shift
      ;;
    --confirm-secret-value-bootstrap)
      CONFIRM_SECRET_VALUE_BOOTSTRAP="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

AWS_ARGS=(--region "$AWS_REGION")
if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
  AWS_ARGS+=(--profile "$AWS_PROFILE_NAME")
fi

DATA_NAME="${PROJECT}-${ENV_NAME}-data"
SA_SECRET_NAME="${PROJECT}/${ENV_NAME}/db/sql-sa-password"
APP_SECRET_NAME="${PROJECT}/${ENV_NAME}/db/sql-app-password"
DB_CONN_SECRET_NAME="${PROJECT}/${ENV_NAME}/app/db-connection-string"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

validate_env_name() {
  case "$ENV_NAME" in
    dev|prod) ;;
    *) die "Unsupported --env '$ENV_NAME'. Supported values: dev, prod." ;;
  esac
}

require_prod_confirmation() {
  if [ "$ENV_NAME" = "prod" ] && [ "$CONFIRM_PROD" != "true" ]; then
    die "prod requires --confirm-prod. Refusing to continue."
  fi
}

require_secret_value_bootstrap_confirmation() {
  if [ "$CONFIRM_SECRET_VALUE_BOOTSTRAP" != "true" ]; then
    die "Refusing to read or write secret values without --confirm-secret-value-bootstrap. Prefer scripts/bootstrap.sh unless you are intentionally running this helper directly."
  fi
}

print_context() {
  echo "[INFO] Bootstrapping DB secrets for project=${PROJECT}, env=${ENV_NAME}, region=${AWS_REGION}."
  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    echo "[INFO] AWS credential mode: instance-role/default-chain."
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    echo "[INFO] AWS credential mode: named profile."
  else
    echo "[INFO] AWS credential mode: default-chain."
  fi
}

require_secret_container() {
  local secret_name="$1"
  local label="$2"
  local deleted_date

  if ! deleted_date="$(aws secretsmanager describe-secret \
    --secret-id "$secret_name" \
    --query DeletedDate \
    --output text \
    "${AWS_ARGS[@]}" 2>/dev/null)"; then
    die "$label secret container does not exist. Run Terraform first so it creates secret metadata, then rerun this script."
  fi

  if [ -n "$deleted_date" ] && [ "$deleted_date" != "None" ]; then
    die "$label secret container is scheduled for deletion. This script will not restore or force-delete secrets."
  fi
}

get_secret_value() {
  local secret_name="$1"

  aws secretsmanager get-secret-value \
    --secret-id "$secret_name" \
    --query SecretString \
    --output text \
    "${AWS_ARGS[@]}" 2>/dev/null || true
}

put_secret_value_from_stdin() {
  local secret_name="$1"

  aws secretsmanager put-secret-value \
    --secret-id "$secret_name" \
    --secret-string file:///dev/stdin \
    "${AWS_ARGS[@]}" >/dev/null
}

generate_sql_password() {
  # Avoid semicolons so the value is safe inside a SQL Server connection string.
  printf 'A1!%s' "$(openssl rand -hex 18)"
}

ensure_password_secret() {
  local secret_name="$1"
  local label="$2"
  local current_value

  current_value="$(get_secret_value "$secret_name")"
  if [ -n "$current_value" ] && [ "$current_value" != "None" ] && [ "$ROTATE" != "true" ]; then
    echo "[OK] $label secret already has a value; leaving it unchanged."
    return 0
  fi

  generate_sql_password | put_secret_value_from_stdin "$secret_name"
  if [ "$ROTATE" = "true" ]; then
    echo "[OK] Rotated $label secret value."
  else
    echo "[OK] Bootstrapped $label secret value."
  fi
}

discover_db_host() {
  aws ec2 describe-instances \
    --filters \
      "Name=tag:Name,Values=${DATA_NAME}-sql-instance" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].PrivateIpAddress | [0]' \
    --output text \
    "${AWS_ARGS[@]}" 2>/dev/null || true
}

ensure_db_connection_secret() {
  local app_password="$1"
  local current_value
  local desired_value

  if [ "$SKIP_DB_CONN" = "true" ]; then
    echo "[SKIP] DB connection string secret update skipped."
    return 0
  fi

  if [ -z "$DB_HOST" ]; then
    DB_HOST="$(discover_db_host)"
  fi

  if [ -z "$DB_HOST" ] || [ "$DB_HOST" = "None" ]; then
    echo "[WARN] DB host/private IP was not provided or discoverable; DB_CONN_STRING was not updated." >&2
    echo "       Rerun with --db-host <private-ip> after the DB instance exists." >&2
    return 0
  fi

  desired_value="Server=${DB_HOST},1433;Database=${DB_NAME};User Id=${DB_USER};Password=${app_password};Encrypt=True;TrustServerCertificate=True;"
  current_value="$(get_secret_value "$DB_CONN_SECRET_NAME")"

  if [ "$current_value" = "$desired_value" ] && [ "$ROTATE" != "true" ]; then
    echo "[OK] DB connection string secret is already up to date."
    return 0
  fi

  if [ -n "$current_value" ] && [ "$current_value" != "None" ] && [ "$ROTATE" != "true" ] && [ "$FORCE_UPDATE_DB_CONN" != "true" ]; then
    echo "[WARN] DB connection string secret already has a different non-empty value; leaving it unchanged." >&2
    echo "       Rerun with --force-update-db-conn for a deliberate host/config change, or --rotate for credential rotation." >&2
    return 0
  fi

  printf '%s' "$desired_value" | put_secret_value_from_stdin "$DB_CONN_SECRET_NAME"
  echo "[OK] Updated DB connection string secret."
}

main() {
  command -v aws >/dev/null || {
    echo "ERROR: aws CLI is required." >&2
    exit 1
  }
  command -v openssl >/dev/null || {
    echo "ERROR: openssl is required to generate passwords." >&2
    exit 1
  }

  validate_env_name
  require_prod_confirmation
  require_secret_value_bootstrap_confirmation

  if [ "$PROJECT" != "demo" ]; then
    die "--project must be 'demo' in this repository because Terragrunt root.hcl uses project_name = \"demo\". Full multi-project support is intentionally not implemented."
  fi

  print_context
  echo "[INFO] Required IAM: secretsmanager:DescribeSecret/GetSecretValue/PutSecretValue, ec2:DescribeInstances when DB host auto-discovery is used, and KMS Encrypt/GenerateDataKey/Decrypt if the secrets use a customer-managed KMS key."
  if [ "$ROTATE" = "true" ]; then
    echo "[WARN] --rotate updates Secrets Manager values only. For an existing SQL Server, update/recreate DB credentials before routing app traffic to rotated values."
  fi

  require_secret_container "$SA_SECRET_NAME" "SQL SA"
  require_secret_container "$APP_SECRET_NAME" "SQL app user"
  require_secret_container "$DB_CONN_SECRET_NAME" "DB connection string"

  ensure_password_secret "$SA_SECRET_NAME" "SQL SA"
  ensure_password_secret "$APP_SECRET_NAME" "SQL app user"

  app_password="$(get_secret_value "$APP_SECRET_NAME")"
  if [ -z "$app_password" ] || [ "$app_password" = "None" ]; then
    echo "ERROR: SQL app user secret has no value after bootstrap." >&2
    exit 1
  fi

  ensure_db_connection_secret "$app_password"
  unset app_password

  echo "[DONE] Secret bootstrap completed without printing secret values."
}

main
