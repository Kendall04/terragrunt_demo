#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

COMMAND="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

ENV_NAME="dev"
AWS_REGION_NAME="us-east-1"
AWS_PROFILE_NAME="terraform-lab"
PROJECT_NAME="demo"
USE_INSTANCE_ROLE="false"
DRY_RUN="false"
PLAN_ONLY="false"
YES="false"
CONFIRM_PROD="false"
CONFIRM_DISPOSABLE_DEMO="false"
YES_CONFIRM_DISPOSABLE_DEMO="false"

ACCOUNT_ID=""
STATE_BUCKET=""
LOCK_TABLE=""
AWS_PROFILE_ARGS=()

TEMP_FILES=()

cleanup_temp_files() {
  if [ "${#TEMP_FILES[@]}" -gt 0 ]; then
    rm -f "${TEMP_FILES[@]}"
  fi
}

trap cleanup_temp_files EXIT

usage() {
  cat <<'EOF'
Usage:
  scripts/bootstrap.sh <command> [options]

Commands:
  validate
  init-state
  apply-shared
  apply-secrets
  bootstrap-db-passwords
  apply-global
  apply-data
  bootstrap-db-connection
  apply-platform
  apply-apps
  apply-edge
  full-dev-bootstrap
  inspect-contaminated-state

Options:
  --env ENV              Environment name: dev or prod. Default: dev
  --region REGION        AWS region. Default: us-east-1
  --profile PROFILE      AWS CLI profile. Default: terraform-lab
  --use-instance-role    Use the EC2 instance role/default AWS credential chain
                         instead of passing an AWS CLI profile
  --project PROJECT      Project name used in secret naming. Must be demo.
  --plan-only            Run terragrunt plan instead of apply for apply-* commands
  --dry-run              Print commands without executing them
  --yes                  Non-interactive apply with Terraform auto-approve
  --confirm-prod         Required for any prod command
  --confirm-disposable-demo
                         Accepted only to make cleanup intent explicit
  --yes-confirm-disposable-demo
                         Accepted only to make cleanup intent explicit
  -h, --help             Show this help

Examples:
  scripts/bootstrap.sh validate --env dev --profile terraform-lab --region us-east-1
  scripts/bootstrap.sh init-state --env dev --profile terraform-lab --region us-east-1
  scripts/bootstrap.sh full-dev-bootstrap --profile terraform-lab --region us-east-1
  scripts/bootstrap.sh inspect-contaminated-state --env dev --profile terraform-lab --region us-east-1

This script never creates Terraform-managed secret values. DB secret values are
bootstrapped through scripts/bootstrap-db-secrets.sh outside Terraform.
full-dev-bootstrap stops before apps/fargate by default; run scripts/deploy.sh
deploy-app to publish an image, apply the ECS skeleton, and promote a color.
EOF
}

log() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

quote_cmd() {
  local quoted=""
  for arg in "$@"; do
    printf -v quoted '%s %q' "$quoted" "$arg"
  done
  redact_text "${quoted# }"
}

redact_text() {
  printf '%s\n' "$*" | sed -E \
    -e 's/[0-9]{12}/<aws-account-id>/g' \
    -e 's#arn:aws:[^[:space:]"'"'"']+#<aws-arn>#g' \
    -e 's#tfstate-demo-[A-Za-z0-9._-]+-[0-9]{12}#tfstate-demo-<env>-<aws-account-id>#g' \
    -e 's#tfstate-locks-[0-9]{12}#tfstate-locks-<aws-account-id>#g'
}

run_cmd() {
  if [ "$DRY_RUN" = "true" ]; then
    printf '[DRY-RUN] %s\n' "$(quote_cmd "$@")"
    return 0
  fi

  "$@"
}

