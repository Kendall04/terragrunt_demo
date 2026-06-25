#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENV_NAME="dev"
AWS_REGION_NAME="us-east-1"
ACCOUNT_ID=""
COLOR=""
IMAGE_URI=""
DB_SECRET_ID=""
KMS_KEY_ID=""
OUTPUT_FILE=""
TEMPLATE_FILE="$ROOT_DIR/demo-api/deploy/task-definition.template.json"

usage() {
  cat <<'EOF'
Usage:
  scripts/render-demo-api-taskdef.sh --env ENV --region REGION --account-id ACCOUNT \
    --color blue|green --image-uri ECR_URI@sha256:... --db-secret-id ARN --output FILE

Renders the versioned Demo API ECS task definition template. The rendered output
is suitable for aws ecs register-task-definition --cli-input-json file://FILE.
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
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
      --account-id)
        ACCOUNT_ID="${2:-}"
        shift 2
        ;;
      --color)
        COLOR="${2:-}"
        shift 2
        ;;
      --image-uri)
        IMAGE_URI="${2:-}"
        shift 2
        ;;
      --db-secret-id|--db-secret-arn)
        DB_SECRET_ID="${2:-}"
        shift 2
        ;;
      --kms-key-id)
        KMS_KEY_ID="${2:-}"
        shift 2
        ;;
      --template)
        TEMPLATE_FILE="${2:-}"
        shift 2
        ;;
      --output)
        OUTPUT_FILE="${2:-}"
        shift 2
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

validate_args() {
  case "$ENV_NAME" in
    dev|prod) ;;
    *) die "Unsupported --env '$ENV_NAME'. Supported values: dev, prod." ;;
  esac

  case "$COLOR" in
    blue|green) ;;
    *) die "--color must be blue or green." ;;
  esac

  if ! [[ "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    die "--account-id must be a 12-digit AWS account ID."
  fi

  if ! [[ "$IMAGE_URI" =~ ^.+@sha256:[a-f0-9]{64}$ ]]; then
    die "--image-uri must be an immutable ECR image URI ending in @sha256:<64 lowercase hex chars>."
  fi

  if ! [[ "$DB_SECRET_ID" =~ ^arn:aws:secretsmanager:[A-Za-z0-9-]+:[0-9]{12}:secret:.+ ]]; then
    die "--db-secret-id must be a full Secrets Manager ARN."
  fi

  [ -f "$TEMPLATE_FILE" ] || die "Template file not found: $TEMPLATE_FILE"
  [ -n "$OUTPUT_FILE" ] || die "--output is required."

  if [ -z "$KMS_KEY_ID" ]; then
    KMS_KEY_ID="alias/${ENV_NAME}-kms-service"
  fi
}

render_task_definition() {
  local app_name
  local execution_role_arn
  local task_role_arn
  local log_group
  local output_dir

  app_name="demo-${ENV_NAME}-app-api-${COLOR}"
  execution_role_arn="arn:aws:iam::${ACCOUNT_ID}:role/${app_name}-exec-role"
  task_role_arn="arn:aws:iam::${ACCOUNT_ID}:role/${app_name}-task-role"
  log_group="/aws/ecs/${app_name}"
  output_dir="$(dirname "$OUTPUT_FILE")"

  mkdir -p "$output_dir"

  jq \
    --arg family "$app_name" \
    --arg container_name "$app_name" \
    --arg image_uri "$IMAGE_URI" \
    --arg execution_role_arn "$execution_role_arn" \
    --arg task_role_arn "$task_role_arn" \
    --arg aws_region "$AWS_REGION_NAME" \
    --arg app_env "$ENV_NAME" \
    --arg deployment "$COLOR" \
    --arg kms_key_id "$KMS_KEY_ID" \
    --arg db_secret_id "$DB_SECRET_ID" \
    --arg log_group "$log_group" \
    '
      def set_env($name; $value):
        .containerDefinitions[0].environment |= map(
          if .name == $name then .value = $value else . end
        );

      .family = $family
      | .executionRoleArn = $execution_role_arn
      | .taskRoleArn = $task_role_arn
      | .containerDefinitions[0].name = $container_name
      | .containerDefinitions[0].image = $image_uri
      | set_env("AWS_REGION"; $aws_region)
      | set_env("APP_ENV"; $app_env)
      | set_env("DEPLOYMENT"; $deployment)
      | set_env("KMS_KEY_ID"; $kms_key_id)
      | .containerDefinitions[0].secrets[0].valueFrom = $db_secret_id
      | .containerDefinitions[0].logConfiguration.options["awslogs-group"] = $log_group
      | .containerDefinitions[0].logConfiguration.options["awslogs-region"] = $aws_region
      | .containerDefinitions[0].logConfiguration.options["awslogs-stream-prefix"] = $container_name
    ' "$TEMPLATE_FILE" > "$OUTPUT_FILE"
}

main() {
  parse_args "$@"
  require_command jq
  validate_args
  render_task_definition
}

main "$@"
