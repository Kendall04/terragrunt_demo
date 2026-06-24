#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${TG_ENV:-dev}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${ACCOUNT_ID:-}"
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
ECS_CLUSTER="${ECS_CLUSTER:-}"
ECS_SERVICE_BLUE="${ECS_SERVICE_BLUE:-}"
ECS_SERVICE_GREEN="${ECS_SERVICE_GREEN:-}"
ALB_LISTENER_ARN="${ALB_LISTENER_ARN:-}"
ALB_CANDIDATE_RULE_ARN="${ALB_CANDIDATE_RULE_ARN:-}"
TG_BLUE_ARN="${TG_BLUE_ARN:-}"
TG_GREEN_ARN="${TG_GREEN_ARN:-}"
SCALE_DOWN_RULE_NAME="${SCALE_DOWN_RULE_NAME:-}"
SCALE_DOWN_LAMBDA_ARN="${SCALE_DOWN_LAMBDA_ARN:-}"
DB_SECRET_ARN="${DB_SECRET_ARN:-}"
REQUIRE_DB_SECRET="false"

AWS_ARGS=()
ERRORS=0

usage() {
  cat <<'EOF'
Usage:
  scripts/check-deploy-resources.sh --environment dev|prod --region REGION \
    --account-id ACCOUNT --cluster CLUSTER --blue-service NAME --green-service NAME \
    --listener-arn ARN --candidate-rule-arn ARN --tg-blue-arn ARN --tg-green-arn ARN \
    --scale-down-rule-name NAME --scale-down-lambda-arn ARN [--db-secret-arn ARN] \
    [--require-db-secret true|false]

Read-only readiness check for ECS/ALB/Lambda/IAM resources required by the
blue/green deployment script.
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

error() {
  printf '[ERROR] %s\n' "$*" >&2
  ERRORS=$((ERRORS + 1))
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --environment|--env)
        ENVIRONMENT="${2:-}"
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
      --cluster)
        ECS_CLUSTER="${2:-}"
        shift 2
        ;;
      --blue-service)
        ECS_SERVICE_BLUE="${2:-}"
        shift 2
        ;;
      --green-service)
        ECS_SERVICE_GREEN="${2:-}"
        shift 2
        ;;
      --listener-arn)
        ALB_LISTENER_ARN="${2:-}"
        shift 2
        ;;
      --candidate-rule-arn)
        ALB_CANDIDATE_RULE_ARN="${2:-}"
        shift 2
        ;;
      --tg-blue-arn)
        TG_BLUE_ARN="${2:-}"
        shift 2
        ;;
      --tg-green-arn)
        TG_GREEN_ARN="${2:-}"
        shift 2
        ;;
      --scale-down-rule-name)
        SCALE_DOWN_RULE_NAME="${2:-}"
        shift 2
        ;;
      --scale-down-lambda-arn)
        SCALE_DOWN_LAMBDA_ARN="${2:-}"
        shift 2
        ;;
      --db-secret-arn|--db-secret-id)
        DB_SECRET_ARN="${2:-}"
        shift 2
        ;;
      --require-db-secret)
        REQUIRE_DB_SECRET="${2:-}"
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

set_aws_args() {
  AWS_ARGS=(--region "$AWS_REGION_NAME")
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    AWS_ARGS+=(--profile "$AWS_PROFILE_NAME")
  fi
}

resolve_account_id() {
  if [ -n "$ACCOUNT_ID" ]; then
    return 0
  fi

  ACCOUNT_ID="$(aws sts get-caller-identity \
    --query Account \
    --output text \
    "${AWS_ARGS[@]}")"
}