run_in_dir() {
  local dir="$1"
  shift

  if [ "$DRY_RUN" = "true" ]; then
    printf '[DRY-RUN] cd %q && %s\n' "$dir" "$(quote_cmd "$@")"
    return 0
  fi

  (cd "$dir" && "$@")
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --env)
        ENV_NAME="${2:-}"
        shift 2
        ;;
      --region)
        AWS_REGION_NAME="${2:-}"
        shift 2
        ;;
      --profile)
        AWS_PROFILE_NAME="${2:-}"
        USE_INSTANCE_ROLE="false"
        shift 2
        ;;
      --use-instance-role)
        AWS_PROFILE_NAME=""
        USE_INSTANCE_ROLE="true"
        shift
        ;;
      --project)
        PROJECT_NAME="${2:-}"
        shift 2
        ;;
      --plan-only)
        PLAN_ONLY="true"
        shift
        ;;
      --dry-run)
        DRY_RUN="true"
        shift
        ;;
      --yes)
        YES="true"
        shift
        ;;
      --confirm-prod)
        CONFIRM_PROD="true"
        shift
        ;;
      --confirm-disposable-demo)
        CONFIRM_DISPOSABLE_DEMO="true"
        shift
        ;;
      --yes-confirm-disposable-demo)
        YES_CONFIRM_DISPOSABLE_DEMO="true"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

set_aws_profile_args() {
  AWS_PROFILE_ARGS=()
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    AWS_PROFILE_ARGS=(--profile "$AWS_PROFILE_NAME")
  fi
}

validate_env_name() {
  case "$ENV_NAME" in
    dev|prod) ;;
    *) die "Unsupported --env '$ENV_NAME'. Supported values: dev, prod." ;;
  esac
}

validate_project_name() {
  if [ "$PROJECT_NAME" != "demo" ]; then
    die "--project must be 'demo' in this repository because Terragrunt root.hcl uses project_name = \"demo\". Full multi-project support is intentionally not implemented."
  fi
}

require_prod_confirmation() {
  if [ "$ENV_NAME" = "prod" ] && [ "$CONFIRM_PROD" != "true" ]; then
    die "prod requires --confirm-prod. Refusing to continue."
  fi
}

resolve_identity_and_backend() {
  require_command aws
  set_aws_profile_args

  if [ "$DRY_RUN" = "true" ]; then
    ACCOUNT_ID="<aws-account-id>"
  else
    ACCOUNT_ID="$(aws sts get-caller-identity \
      --query Account \
      --output text \
      --region "$AWS_REGION_NAME" \
      "${AWS_PROFILE_ARGS[@]}")"
  fi

  STATE_BUCKET="${TF_STATE_BUCKET:-tfstate-demo-${ENV_NAME}-${ACCOUNT_ID}}"
  LOCK_TABLE="${TF_STATE_TABLE:-tfstate-locks-${ACCOUNT_ID}}"

  export TG_ENV="$ENV_NAME"
  export AWS_REGION="$AWS_REGION_NAME"
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    export AWS_PROFILE="$AWS_PROFILE_NAME"
  else
    unset AWS_PROFILE
  fi
  export TF_STATE_BUCKET="$STATE_BUCKET"
  export TF_STATE_TABLE="$LOCK_TABLE"
}

print_target() {
  log "Target environment"
  printf '  env             : %s\n' "$ENV_NAME"
  printf '  region          : %s\n' "$AWS_REGION_NAME"
  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    printf '  profile mode    : instance-role/default-chain\n'
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    printf '  profile         : %s\n' "$AWS_PROFILE_NAME"
  else
    printf '  profile mode    : default-chain\n'
  fi
  printf '  project         : %s\n' "$PROJECT_NAME"
  printf '  AWS account ID  : %s\n' "$(redact_text "$ACCOUNT_ID")"
  printf '  state bucket    : %s\n' "$(redact_text "$STATE_BUCKET")"
  printf '  lock table      : %s\n' "$(redact_text "$LOCK_TABLE")"
}

layer_dir() {
  case "$1" in
    shared) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/shared" ;;
    secrets) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/secrets" ;;
    global) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/global" ;;
    data) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/data" ;;
    platform) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/platform" ;;
    apps) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/apps/fargate" ;;
    edge) printf '%s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/edge" ;;
    *) die "Unknown layer: $1" ;;
  esac
}

