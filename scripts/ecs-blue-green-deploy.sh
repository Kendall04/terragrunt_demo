#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENV_NAME="${TG_ENV:-dev}"
AWS_REGION_NAME="${AWS_REGION:-us-east-1}"
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
ACCOUNT_ID="${ACCOUNT_ID:-}"
IMAGE_URI="${IMAGE_URI:-}"
ECS_CLUSTER="${ECS_CLUSTER:-}"
ECS_SERVICE_BLUE="${ECS_SERVICE_BLUE:-}"
ECS_SERVICE_GREEN="${ECS_SERVICE_GREEN:-}"
ALB_LISTENER_ARN="${ALB_LISTENER_ARN:-}"
ALB_CANDIDATE_RULE_ARN="${ALB_CANDIDATE_RULE_ARN:-}"
TG_BLUE_ARN="${TG_BLUE_ARN:-}"
TG_GREEN_ARN="${TG_GREEN_ARN:-}"
SCALE_DOWN_RULE_NAME="${SCALE_DOWN_RULE_NAME:-}"
SCALE_DOWN_LAMBDA_ARN="${SCALE_DOWN_LAMBDA_ARN:-}"
DB_SECRET_ID="${DB_SECRET_ID:-}"
DESIRED_COUNT="1"
DRAIN_DELAY_MINUTES="5"
TARGET_HEALTH_MAX_WAIT_SECONDS="${TARGET_HEALTH_MAX_WAIT_SECONDS:-300}"
TARGET_HEALTH_POLL_INTERVAL_SECONDS="${TARGET_HEALTH_POLL_INTERVAL_SECONDS:-10}"
OUTPUT_ENV_FILE=""

AWS_ARGS=()
TEMP_DIR=""

ACTIVE_COLOR=""
INACTIVE_COLOR=""
ACTIVE_SERVICE=""
INACTIVE_SERVICE=""
ACTIVE_TG=""
INACTIVE_TG=""
NEW_TASK_DEFINITION_ARN=""

cleanup() {
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
  fi
}

trap cleanup EXIT

usage() {
  cat <<'EOF'
Usage:
  scripts/ecs-blue-green-deploy.sh --env ENV --region REGION --image-uri ECR_URI@sha256:... \
    --cluster CLUSTER --blue-service NAME --green-service NAME \
    --listener-arn ARN --candidate-rule-arn ARN --tg-blue-arn ARN --tg-green-arn ARN \
    --scale-down-rule-name NAME --scale-down-lambda-arn ARN [options]

Options:
  --account-id ACCOUNT        AWS account ID. Defaults to sts get-caller-identity.
  --db-secret-id ARN          DB connection Secrets Manager ARN. Defaults to the current inactive task definition value.
  --desired-count N           Desired task count for promoted color. Default: 1
  --drain-delay-minutes N     Delay before scaling down old color. Default: 5
  --target-health-timeout N   Seconds to wait for ALB target health. Default: 300
  --target-health-interval N  Seconds between target health polls. Default: 10
  --profile PROFILE           AWS CLI profile for local runs
  --use-instance-role         Use default AWS credential chain and do not pass a profile
  --output-env FILE           Append ACTIVE_COLOR/ACTIVE_SERVICE outputs to FILE
  -h, --help                  Show this help
EOF
}

log() {
  printf '[INFO] %s\n' "$*"
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

redact_text() {
  printf '%s\n' "$*" | sed -E \
    -e 's/[0-9]{12}/<aws-account-id>/g' \
    -e 's#arn:aws:[^[:space:]"'"'"']+#<aws-arn>#g' \
    -e 's#[0-9]{12}\.dkr\.ecr\.([A-Za-z0-9-]+)\.amazonaws\.com#<aws-account-id>.dkr.ecr.\1.amazonaws.com#g'
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
      --account-id)
        ACCOUNT_ID="${2:-}"
        shift 2
        ;;
      --image-uri)
        IMAGE_URI="${2:-}"
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
      --db-secret-id|--db-secret-arn)
        DB_SECRET_ID="${2:-}"
        shift 2
        ;;
      --desired-count)
        DESIRED_COUNT="${2:-}"
        shift 2
        ;;
      --drain-delay-minutes)
        DRAIN_DELAY_MINUTES="${2:-}"
        shift 2
        ;;
      --target-health-timeout|--target-health-timeout-seconds)
        TARGET_HEALTH_MAX_WAIT_SECONDS="${2:-}"
        shift 2
        ;;
      --target-health-interval|--target-health-interval-seconds)
        TARGET_HEALTH_POLL_INTERVAL_SECONDS="${2:-}"
        shift 2
        ;;
      --output-env)
        OUTPUT_ENV_FILE="${2:-}"
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

