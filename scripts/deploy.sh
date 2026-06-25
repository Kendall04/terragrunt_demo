#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

COMMAND="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

ENV_NAME="dev"
AWS_REGION_NAME="us-east-1"
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
IMAGE_TAG=""
IMAGE_TAG_PROVIDED="false"
SKIP_BUILD="false"
IMAGE_DIGEST=""
INCLUDE_EDGE="false"
SMOKE_TEST="false"
DRY_RUN="false"
YES="false"
CONFIRM_PROD="false"
ACTIVE_COLOR="blue"
TARGET_HEALTH_MAX_WAIT_SECONDS=300
TARGET_HEALTH_POLL_INTERVAL_SECONDS=10

AWS_ARGS=()
ACCOUNT_ID=""
STATE_BUCKET=""
LOCK_TABLE=""
ECR_REPOSITORY=""
REGISTRY=""
IMAGE_URI=""
IMAGE_DIGEST_URI=""

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy.sh full-dev-deploy [options]
  scripts/deploy.sh deploy-app [options]

Commands:
  full-dev-deploy      Run full-dev-bootstrap first, then deploy-app.
                        Recommended complete dev flow for base drift
                        reconciliation plus app/edge deployment.
  deploy-app            Build/push the demo API image, resolve its ECR digest,
                        apply the apps/fargate skeleton, and run ECS blue/green.
                        Fast path; assumes base infrastructure is reconciled.

Options:
  --env ENV             Environment name: dev or prod. Default: dev
  --region REGION       AWS region. Default: us-east-1
  --profile PROFILE     AWS CLI profile to use for local named-profile deploys
  --use-instance-role   Use the EC2 instance role/default AWS credential chain
                        and do not pass an AWS CLI profile
  --tag TAG             Image tag. Default: <git-short-sha>-<YYYYMMDDHHMMSS>
  --skip-build          Do not build/push. Requires --image-digest or --tag.
  --image-digest DIGEST Use an existing ECR image digest, e.g. sha256:abc...
  --include-edge        Apply edge/API Gateway after apps/fargate succeeds
  --smoke-test          Read edge api_endpoint and curl /ready
  --active-color COLOR  Fallback active ECS/ALB color for readiness waits.
                        Default: blue. Supported: blue, green
  --dry-run             Print the actions without building, pushing, or applying
  --yes                 Pass --yes to bootstrap apply commands
  --confirm-prod        Required when --env prod
  -h, --help            Show this help

Examples:
  scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes
  scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --profile terraform-lab --include-edge --smoke-test --yes
  scripts/deploy.sh deploy-app --env dev --region us-east-1
  scripts/deploy.sh deploy-app --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test
  scripts/deploy.sh deploy-app --env dev --profile my-aws-profile --region us-east-1
  scripts/deploy.sh deploy-app --env dev --region us-east-1 --skip-build --tag abc123-20260101120000
  scripts/deploy.sh deploy-app --env dev --region us-east-1 --image-digest sha256:...

Use full-dev-deploy for the complete flow. Run deploy-app directly only when
shared/ECR, secrets, global, data, and platform have already been reconciled.
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
    -e 's#[0-9]{12}\.dkr\.ecr\.([A-Za-z0-9-]+)\.amazonaws\.com#<aws-account-id>.dkr.ecr.\1.amazonaws.com#g' \
    -e 's#tfstate-demo-[A-Za-z0-9._-]+-[0-9]{12}#tfstate-demo-<env>-<aws-account-id>#g' \
    -e 's#tfstate-locks-[0-9]{12}#tfstate-locks-<aws-account-id>#g'
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
      --tag)
        IMAGE_TAG="${2:-}"
        IMAGE_TAG_PROVIDED="true"
        shift 2
        ;;
      --skip-build)
        SKIP_BUILD="true"
        shift
        ;;
      --image-digest)
        IMAGE_DIGEST="${2:-}"
        SKIP_BUILD="true"
        shift 2
        ;;
      --include-edge)
        INCLUDE_EDGE="true"
        shift
        ;;
      --smoke-test)
        SMOKE_TEST="true"
        shift
        ;;
      --active-color)
        ACTIVE_COLOR="${2:-}"
        shift 2
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