validate_layout() {
  local env_root="$ROOT_DIR/terraform/live/$ENV_NAME"
  local required_layer

  [ -d "$env_root" ] || die "Missing Terragrunt environment: $env_root"
  [ -d "$env_root/secrets" ] || die "Missing centralized secrets root: $env_root/secrets"

  for required_layer in shared secrets global data platform edge; do
    [ -d "$(layer_dir "$required_layer")" ] || die "Missing layer directory: $(layer_dir "$required_layer")"
  done
  [ -d "$(layer_dir apps)" ] || die "Missing layer directory: $(layer_dir apps)"

  [ -f "$ROOT_DIR/scripts/bootstrap-db-secrets.sh" ] || die "Missing scripts/bootstrap-db-secrets.sh"
}

validate_backend_config() {
  local root_hcl="$ROOT_DIR/terraform/live/$ENV_NAME/root.hcl"

  [ -f "$root_hcl" ] || die "Missing Terragrunt root config: $root_hcl"
  rg -q 'get_env\("TF_STATE_BUCKET"' "$root_hcl" || die "root.hcl does not read TF_STATE_BUCKET."
  rg -q 'get_env\("TF_STATE_TABLE"' "$root_hcl" || die "root.hcl does not read TF_STATE_TABLE."

  log "Terragrunt backend config reads TF_STATE_BUCKET and TF_STATE_TABLE."
}

validate() {
  require_command aws
  require_command terraform
  require_command terragrunt
  require_command jq
  require_command rg

  validate_env_name
  require_prod_confirmation
  resolve_identity_and_backend
  validate_layout
  validate_backend_config
  print_target

  log "Validation completed."
}

init_state() {
  validate_env_name
  require_prod_confirmation
  resolve_identity_and_backend
  print_target

  log "Ensuring S3 state bucket exists: $(redact_text "$STATE_BUCKET")"
  if [ "$DRY_RUN" = "true" ]; then
    run_cmd aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION_NAME" "${AWS_PROFILE_ARGS[@]}"
  elif aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION_NAME" "${AWS_PROFILE_ARGS[@]}" >/dev/null 2>&1; then
    log "S3 bucket already exists."
  else
    log "Creating S3 bucket."
    if [ "$AWS_REGION_NAME" = "us-east-1" ]; then
      run_cmd aws s3api create-bucket \
        --bucket "$STATE_BUCKET" \
        --region "$AWS_REGION_NAME" \
        "${AWS_PROFILE_ARGS[@]}"
    else
      run_cmd aws s3api create-bucket \
        --bucket "$STATE_BUCKET" \
        --region "$AWS_REGION_NAME" \
        --create-bucket-configuration "LocationConstraint=$AWS_REGION_NAME" \
        "${AWS_PROFILE_ARGS[@]}"
    fi
  fi

  log "Enabling S3 bucket versioning."
  run_cmd aws s3api put-bucket-versioning \
    --bucket "$STATE_BUCKET" \
    --versioning-configuration Status=Enabled \
    --region "$AWS_REGION_NAME" \
    "${AWS_PROFILE_ARGS[@]}"

  log "Enabling S3 bucket default encryption."
  run_cmd aws s3api put-bucket-encryption \
    --bucket "$STATE_BUCKET" \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' \
    --region "$AWS_REGION_NAME" \
    "${AWS_PROFILE_ARGS[@]}"

  log "Enabling S3 public access block."
  run_cmd aws s3api put-public-access-block \
    --bucket "$STATE_BUCKET" \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
    --region "$AWS_REGION_NAME" \
    "${AWS_PROFILE_ARGS[@]}"

  log "Enabling bucket-owner-enforced object ownership."
  run_cmd aws s3api put-bucket-ownership-controls \
    --bucket "$STATE_BUCKET" \
    --ownership-controls 'Rules=[{ObjectOwnership=BucketOwnerEnforced}]' \
    --region "$AWS_REGION_NAME" \
    "${AWS_PROFILE_ARGS[@]}"

  if [ "$DRY_RUN" = "true" ]; then
    log "Skipping TLS bucket policy check in dry-run mode."
  elif aws s3api get-bucket-policy --bucket "$STATE_BUCKET" --region "$AWS_REGION_NAME" "${AWS_PROFILE_ARGS[@]}" >/dev/null 2>&1; then
    log "Bucket policy already exists; leaving it unchanged."
  else
    local policy_file
    policy_file="$(mktemp)"
    TEMP_FILES+=("$policy_file")
    cat >"$policy_file" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::$STATE_BUCKET",
        "arn:aws:s3:::$STATE_BUCKET/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
EOF
    log "Adding TLS-only bucket policy."
    aws s3api put-bucket-policy \
      --bucket "$STATE_BUCKET" \
      --policy "file://$policy_file" \
      --region "$AWS_REGION_NAME" \
      "${AWS_PROFILE_ARGS[@]}"
  fi

  log "Ensuring DynamoDB lock table exists: $(redact_text "$LOCK_TABLE")"
  if [ "$DRY_RUN" = "true" ]; then
    run_cmd aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION_NAME" "${AWS_PROFILE_ARGS[@]}"
  elif aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION_NAME" "${AWS_PROFILE_ARGS[@]}" >/dev/null 2>&1; then
    log "DynamoDB table already exists."
  else
    run_cmd aws dynamodb create-table \
      --table-name "$LOCK_TABLE" \
      --attribute-definitions AttributeName=LockID,AttributeType=S \
      --key-schema AttributeName=LockID,KeyType=HASH \
      --billing-mode PAY_PER_REQUEST \
      --region "$AWS_REGION_NAME" \
      "${AWS_PROFILE_ARGS[@]}"

    log "Waiting for DynamoDB lock table to become active."
    run_cmd aws dynamodb wait table-exists \
      --table-name "$LOCK_TABLE" \
      --region "$AWS_REGION_NAME" \
      "${AWS_PROFILE_ARGS[@]}"
  fi
}