validate_args() {
  case "$ENV_NAME" in
    dev|prod) ;;
    *) die "Unsupported --env '$ENV_NAME'. Supported values: dev, prod." ;;
  esac

  if ! [[ "$ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
    die "Could not resolve a valid 12-digit AWS account ID."
  fi

  if ! [[ "$IMAGE_URI" =~ ^.+@sha256:[a-f0-9]{64}$ ]]; then
    die "--image-uri must be immutable and end in @sha256:<64 lowercase hex chars>."
  fi

  if ! [[ "$DESIRED_COUNT" =~ ^[0-9]+$ ]] || [ "$DESIRED_COUNT" -lt 1 ]; then
    die "--desired-count must be a positive integer."
  fi

  if ! [[ "$DRAIN_DELAY_MINUTES" =~ ^[0-9]+$ ]] || [ "$DRAIN_DELAY_MINUTES" -lt 1 ]; then
    die "--drain-delay-minutes must be a positive integer."
  fi

  if ! [[ "$TARGET_HEALTH_MAX_WAIT_SECONDS" =~ ^[0-9]+$ ]] || [ "$TARGET_HEALTH_MAX_WAIT_SECONDS" -lt 1 ]; then
    die "--target-health-timeout must be a positive integer."
  fi

  if ! [[ "$TARGET_HEALTH_POLL_INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [ "$TARGET_HEALTH_POLL_INTERVAL_SECONDS" -lt 1 ]; then
    die "--target-health-interval must be a positive integer."
  fi

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
      die "Required value $var_name is empty."
    fi
  done
}

validate_db_secret_id() {
  if ! [[ "$DB_SECRET_ID" =~ ^arn:aws:secretsmanager:[A-Za-z0-9-]+:[0-9]{12}:secret:.+ ]]; then
    die "DB secret valueFrom must be a full Secrets Manager ARN. Got: $(redact_text "$DB_SECRET_ID")"
  fi
}

preflight_resources() {
  local services_json
  local failures

  aws elbv2 describe-listeners \
    --listener-arns "$ALB_LISTENER_ARN" \
    "${AWS_ARGS[@]}" >/dev/null

  aws elbv2 describe-rules \
    --rule-arns "$ALB_CANDIDATE_RULE_ARN" \
    "${AWS_ARGS[@]}" >/dev/null

  aws elbv2 describe-target-groups \
    --target-group-arns "$TG_BLUE_ARN" "$TG_GREEN_ARN" \
    "${AWS_ARGS[@]}" >/dev/null

  services_json="$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE_BLUE" "$ECS_SERVICE_GREEN" \
    "${AWS_ARGS[@]}")"

  failures="$(jq -r '.failures | length' <<<"$services_json")"
  if [ "$failures" != "0" ]; then
    jq -r '.failures[] | (.arn // .reason) + " " + (.reason // "")' <<<"$services_json" >&2
    die "Unable to describe one or more blue/green ECS services."
  fi
}

detect_blue_green_state() {
  local listener_json
  local rule_json
  local default_tg
  local candidate_tg

  listener_json="$(aws elbv2 describe-listeners \
    --listener-arns "$ALB_LISTENER_ARN" \
    "${AWS_ARGS[@]}")"

  default_tg="$(jq -er '
    .Listeners[0].DefaultActions[0]
    | .TargetGroupArn // .ForwardConfig.TargetGroups[0].TargetGroupArn
  ' <<<"$listener_json")"

  rule_json="$(aws elbv2 describe-rules \
    --rule-arns "$ALB_CANDIDATE_RULE_ARN" \
    "${AWS_ARGS[@]}")"

  candidate_tg="$(jq -er '
    .Rules[0].Actions[0]
    | .TargetGroupArn // .ForwardConfig.TargetGroups[0].TargetGroupArn
  ' <<<"$rule_json")"

  if [ "$default_tg" = "$TG_BLUE_ARN" ]; then
    ACTIVE_COLOR="blue"
    ACTIVE_TG="$TG_BLUE_ARN"
    ACTIVE_SERVICE="$ECS_SERVICE_BLUE"
    INACTIVE_COLOR="green"
    INACTIVE_TG="$TG_GREEN_ARN"
    INACTIVE_SERVICE="$ECS_SERVICE_GREEN"
  elif [ "$default_tg" = "$TG_GREEN_ARN" ]; then
    ACTIVE_COLOR="green"
    ACTIVE_TG="$TG_GREEN_ARN"
    ACTIVE_SERVICE="$ECS_SERVICE_GREEN"
    INACTIVE_COLOR="blue"
    INACTIVE_TG="$TG_BLUE_ARN"
    INACTIVE_SERVICE="$ECS_SERVICE_BLUE"
  else
    die "ALB default target group does not match the expected blue/green target groups."
  fi

  if [ "$candidate_tg" != "$INACTIVE_TG" ]; then
    die "ALB candidate rule is not pointing at the inactive target group."
  fi

  log "Active color: $ACTIVE_COLOR; deploying to inactive color: $INACTIVE_COLOR"
}

resolve_db_secret_id() {
  local task_definition_arn
  local task_definition_json

  if [ -n "$DB_SECRET_ID" ]; then
    validate_db_secret_id
    return 0
  fi

  task_definition_arn="$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER" \
    --services "$INACTIVE_SERVICE" \
    --query 'services[0].taskDefinition' \
    --output text \
    "${AWS_ARGS[@]}")"

  if [ -z "$task_definition_arn" ] || [ "$task_definition_arn" = "None" ] || [ "$task_definition_arn" = "null" ]; then
    die "Could not resolve current task definition for inactive service: $INACTIVE_SERVICE"
  fi

  task_definition_json="$(aws ecs describe-task-definition \
    --task-definition "$task_definition_arn" \
    "${AWS_ARGS[@]}")"

  DB_SECRET_ID="$(jq -er '
    .taskDefinition.containerDefinitions[]
    | .secrets[]?
    | select(.name == "DB_CONN_STRING")
    | .valueFrom
  ' <<<"$task_definition_json")"

  validate_db_secret_id
  log "Resolved DB secret ARN from inactive service task definition."
}

wait_for_no_running_tasks() {
  local service_name="$1"
  local tasks

  for _ in {1..30}; do
    tasks="$(aws ecs list-tasks \
      --cluster "$ECS_CLUSTER" \
      --service-name "$service_name" \
      --desired-status RUNNING \
      --query 'length(taskArns)' \
      --output text \
      "${AWS_ARGS[@]}")"

    if [ "$tasks" = "0" ]; then
      return 0
    fi

    log "Still RUNNING tasks on $service_name: $tasks"
    sleep 2
  done

  die "Service still has running tasks after waiting: $service_name"
}

stop_inactive_service() {
  log "Stopping inactive service before task definition replacement: $INACTIVE_SERVICE"
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$INACTIVE_SERVICE" \
    --desired-count 0 \
    "${AWS_ARGS[@]}" >/dev/null

  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$INACTIVE_SERVICE" \
    "${AWS_ARGS[@]}"

  wait_for_no_running_tasks "$INACTIVE_SERVICE"
}

register_rendered_task_definition() {
  local taskdef_file

  TEMP_DIR="$(mktemp -d)"
  taskdef_file="$TEMP_DIR/task-definition-${INACTIVE_COLOR}.json"

  "$ROOT_DIR/scripts/render-demo-api-taskdef.sh" \
    --env "$ENV_NAME" \
    --region "$AWS_REGION_NAME" \
    --account-id "$ACCOUNT_ID" \
    --color "$INACTIVE_COLOR" \
    --image-uri "$IMAGE_URI" \
    --db-secret-id "$DB_SECRET_ID" \
    --output "$taskdef_file"

  NEW_TASK_DEFINITION_ARN="$(aws ecs register-task-definition \
    --cli-input-json "file://$taskdef_file" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text \
    "${AWS_ARGS[@]}")"

  log "Registered task definition for $INACTIVE_COLOR: $(redact_text "$NEW_TASK_DEFINITION_ARN")"
}