resolve_identity_and_backend() {
  set_aws_args

  if [ "$DRY_RUN" = "true" ]; then
    if command -v aws >/dev/null 2>&1; then
      ACCOUNT_ID="$(aws sts get-caller-identity \
        --query Account \
        --output text \
        "${AWS_ARGS[@]}" 2>/dev/null || true)"
    fi

    if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
      ACCOUNT_ID="<aws-account-id>"
    fi
  else
    require_command aws
    ACCOUNT_ID="$(aws sts get-caller-identity \
      --query Account \
      --output text \
      "${AWS_ARGS[@]}")"

    if [ -z "$ACCOUNT_ID" ] || [ "$ACCOUNT_ID" = "None" ]; then
      die "Could not resolve AWS account ID."
    fi
  fi

  STATE_BUCKET="tfstate-demo-${ENV_NAME}-${ACCOUNT_ID}"
  LOCK_TABLE="tfstate-locks-${ACCOUNT_ID}"

  export TG_ENV="$ENV_NAME"
  export AWS_REGION="$AWS_REGION_NAME"
  export TF_STATE_BUCKET="$STATE_BUCKET"
  export TF_STATE_TABLE="$LOCK_TABLE"
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    export AWS_PROFILE="$AWS_PROFILE_NAME"
  else
    unset AWS_PROFILE
  fi
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

validate_layout() {
  [ -f "$ROOT_DIR/scripts/bootstrap.sh" ] || die "Missing scripts/bootstrap.sh."
  [ -f "$ROOT_DIR/scripts/ecs-blue-green-deploy.sh" ] || die "Missing scripts/ecs-blue-green-deploy.sh."
  [ -f "$ROOT_DIR/scripts/render-demo-api-taskdef.sh" ] || die "Missing scripts/render-demo-api-taskdef.sh."
  [ -f "$ROOT_DIR/demo-api/deploy/task-definition.template.json" ] || die "Missing demo-api/deploy/task-definition.template.json."
  [ -f "$ROOT_DIR/demo-api/Dockerfile" ] || die "Missing demo-api/Dockerfile."
  [ -f "$ROOT_DIR/demo-api/terragrunt-demo/terragrunt-demo.csproj" ] || die "Missing demo-api/terragrunt-demo/terragrunt-demo.csproj."
  [ -d "$ROOT_DIR/terraform/live/$ENV_NAME/apps/fargate" ] || die "Missing terraform/live/$ENV_NAME/apps/fargate."
  [ -d "$ROOT_DIR/terraform/live/$ENV_NAME/edge" ] || die "Missing terraform/live/$ENV_NAME/edge."
}

generate_default_tag() {
  local short_sha
  local timestamp

  timestamp="$(date -u +%Y%m%d%H%M%S)"
  if command -v git >/dev/null 2>&1 && short_sha="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD 2>/dev/null)"; then
    printf '%s-%s\n' "$short_sha" "$timestamp"
  else
    printf 'local-%s\n' "$timestamp"
  fi
}

validate_tag() {
  if [ -z "$IMAGE_TAG" ]; then
    IMAGE_TAG="$(generate_default_tag)"
  fi

  if ! [[ "$IMAGE_TAG" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    die "Invalid image tag '$IMAGE_TAG'. Use only letters, numbers, underscores, periods, and dashes."
  fi
}

validate_skip_build() {
  if [ "$SKIP_BUILD" = "true" ] && [ -z "$IMAGE_DIGEST" ] && [ "$IMAGE_TAG_PROVIDED" != "true" ]; then
    die "--skip-build requires --image-digest or an explicit --tag for an existing ECR image."
  fi
}

validate_active_color() {
  case "$ACTIVE_COLOR" in
    blue|green) ;;
    *) die "Unsupported --active-color '$ACTIVE_COLOR'. Supported values: blue, green." ;;
  esac
}

validate_digest() {
  local digest="$1"

  if [ -z "$digest" ] || [ "$digest" = "None" ] || [ "$digest" = "null" ]; then
    die "Image digest is empty. Expected a value like sha256:..."
  fi

  if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
    die "Invalid image digest '$digest'. Expected sha256:<64 lowercase hex chars>."
  fi
}

set_image_names() {
  ECR_REPOSITORY="demo-${ENV_NAME}-shared-demo-ms"
  REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION_NAME}.amazonaws.com"
  IMAGE_URI="${REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"
}