terragrunt_layer() {
  local layer="$1"
  local dir
  dir="$(layer_dir "$layer")"

  validate_env_name
  require_prod_confirmation
  resolve_identity_and_backend
  validate_layout
  require_command terragrunt

  log "Running Terragrunt init for layer '$layer'."
  run_in_dir "$dir" terragrunt init --non-interactive -- -reconfigure

  if [ "$PLAN_ONLY" = "true" ]; then
    log "Running Terragrunt plan for layer '$layer'."
    run_in_dir "$dir" terragrunt plan --non-interactive -- -input=false
    return 0
  fi

  log "Running Terragrunt apply for layer '$layer'."
  if [ "$YES" = "true" ]; then
    run_in_dir "$dir" terragrunt apply --non-interactive -- -input=false -auto-approve
  else
    run_in_dir "$dir" terragrunt apply -- -input=false
  fi
}

bootstrap_db_passwords() {
  local profile_args=()

  validate_env_name
  require_prod_confirmation
  resolve_identity_and_backend
  validate_layout

  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    profile_args=(--use-instance-role)
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    profile_args=(--profile "$AWS_PROFILE_NAME")
  fi
  if [ "$CONFIRM_PROD" = "true" ]; then
    profile_args+=(--confirm-prod)
  fi

  log "Bootstrapping DB password secret values outside Terraform."
  run_cmd bash "$ROOT_DIR/scripts/bootstrap-db-secrets.sh" \
    --env "$ENV_NAME" \
    --project "$PROJECT_NAME" \
    --region "$AWS_REGION_NAME" \
    "${profile_args[@]}" \
    --skip-db-conn \
    --confirm-secret-value-bootstrap
}

bootstrap_db_connection() {
  local data_dir
  local db_host
  local profile_args=()

  validate_env_name
  require_prod_confirmation
  resolve_identity_and_backend
  validate_layout
  require_command terragrunt

  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    profile_args=(--use-instance-role)
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    profile_args=(--profile "$AWS_PROFILE_NAME")
  fi
  if [ "$CONFIRM_PROD" = "true" ]; then
    profile_args+=(--confirm-prod)
  fi

  data_dir="$(layer_dir data)"

  if [ "$DRY_RUN" = "true" ]; then
    log "Would read db_private_ip from data outputs."
    run_cmd bash "$ROOT_DIR/scripts/bootstrap-db-secrets.sh" \
      --env "$ENV_NAME" \
      --project "$PROJECT_NAME" \
      --region "$AWS_REGION_NAME" \
      "${profile_args[@]}" \
      --db-host "<db_private_ip_from_data_output>" \
      --confirm-secret-value-bootstrap
    return 0
  fi

  if db_host="$(cd "$data_dir" && terragrunt output -raw db_private_ip 2>/dev/null)"; then
    :
  else
    db_host=""
  fi
  if [ -z "$db_host" ] || [ "$db_host" = "None" ] || [ "$db_host" = "null" ]; then
    die "Could not read db_private_ip from $data_dir. Apply data first, then rerun bootstrap-db-connection."
  fi

  log "Bootstrapping DB connection-string secret value outside Terraform."
  bash "$ROOT_DIR/scripts/bootstrap-db-secrets.sh" \
    --env "$ENV_NAME" \
    --project "$PROJECT_NAME" \
    --region "$AWS_REGION_NAME" \
    "${profile_args[@]}" \
    --db-host "$db_host" \
    --confirm-secret-value-bootstrap
}