validate_inputs() {
  case "$ENVIRONMENT" in
    dev|prod) ;;
    *) die "--environment must be dev or prod." ;;
  esac

  if ! [[ "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    die "--account-id must be a 12-digit AWS account ID."
  fi

  case "$REQUIRE_DB_SECRET" in
    true|false) ;;
    *) die "--require-db-secret must be true or false." ;;
  esac

  local required=(
    ECS_CLUSTER
    ECS_SERVICE_BLUE
    ECS_SERVICE_GREEN
    ALB_LISTENER_ARN
    ALB_CANDIDATE_RULE_ARN
    TG_BLUE_ARN
    TG_GREEN_ARN
    SCALE_DOWN_RULE_NAME
    SCALE_DOWN_LAMBDA_ARN
  )

  for var_name in "${required[@]}"; do
    if [ -z "${!var_name:-}" ]; then
      error "Required deploy resource ${var_name} is empty for environment=${ENVIRONMENT}."
    fi
  done

  if [ "$REQUIRE_DB_SECRET" = "true" ] && [ -z "$DB_SECRET_ARN" ]; then
    error "DB_SECRET_ARN is required for environment=${ENVIRONMENT}."
  fi

  if [ -n "$DB_SECRET_ARN" ] && ! [[ "$DB_SECRET_ARN" =~ ^arn:aws:secretsmanager:[A-Za-z0-9-]+:[0-9]{12}:secret:.+ ]]; then
    error "DB secret must be a full Secrets Manager ARN."
  fi

  # The scale-down EventBridge rule is intentionally ephemeral. It is created
  # by the deploy script and may be deleted by the scale-down Lambda, so
  # readiness validates the rule name and Lambda, not pre-existence of the rule.
  if [ -n "$SCALE_DOWN_RULE_NAME" ] && ! [[ "$SCALE_DOWN_RULE_NAME" =~ ^[A-Za-z0-9._-]{1,64}$ ]]; then
    error "Scale-down EventBridge rule name contains unsupported characters."
  fi
}

check_aws_resources() {
  local clusters_json
  local services_json
  local failures
  local role_name

  if ! clusters_json="$(aws ecs describe-clusters --clusters "$ECS_CLUSTER" "${AWS_ARGS[@]}" 2>&1)"; then
    error "Unable to describe ECS cluster ${ECS_CLUSTER}: ${clusters_json}"
  elif [ "$(jq -r '.clusters | length' <<<"$clusters_json")" != "1" ]; then
    error "ECS cluster does not exist or is inactive: ${ECS_CLUSTER}"
  fi

  if ! services_json="$(aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE_BLUE" "$ECS_SERVICE_GREEN" "${AWS_ARGS[@]}" 2>&1)"; then
    error "Unable to describe ECS blue/green services: ${services_json}"
  else
    failures="$(jq -r '.failures | length' <<<"$services_json")"
    if [ "$failures" != "0" ]; then
      jq -r '.failures[] | "[ERROR] " + (.arn // .reason) + " " + (.reason // "")' <<<"$services_json" >&2
      ERRORS=$((ERRORS + failures))
    fi
  fi

  aws elbv2 describe-listeners --listener-arns "$ALB_LISTENER_ARN" "${AWS_ARGS[@]}" >/dev/null 2>&1 \
    || error "ALB listener does not exist or is not accessible."

  aws elbv2 describe-rules --rule-arns "$ALB_CANDIDATE_RULE_ARN" "${AWS_ARGS[@]}" >/dev/null 2>&1 \
    || error "ALB candidate listener rule does not exist or is not accessible."

  aws elbv2 describe-target-groups --target-group-arns "$TG_BLUE_ARN" "$TG_GREEN_ARN" "${AWS_ARGS[@]}" >/dev/null 2>&1 \
    || error "One or both ALB target groups do not exist or are not accessible."

  aws lambda get-function --function-name "$SCALE_DOWN_LAMBDA_ARN" "${AWS_ARGS[@]}" >/dev/null 2>&1 \
    || error "Scale-down Lambda does not exist or is not accessible."

  for role_name in \
    "demo-${ENVIRONMENT}-app-api-blue-exec-role" \
    "demo-${ENVIRONMENT}-app-api-blue-task-role" \
    "demo-${ENVIRONMENT}-app-api-green-exec-role" \
    "demo-${ENVIRONMENT}-app-api-green-task-role"; do
    aws iam get-role --role-name "$role_name" "${AWS_ARGS[@]}" >/dev/null 2>&1 \
      || error "Required ECS task role does not exist or is not accessible: ${role_name}"
  done
}

main() {
  parse_args "$@"
  require_command aws
  require_command jq
  set_aws_args
  resolve_account_id
  validate_inputs

  if [ "$ERRORS" -eq 0 ]; then
    check_aws_resources
  fi

  if [ "$ERRORS" -ne 0 ]; then
    die "Deployment resources are not ready for environment=${ENVIRONMENT}. Bootstrap the required Terragrunt layers before deploying."
  fi

  printf '[INFO] Deployment resources are ready for environment=%s.\n' "$ENVIRONMENT"
}

main "$@"