set_image_digest_uri() {
  validate_digest "$IMAGE_DIGEST"
  IMAGE_DIGEST_URI="${REGISTRY}/${ECR_REPOSITORY}@${IMAGE_DIGEST}"
}

default_cluster_name() {
  printf 'demo-%s-platform-main-cluster\n' "$ENV_NAME"
}

default_active_service_name() {
  printf 'demo-%s-app-api-%s-svc\n' "$ENV_NAME" "$ACTIVE_COLOR"
}

default_active_target_group_name() {
  printf 'demo-%s-%s-tg\n' "$ENV_NAME" "$ACTIVE_COLOR"
}

print_target() {
  log "Local app deploy target"
  printf '  env             : %s\n' "$ENV_NAME"
  printf '  region          : %s\n' "$AWS_REGION_NAME"
  if [ "$USE_INSTANCE_ROLE" = "true" ]; then
    printf '  profile mode    : instance-role/default-chain\n'
  elif [ -n "$AWS_PROFILE_NAME" ]; then
    printf '  profile         : %s\n' "$AWS_PROFILE_NAME"
  else
    printf '  profile mode    : default-chain\n'
  fi
  printf '  AWS account ID  : %s\n' "$(redact_text "$ACCOUNT_ID")"
  printf '  state bucket    : %s\n' "$(redact_text "$STATE_BUCKET")"
  printf '  lock table      : %s\n' "$(redact_text "$LOCK_TABLE")"
  printf '  ECR repository  : %s\n' "$ECR_REPOSITORY"
  printf '  image tag       : %s\n' "$IMAGE_TAG"
  printf '  image URI       : %s\n' "$(redact_text "$IMAGE_URI")"
  if [ -n "$IMAGE_DIGEST" ]; then
    printf '  image digest    : %s\n' "$IMAGE_DIGEST"
  fi
  if [ -n "$IMAGE_DIGEST_URI" ]; then
    printf '  immutable URI   : %s\n' "$(redact_text "$IMAGE_DIGEST_URI")"
  fi
  printf '  active color    : %s\n' "$ACTIVE_COLOR"
}

append_bootstrap_common_args() {
  local -n args_ref="$1"

  args_ref+=(--env "$ENV_NAME" --region "$AWS_REGION_NAME")
  if [ "$USE_INSTANCE_ROLE" = "true" ] || [ -z "$AWS_PROFILE_NAME" ]; then
    args_ref+=(--use-instance-role)
  else
    args_ref+=(--profile "$AWS_PROFILE_NAME")
  fi
  if [ "$YES" = "true" ]; then
    args_ref+=(--yes)
  fi
  if [ "$CONFIRM_PROD" = "true" ]; then
    args_ref+=(--confirm-prod)
  fi
}