inspect_contaminated_state() {
  local audit_args

  validate_env_name
  validate_project_name
  require_prod_confirmation
  resolve_identity_and_backend
  validate_layout

  audit_args=("$ROOT_DIR/scripts/audit-terraform-state-secrets.sh" --env "$ENV_NAME" --region "$AWS_REGION_NAME" --historical)
  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    audit_args+=(--use-instance-role)
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    audit_args+=(--profile "$AWS_PROFILE_NAME")
  fi

  if [ "$DRY_RUN" = "true" ]; then
    audit_args+=(--dry-run)
  fi

  log "Delegating to the redacted state secret-risk audit script."
  run_cmd bash "${audit_args[@]}"
}

full_dev_bootstrap() {
  if [ "$ENV_NAME" != "dev" ]; then
    die "full-dev-bootstrap only supports --env dev."
  fi
  if [ "$PLAN_ONLY" = "true" ]; then
    die "full-dev-bootstrap does not support --plan-only because it includes remote-state setup and out-of-band secret bootstrap steps. Run individual apply-* commands with --plan-only instead."
  fi

  validate
  init_state

  print_target
  warn "This flow applies infrastructure. It does not run destroy or cleanup."

  terragrunt_layer shared
  terragrunt_layer secrets
  bootstrap_db_passwords
  terragrunt_layer global
  terragrunt_layer data
  bootstrap_db_connection
  terragrunt_layer platform

  log "Full dev bootstrap completed through apply-platform."
  warn "apps/fargate was not applied. Run scripts/deploy.sh deploy-app to apply the ECS skeleton and promote an immutable image."
  warn "edge/API Gateway remains separate. It can apply after global, but is more useful after apps are healthy."
}

main() {
  parse_args "$@"

  case "$COMMAND" in
    help|-h|--help) ;;
    *) validate_project_name ;;
  esac

  if [ "$CONFIRM_DISPOSABLE_DEMO" = "true" ] || [ "$YES_CONFIRM_DISPOSABLE_DEMO" = "true" ]; then
    log "Disposable demo cleanup confirmation flag accepted."
  fi

  if [ "$PLAN_ONLY" = "true" ]; then
    case "$COMMAND" in
      apply-*) ;;
      full-dev-bootstrap) ;;
      *) die "--plan-only is supported only for apply-* commands. It is rejected for '$COMMAND' because that command is not a Terraform plan." ;;
    esac
  fi

  case "$COMMAND" in
    help|-h|--help)
      usage
      ;;
    validate)
      validate
      ;;
    init-state)
      init_state
      ;;
    apply-shared)
      terragrunt_layer shared
      ;;
    apply-secrets)
      terragrunt_layer secrets
      ;;
    bootstrap-db-passwords)
      bootstrap_db_passwords
      ;;
    apply-global)
      terragrunt_layer global
      ;;
    apply-data)
      terragrunt_layer data
      ;;
    bootstrap-db-connection)
      bootstrap_db_connection
      ;;
    apply-platform)
      terragrunt_layer platform
      ;;
    apply-apps)
      terragrunt_layer apps
      ;;
    apply-edge)
      terragrunt_layer edge
      ;;
    full-dev-bootstrap)
      full_dev_bootstrap
      ;;
    inspect-contaminated-state)
      inspect_contaminated_state
      ;;
    cleanup-contaminated-state)
      die "Destructive cleanup is intentionally not automated. Run inspect-contaminated-state first, then follow the documented demo-only cleanup commands."
      ;;
    *)
      usage >&2
      die "Unknown command: $COMMAND"
      ;;
  esac
}

main "$@"