attach_task_definition_to_inactive_service() {
  local current_td

  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$INACTIVE_SERVICE" \
    --task-definition "$NEW_TASK_DEFINITION_ARN" \
    --desired-count 0 \
    "${AWS_ARGS[@]}" >/dev/null

  for _ in {1..30}; do
    current_td="$(aws ecs describe-services \
      --cluster "$ECS_CLUSTER" \
      --services "$INACTIVE_SERVICE" \
      --query 'services[0].taskDefinition' \
      --output text \
      "${AWS_ARGS[@]}")"

    if [ "$current_td" = "$NEW_TASK_DEFINITION_ARN" ]; then
      break
    fi

    log "Waiting for ECS service to attach the new task definition..."
    sleep 2
  done

  if [ "$current_td" != "$NEW_TASK_DEFINITION_ARN" ]; then
    die "ECS service did not attach the new task definition: $INACTIVE_SERVICE"
  fi

  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$INACTIVE_SERVICE" \
    "${AWS_ARGS[@]}"

  wait_for_no_running_tasks "$INACTIVE_SERVICE"
}

wait_for_target_group_healthy() {
  local target_group_arn="$1"
  local color="$2"
  local start
  local now
  local elapsed
  local healthy_count="0"
  local last_health="[]"

  start="$(date +%s)"
  log "Waiting for ALB target health before traffic switch: color=$color target_group=$(redact_text "$target_group_arn")"

  while true; do
    if ! healthy_count="$(aws elbv2 describe-target-health \
      --target-group-arn "$target_group_arn" \
      --query "length(TargetHealthDescriptions[?TargetHealth.State==\`healthy\`])" \
      --output text \
      "${AWS_ARGS[@]}" 2>&1)"; then
      die "Failed to describe target health for color=$color target_group=$(redact_text "$target_group_arn"): $(redact_text "$healthy_count")"
    fi

    if ! last_health="$(aws elbv2 describe-target-health \
      --target-group-arn "$target_group_arn" \
      --query 'TargetHealthDescriptions[].{Id:Target.Id,Port:Target.Port,State:TargetHealth.State,Reason:TargetHealth.Reason}' \
      --output json \
      "${AWS_ARGS[@]}" 2>&1)"; then
      die "Failed to read target health diagnostics for color=$color target_group=$(redact_text "$target_group_arn"): $(redact_text "$last_health")"
    fi

    if [[ "$healthy_count" =~ ^[0-9]+$ ]] && [ "$healthy_count" -ge "$DESIRED_COUNT" ]; then
      log "ALB target group has $healthy_count healthy target(s) for color=$color."
      return 0
    fi

    now="$(date +%s)"
    elapsed=$((now - start))
    if [ "$elapsed" -ge "$TARGET_HEALTH_MAX_WAIT_SECONDS" ]; then
      printf '%s\n' "$last_health" >&2
      die "Expected at least $DESIRED_COUNT healthy ALB target(s) for color=$color after ${TARGET_HEALTH_MAX_WAIT_SECONDS}s."
    fi

    sleep "$TARGET_HEALTH_POLL_INTERVAL_SECONDS"
  done
}

promote_inactive_color() {
  log "Scaling $INACTIVE_COLOR to desired-count=$DESIRED_COUNT"
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$INACTIVE_SERVICE" \
    --desired-count "$DESIRED_COUNT" \
    "${AWS_ARGS[@]}" >/dev/null

  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$INACTIVE_SERVICE" \
    "${AWS_ARGS[@]}"

  wait_for_target_group_healthy "$INACTIVE_TG" "$INACTIVE_COLOR"

  log "Switching ALB production traffic to $INACTIVE_COLOR"
  aws elbv2 modify-listener \
    --listener-arn "$ALB_LISTENER_ARN" \
    --default-actions "Type=forward,TargetGroupArn=$INACTIVE_TG" \
    "${AWS_ARGS[@]}" >/dev/null

  aws elbv2 modify-rule \
    --rule-arn "$ALB_CANDIDATE_RULE_ARN" \
    --actions "Type=forward,TargetGroupArn=$ACTIVE_TG" \
    "${AWS_ARGS[@]}" >/dev/null
}

schedule_old_color_scale_down() {
  local targets
  local schedule_unit="minutes"

  if [ "$DRAIN_DELAY_MINUTES" = "1" ]; then
    schedule_unit="minute"
  fi

  log "Scheduling scale-down for old active service after ${DRAIN_DELAY_MINUTES} minute(s): $ACTIVE_SERVICE"
  aws events put-rule \
    --name "$SCALE_DOWN_RULE_NAME" \
    --schedule-expression "rate(${DRAIN_DELAY_MINUTES} ${schedule_unit})" \
    "${AWS_ARGS[@]}" >/dev/null

  targets="$(jq -n \
    --arg arn "$SCALE_DOWN_LAMBDA_ARN" \
    --arg svc "$ACTIVE_SERVICE" \
    '[{Id:"scale-down", Arn:$arn, Input:( "{\"serviceName\":\"" + $svc + "\"}" )}]')"

  aws events put-targets \
    --rule "$SCALE_DOWN_RULE_NAME" \
    --targets "$targets" \
    "${AWS_ARGS[@]}" >/dev/null
}

write_outputs() {
  if [ -z "$OUTPUT_ENV_FILE" ]; then
    return 0
  fi

  {
    echo "ACTIVE_COLOR=$INACTIVE_COLOR"
    echo "ACTIVE_SERVICE=$INACTIVE_SERVICE"
    echo "ACTIVE_TG_ARN=$INACTIVE_TG"
    echo "INACTIVE_COLOR=$ACTIVE_COLOR"
    echo "INACTIVE_SERVICE=$ACTIVE_SERVICE"
    echo "TASK_DEFINITION_ARN=$NEW_TASK_DEFINITION_ARN"
  } >> "$OUTPUT_ENV_FILE"
}

main() {
  parse_args "$@"
  require_command aws
  require_command jq
  set_aws_args
  resolve_account_id
  validate_args
  preflight_resources
  detect_blue_green_state
  resolve_db_secret_id
  stop_inactive_service
  register_rendered_task_definition
  attach_task_definition_to_inactive_service
  promote_inactive_color
  schedule_old_color_scale_down
  write_outputs
  log "Blue/green deployment completed. New active color: $INACTIVE_COLOR"
}

main "$@"