dry_run_plan() {
  local bootstrap_args
  local edge_args
  local immutable_uri="${REGISTRY}/${ECR_REPOSITORY}@${IMAGE_DIGEST:-<resolved-image-digest>}"

  print_target
  log "Dry run only. No Docker, ECR login, ECR push, Terragrunt apply, ECS deploy, edge apply, or smoke test will run."
  printf '[DRY-RUN] %s\n' "$(quote_cmd aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" "${AWS_ARGS[@]}")"

  if [ -n "$IMAGE_DIGEST" ]; then
    printf '[DRY-RUN] use provided image digest: %s\n' "$IMAGE_DIGEST"
  elif [ "$SKIP_BUILD" = "true" ]; then
    printf '[DRY-RUN] %s\n' "$(quote_cmd aws ecr describe-images --repository-name "$ECR_REPOSITORY" --image-ids "imageTag=$IMAGE_TAG" --query "imageDetails[0].imageDigest" --output text "${AWS_ARGS[@]}")"
  else
    printf '[DRY-RUN] %s | %s\n' \
      "$(quote_cmd aws ecr get-login-password "${AWS_ARGS[@]}")" \
      "$(quote_cmd docker login --username AWS --password-stdin "$REGISTRY")"
    printf '[DRY-RUN] %s\n' "$(quote_cmd docker build -f demo-api/Dockerfile -t "demo-api:${IMAGE_TAG}" demo-api)"
    printf '[DRY-RUN] %s\n' "$(quote_cmd docker tag "demo-api:${IMAGE_TAG}" "$IMAGE_URI")"
    printf '[DRY-RUN] %s\n' "$(quote_cmd docker push "$IMAGE_URI")"
    printf '[DRY-RUN] %s\n' "$(quote_cmd aws ecr describe-images --repository-name "$ECR_REPOSITORY" --image-ids "imageTag=$IMAGE_TAG" --query "imageDetails[0].imageDigest" --output text "${AWS_ARGS[@]}")"
  fi

  bootstrap_args=("$ROOT_DIR/scripts/bootstrap.sh" apply-apps)
  append_bootstrap_common_args bootstrap_args
  printf '[DRY-RUN] %s\n' "$(quote_cmd "${bootstrap_args[@]}")"
  printf '[DRY-RUN] resolve Terragrunt outputs for platform/global/apps deploy resources\n'
  printf '[DRY-RUN] %s\n' "$(quote_cmd "$ROOT_DIR/scripts/ecs-blue-green-deploy.sh" --env "$ENV_NAME" --region "$AWS_REGION_NAME" --account-id "$ACCOUNT_ID" --image-uri "$immutable_uri" --cluster "$(default_cluster_name)" --blue-service "demo-${ENV_NAME}-app-api-blue-svc" --green-service "demo-${ENV_NAME}-app-api-green-svc" --listener-arn "<alb-listener-arn>" --candidate-rule-arn "<alb-candidate-rule-arn>" --tg-blue-arn "<blue-target-group-arn>" --tg-green-arn "<green-target-group-arn>" --scale-down-rule-name "demo-${ENV_NAME}-scale-down-old-color-rule" --scale-down-lambda-arn "<scale-down-lambda-arn>")"

  if [ "$INCLUDE_EDGE" = "true" ]; then
    edge_args=("$ROOT_DIR/scripts/bootstrap.sh" apply-edge)
    append_bootstrap_common_args edge_args
    printf '[DRY-RUN] %s\n' "$(quote_cmd "${edge_args[@]}")"
  fi

  if [ "$SMOKE_TEST" = "true" ]; then
    printf '[DRY-RUN] cd %q && %s\n' "$ROOT_DIR/terraform/live/$ENV_NAME/edge" "$(quote_cmd terragrunt output -raw api_endpoint)"
    printf '[DRY-RUN] wait for ECS service stable: cluster=%s service=%s\n' "$(default_cluster_name)" "$(default_active_service_name)"
    printf '[DRY-RUN] wait for ALB target healthy: target_group=%s active_color=%s max_wait_seconds=%s interval_seconds=%s\n' \
      "$(default_active_target_group_name)" \
      "$ACTIVE_COLOR" \
      "$TARGET_HEALTH_MAX_WAIT_SECONDS" \
      "$TARGET_HEALTH_POLL_INTERVAL_SECONDS"
    printf '[DRY-RUN] %s\n' "$(quote_cmd curl -fsS "<api_endpoint>/ready")"
  fi
}

dry_run_full_dev_deploy() {
  local bootstrap_args

  bootstrap_args=("$ROOT_DIR/scripts/bootstrap.sh" full-dev-bootstrap)
  append_bootstrap_common_args bootstrap_args

  log "Dry run only. Full dev deploy will reconcile base infrastructure before any image build, push, app apply, edge apply, or smoke test."
  printf '[DRY-RUN] %s\n' "$(quote_cmd "${bootstrap_args[@]}")"
  log "After full-dev-bootstrap succeeds, the app deployment phase would run:"
  dry_run_plan
}

verify_ecr_repository() {
  if ! aws ecr describe-repositories \
    --repository-names "$ECR_REPOSITORY" \
    "${AWS_ARGS[@]}" >/dev/null 2>&1; then
    die "ECR repository not found. Run scripts/bootstrap.sh full-dev-bootstrap first."
  fi
}

tag_exists_in_ecr() {
  aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --image-ids "imageTag=$IMAGE_TAG" \
    "${AWS_ARGS[@]}" >/dev/null 2>&1
}

ensure_tag_is_available() {
  if [ "$SKIP_BUILD" = "true" ]; then
    return 0
  fi

  if tag_exists_in_ecr; then
    die "ECR image tag already exists: $IMAGE_TAG. ECR tags are immutable; choose a new --tag or use --skip-build --tag $IMAGE_TAG to reuse it."
  fi
}

docker_login() {
  log "Logging in to ECR registry: $(redact_text "$REGISTRY")"
  aws ecr get-login-password "${AWS_ARGS[@]}" \
    | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
}

build_and_push_image() {
  require_command docker

  if ! docker info >/dev/null 2>&1; then
    die "Docker daemon is not available. Start Docker and rerun deploy."
  fi

  docker_login

  log "Building Docker image from demo-api/Dockerfile."
  docker build -f "$ROOT_DIR/demo-api/Dockerfile" -t "demo-api:${IMAGE_TAG}" "$ROOT_DIR/demo-api"

  log "Tagging image: $(redact_text "$IMAGE_URI")"
  docker tag "demo-api:${IMAGE_TAG}" "$IMAGE_URI"

  log "Pushing image to ECR."
  docker push "$IMAGE_URI"
}

resolve_digest_from_tag() {
  local digest

  digest="$(aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --image-ids "imageTag=$IMAGE_TAG" \
    --query 'imageDetails[0].imageDigest' \
    --output text \
    "${AWS_ARGS[@]}")"

  validate_digest "$digest"
  printf '%s\n' "$digest"
}

apply_apps() {
  local args=("$ROOT_DIR/scripts/bootstrap.sh" apply-apps)
  append_bootstrap_common_args args

  log "Applying apps/fargate ECS skeleton."
  "${args[@]}"
}

apply_edge() {
  local args=("$ROOT_DIR/scripts/bootstrap.sh" apply-edge)
  append_bootstrap_common_args args

  log "Applying edge/API Gateway."
  "${args[@]}"
}

required_terragrunt_output() {
  local dir="$1"
  local output_name="$2"
  local value

  value="$(terragrunt_output_raw_or_empty "$dir" "$output_name")"
  if [ -z "$value" ]; then
    die "Could not read Terragrunt output '$output_name' from $dir."
  fi

  printf '%s\n' "$value"
}

run_blue_green_deploy() {
  local global_dir="$ROOT_DIR/terraform/live/$ENV_NAME/global"
  local apps_dir="$ROOT_DIR/terraform/live/$ENV_NAME/apps/fargate"
  local secrets_dir="$ROOT_DIR/terraform/live/$ENV_NAME/secrets"
  local deploy_env_file
  local cluster_name
  local listener_arn
  local candidate_rule_arn
  local blue_tg_arn
  local green_tg_arn
  local scale_down_rule_name
  local scale_down_lambda_arn
  local db_secret_arn
  local promoted_color
  local args

  require_command terragrunt

  cluster_name="$(resolve_cluster_name)"
  listener_arn="$(required_terragrunt_output "$global_dir" alb_listener_arn)"
  candidate_rule_arn="$(required_terragrunt_output "$global_dir" alb_candidate_rule_arn)"
  blue_tg_arn="$(required_terragrunt_output "$global_dir" demo_blue_tg_arn)"
  green_tg_arn="$(required_terragrunt_output "$global_dir" demo_green_tg_arn)"
  scale_down_rule_name="$(required_terragrunt_output "$apps_dir" scale_down_rule_name)"
  scale_down_lambda_arn="$(required_terragrunt_output "$apps_dir" scale_down_lambda_arn)"
  db_secret_arn="$(required_terragrunt_output "$secrets_dir" db_secret_arn)"

  deploy_env_file="$(mktemp)"
  args=(
    "$ROOT_DIR/scripts/ecs-blue-green-deploy.sh"
    --env "$ENV_NAME"
    --region "$AWS_REGION_NAME"
    --account-id "$ACCOUNT_ID"
    --image-uri "$IMAGE_DIGEST_URI"
    --cluster "$cluster_name"
    --blue-service "demo-${ENV_NAME}-app-api-blue-svc"
    --green-service "demo-${ENV_NAME}-app-api-green-svc"
    --listener-arn "$listener_arn"
    --candidate-rule-arn "$candidate_rule_arn"
    --tg-blue-arn "$blue_tg_arn"
    --tg-green-arn "$green_tg_arn"
    --scale-down-rule-name "$scale_down_rule_name"
    --scale-down-lambda-arn "$scale_down_lambda_arn"
    --db-secret-id "$db_secret_arn"
    --desired-count "1"
    --drain-delay-minutes "5"
    --output-env "$deploy_env_file"
  )

  if [ "$USE_INSTANCE_ROLE" = "true" ] || [ -z "$AWS_PROFILE_NAME" ]; then
    args+=(--use-instance-role)
  else
    args+=(--profile "$AWS_PROFILE_NAME")
  fi

  log "Deploying immutable image through ECS blue/green."
  "${args[@]}"

  promoted_color="$(awk -F= '$1 == "ACTIVE_COLOR" { value=$2 } END { print value }' "$deploy_env_file")"
  rm -f "$deploy_env_file"

  if [ -n "$promoted_color" ]; then
    ACTIVE_COLOR="$promoted_color"
  fi
}

terragrunt_output_raw_or_empty() {
  local dir="$1"
  local output_name="$2"
  local value

  if value="$(cd "$dir" && terragrunt output -raw "$output_name" 2>/dev/null)"; then
    :
  else
    value=""
  fi
  if [ "$value" = "None" ] || [ "$value" = "null" ]; then
    value=""
  fi

  printf '%s\n' "$value"
}

resolve_cluster_name() {
  local platform_dir="$ROOT_DIR/terraform/live/$ENV_NAME/platform"
  local cluster_name

  cluster_name="$(terragrunt_output_raw_or_empty "$platform_dir" cluster_name)"
  if [ -z "$cluster_name" ]; then
    cluster_name="$(default_cluster_name)"
    warn "Could not read platform cluster_name output; using convention: $cluster_name"
  fi

  printf '%s\n' "$cluster_name"
}

resolve_active_target_group_arn() {
  local global_dir="$ROOT_DIR/terraform/live/$ENV_NAME/global"
  local output_name="demo_${ACTIVE_COLOR}_tg_arn"
  local target_group_name
  local target_group_arn

  target_group_arn="$(terragrunt_output_raw_or_empty "$global_dir" "$output_name")"
  if [ -n "$target_group_arn" ]; then
    printf '%s\n' "$target_group_arn"
    return 0
  fi

  target_group_name="$(default_active_target_group_name)"
  warn "Could not read global $output_name output; resolving target group by name: $target_group_name"
  if ! target_group_arn="$(aws elbv2 describe-target-groups \
    --names "$target_group_name" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text \
    "${AWS_ARGS[@]}" 2>&1)"; then
    die "Could not resolve target group ARN for active color '$ACTIVE_COLOR' using output '$output_name' or name '$target_group_name': $(redact_text "$target_group_arn")"
  fi

  if [ -z "$target_group_arn" ] || [ "$target_group_arn" = "None" ] || [ "$target_group_arn" = "null" ]; then
    die "Could not resolve target group ARN for active color '$ACTIVE_COLOR' using output '$output_name' or name '$target_group_name'."
  fi

  printf '%s\n' "$target_group_arn"
}

wait_for_ecs_service_stable() {
  local cluster_name="$1"
  local service_name="$2"

  log "Waiting for ECS service stable: cluster=$cluster_name service=$service_name"
  if ! aws ecs wait services-stable \
    --cluster "$cluster_name" \
    --services "$service_name" \
    "${AWS_ARGS[@]}"; then
    aws ecs describe-services \
      --cluster "$cluster_name" \
      --services "$service_name" \
      --query 'services[].{service:serviceName,desired:desiredCount,running:runningCount,pending:pendingCount,events:events[0:5].message}' \
      --output json \
      "${AWS_ARGS[@]}" >&2 || true
    die "ECS service did not become stable: cluster=$cluster_name service=$service_name"
  fi
}

wait_for_target_group_healthy() {
  local target_group_arn="$1"
  local target_group_name="$2"
  local start
  local now
  local elapsed
  local healthy_count="0"
  local last_health="[]"

  start="$(date +%s)"
  log "Waiting for ALB target healthy: target_group=$target_group_name target_group_arn=$(redact_text "$target_group_arn")"

  while true; do
    if ! healthy_count="$(aws elbv2 describe-target-health \
      --target-group-arn "$target_group_arn" \
      --query "length(TargetHealthDescriptions[?TargetHealth.State==\`healthy\`])" \
      --output text \
      "${AWS_ARGS[@]}" 2>&1)"; then
      die "Failed to describe target health for active_color=$ACTIVE_COLOR target_group=$target_group_name target_group_arn=$(redact_text "$target_group_arn"): $(redact_text "$healthy_count")"
    fi

    if ! last_health="$(aws elbv2 describe-target-health \
      --target-group-arn "$target_group_arn" \
      --query 'TargetHealthDescriptions[].{Id:Target.Id,Port:Target.Port,State:TargetHealth.State,Reason:TargetHealth.Reason}' \
      --output json \
      "${AWS_ARGS[@]}" 2>&1)"; then
      die "Failed to read target health diagnostics for active_color=$ACTIVE_COLOR target_group=$target_group_name target_group_arn=$(redact_text "$target_group_arn"): $(redact_text "$last_health")"
    fi

    if [[ "$healthy_count" =~ ^[0-9]+$ ]] && [ "$healthy_count" -gt 0 ]; then
      log "ALB target group has $healthy_count healthy target(s): $target_group_name"
      return 0
    fi

    now="$(date +%s)"
    elapsed=$((now - start))
    if [ "$elapsed" -ge "$TARGET_HEALTH_MAX_WAIT_SECONDS" ]; then
      printf '%s\n' "$last_health" >&2
      die "No healthy ALB targets after ${TARGET_HEALTH_MAX_WAIT_SECONDS}s: active_color=$ACTIVE_COLOR target_group=$target_group_name target_group_arn=$(redact_text "$target_group_arn")"
    fi

    sleep "$TARGET_HEALTH_POLL_INTERVAL_SECONDS"
  done
}

wait_for_smoke_readiness() {
  local cluster_name
  local service_name
  local target_group_name
  local target_group_arn

  require_command aws
  require_command terragrunt

  cluster_name="$(resolve_cluster_name)"
  service_name="$(default_active_service_name)"
  target_group_name="$(default_active_target_group_name)"
  target_group_arn="$(resolve_active_target_group_arn)"

  wait_for_ecs_service_stable "$cluster_name" "$service_name"
  wait_for_target_group_healthy "$target_group_arn" "$target_group_name"
}

run_smoke_test() {
  local edge_dir="$ROOT_DIR/terraform/live/$ENV_NAME/edge"
  local api_url

  require_command terragrunt
  require_command curl

  if api_url="$(cd "$edge_dir" && terragrunt output -raw api_endpoint 2>/dev/null)"; then
    :
  else
    api_url=""
  fi
  if [ -z "$api_url" ] || [ "$api_url" = "None" ] || [ "$api_url" = "null" ]; then
    die "Could not read edge api_endpoint. Apply edge first or rerun with --include-edge."
  fi

  api_url="${api_url%/}"
  wait_for_smoke_readiness
  log "Running smoke test: ${api_url}/ready"
  if ! curl -fsS "${api_url}/ready"; then
    die "Smoke test failed for ${api_url}/ready."
  fi
  printf '\n'
}

deploy_app() {
  parse_args "$@"
  validate_env_name
  require_prod_confirmation
  validate_layout
  validate_tag
  validate_skip_build
  validate_active_color
  if [ -n "$IMAGE_DIGEST" ]; then
    validate_digest "$IMAGE_DIGEST"
  fi
  resolve_identity_and_backend
  set_image_names

  if [ "$DRY_RUN" = "true" ]; then
    dry_run_plan
    return 0
  fi

  require_command aws
  verify_ecr_repository

  if [ -n "$IMAGE_DIGEST" ]; then
    validate_digest "$IMAGE_DIGEST"
    log "Using provided image digest; build and push are skipped."
  elif [ "$SKIP_BUILD" = "true" ]; then
    log "Skipping build/push and resolving digest for existing tag: $IMAGE_TAG"
    IMAGE_DIGEST="$(resolve_digest_from_tag)"
  else
    ensure_tag_is_available
    build_and_push_image
    IMAGE_DIGEST="$(resolve_digest_from_tag)"
  fi

  set_image_digest_uri
  print_target
  apply_apps
  run_blue_green_deploy

  if [ "$INCLUDE_EDGE" = "true" ]; then
    apply_edge
  else
    log "Edge/API Gateway was not applied. Pass --include-edge to apply it after apps/fargate."
  fi

  if [ "$SMOKE_TEST" = "true" ]; then
    run_smoke_test
  fi

  log "Local app deploy completed."
}

run_full_dev_bootstrap() {
  local bootstrap_args

  bootstrap_args=("$ROOT_DIR/scripts/bootstrap.sh" full-dev-bootstrap)
  append_bootstrap_common_args bootstrap_args
  log "Reconciling base infrastructure with full-dev-bootstrap before app deployment."
  "${bootstrap_args[@]}"
}

full_dev_deploy() {
  parse_args "$@"
  validate_env_name
  if [ "$ENV_NAME" != "dev" ]; then
    die "full-dev-deploy only supports --env dev because it runs full-dev-bootstrap."
  fi
  require_prod_confirmation
  validate_layout
  validate_tag
  validate_skip_build
  validate_active_color
  if [ -n "$IMAGE_DIGEST" ]; then
    validate_digest "$IMAGE_DIGEST"
  fi
  resolve_identity_and_backend
  set_image_names

  if [ "$DRY_RUN" = "true" ]; then
    dry_run_full_dev_deploy
    return 0
  fi

  if ! run_full_dev_bootstrap; then
    die "full-dev-bootstrap failed. Stopping before Docker build, ECR push, apps/fargate apply, ECS blue/green deploy, edge apply, or smoke test."
  fi

  log "Base infrastructure reconciliation completed. Continuing with app deployment."
  deploy_app "$@"
}

old_usage_message() {
  cat >&2 <<EOF
[ERROR] scripts/deploy.sh no longer runs base infrastructure bootstrap.

Use the complete dev deploy flow:
  scripts/deploy.sh full-dev-deploy --env dev --region us-east-1

Or use the staged bootstrap first:
  scripts/bootstrap.sh full-dev-bootstrap --env dev --region us-east-1
  scripts/deploy.sh deploy-app --env dev --region us-east-1

Base infrastructure is missing if ECR/ECS prerequisites are not found. Run scripts/bootstrap.sh full-dev-bootstrap first.
EOF
  exit 1
}

main() {
  case "$COMMAND" in
    help|-h|--help)
      usage
      ;;
    full-dev-deploy)
      full_dev_deploy "$@"
      ;;
    deploy-app)
      deploy_app "$@"
      ;;
    dev|prod)
      old_usage_message
      ;;
    *)
      usage >&2
      die "Unknown command: $COMMAND"
      ;;
  esac
}

main "$@"
