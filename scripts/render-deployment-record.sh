#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_NAME="${APP_NAME:-demo-api}"
ENVIRONMENT="${TG_ENV:-}"
RELEASE_MANIFEST_URI="${RELEASE_MANIFEST_URI:-}"
GIT_SHA="${RELEASE_GIT_SHA:-}"
IMAGE_DIGEST="${IMAGE_DIGEST:-}"
IMAGE_URI="${IMAGE_URI:-}"
GITHUB_RUN_ID_VALUE="${GITHUB_RUN_ID:-}"
PREVIOUS_COLOR="${INACTIVE_COLOR:-}"
NEW_COLOR="${ACTIVE_COLOR:-}"
ACTIVE_SERVICE_NAME="${ACTIVE_SERVICE:-}"
INACTIVE_SERVICE_NAME="${INACTIVE_SERVICE:-}"
TASK_DEFINITION_ARN="${TASK_DEFINITION_ARN:-}"
LISTENER_ARN="${ALB_LISTENER_ARN:-}"
TARGET_GROUP_ARN="${ACTIVE_TG_ARN:-}"
STATUS="success"
ROLLBACK_IS_ROLLBACK="false"
ROLLBACK_REASON=""
ROLLBACK_SELECTOR_TYPE=""
ROLLBACK_SELECTED_MANIFEST_URI=""
ROLLBACK_PREVIOUS_CURRENT_MANIFEST_URI=""
ROLLBACK_REQUESTED_BY=""
OUTPUT_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/render-deployment-record.sh --environment dev|prod \
    --release-manifest-uri s3://bucket/key --git-sha SHA \
    --image-digest sha256:<64 lowercase hex> --image-uri REPO@sha256:... \
    --github-run-id ID --previous-color blue|green|null --new-color blue|green \
    --active-service NAME --inactive-service NAME --task-definition-arn ARN \
    --listener-arn ARN --target-group-arn ARN --output FILE

Environment variables with matching deployment output names are also accepted.
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
      --app)
        APP_NAME="${2:-}"
        shift 2
        ;;
      --environment)
        ENVIRONMENT="${2:-}"
        shift 2
        ;;
      --release-manifest-uri)
        RELEASE_MANIFEST_URI="${2:-}"
        shift 2
        ;;
      --git-sha)
        GIT_SHA="${2:-}"
        shift 2
        ;;
      --image-digest)
        IMAGE_DIGEST="${2:-}"
        shift 2
        ;;
      --image-uri)
        IMAGE_URI="${2:-}"
        shift 2
        ;;
      --github-run-id)
        GITHUB_RUN_ID_VALUE="${2:-}"
        shift 2
        ;;
      --previous-color)
        PREVIOUS_COLOR="${2:-}"
        shift 2
        ;;
      --new-color)
        NEW_COLOR="${2:-}"
        shift 2
        ;;
      --active-service)
        ACTIVE_SERVICE_NAME="${2:-}"
        shift 2
        ;;
      --inactive-service)
        INACTIVE_SERVICE_NAME="${2:-}"
        shift 2
        ;;
      --task-definition-arn)
        TASK_DEFINITION_ARN="${2:-}"
        shift 2
        ;;
      --listener-arn)
        LISTENER_ARN="${2:-}"
        shift 2
        ;;
      --target-group-arn)
        TARGET_GROUP_ARN="${2:-}"
        shift 2
        ;;
      --status)
        STATUS="${2:-}"
        shift 2
        ;;
      --rollback-is-rollback)
        ROLLBACK_IS_ROLLBACK="${2:-}"
        shift 2
        ;;
      --rollback-reason)
        ROLLBACK_REASON="${2:-}"
        shift 2
        ;;
      --rollback-selector-type)
        ROLLBACK_SELECTOR_TYPE="${2:-}"
        shift 2
        ;;
      --rollback-selected-manifest-uri)
        ROLLBACK_SELECTED_MANIFEST_URI="${2:-}"
        shift 2
        ;;
      --rollback-previous-current-manifest-uri)
        ROLLBACK_PREVIOUS_CURRENT_MANIFEST_URI="${2:-}"
        shift 2
        ;;
      --rollback-requested-by)
        ROLLBACK_REQUESTED_BY="${2:-}"
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
  [ "$APP_NAME" = "demo-api" ] || die "--app must be demo-api."

  case "$ENVIRONMENT" in
    dev|prod) ;;
    *) die "--environment must be dev or prod." ;;
  esac

  [[ "$RELEASE_MANIFEST_URI" =~ ^s3://[^/]+/.+ ]] || die "--release-manifest-uri must be an s3:// URI."
  [[ "$GIT_SHA" =~ ^[A-Fa-f0-9]{7,40}$ ]] || die "--git-sha must be a 7 to 40 character git SHA."
  [[ "$GITHUB_RUN_ID_VALUE" =~ ^[0-9]+$ ]] || die "--github-run-id must be numeric."

  case "$PREVIOUS_COLOR" in
    blue|green|null|"") ;;
    *) die "--previous-color must be blue, green, null, or empty." ;;
  esac

  case "$NEW_COLOR" in
    blue|green) ;;
    *) die "--new-color must be blue or green." ;;
  esac

  [ -n "$ACTIVE_SERVICE_NAME" ] || die "--active-service is required."
  [ -n "$INACTIVE_SERVICE_NAME" ] || die "--inactive-service is required."
  [ -n "$TASK_DEFINITION_ARN" ] || die "--task-definition-arn is required."
  [ -n "$LISTENER_ARN" ] || die "--listener-arn is required."
  [ -n "$TARGET_GROUP_ARN" ] || die "--target-group-arn is required."

  case "$STATUS" in
    success|failed) ;;
    *) die "--status must be success or failed." ;;
  esac

  case "$ROLLBACK_IS_ROLLBACK" in
    true|false) ;;
    *) die "--rollback-is-rollback must be true or false." ;;
  esac

  if [ "$ROLLBACK_IS_ROLLBACK" = "true" ]; then
    case "$ROLLBACK_SELECTOR_TYPE" in
      manifest_uri|git_sha_run_id|digest|previous_environment_history) ;;
      *) die "--rollback-selector-type must be manifest_uri, git_sha_run_id, digest, or previous_environment_history." ;;
    esac

    [[ "$ROLLBACK_SELECTED_MANIFEST_URI" =~ ^s3://[^/]+/.+ ]] || die "--rollback-selected-manifest-uri must be an s3:// URI."
    [[ "$ROLLBACK_PREVIOUS_CURRENT_MANIFEST_URI" =~ ^s3://[^/]+/.+ ]] || die "--rollback-previous-current-manifest-uri must be an s3:// URI."
    [ -n "$ROLLBACK_REQUESTED_BY" ] || die "--rollback-requested-by is required for rollback records."
  fi

  [ -n "$OUTPUT_FILE" ] || die "--output is required."

  "$ROOT_DIR/scripts/validate-image-digest.sh" \
    --digest "$IMAGE_DIGEST" \
    --image-uri "$IMAGE_URI"
}

render_record() {
  local deployed_at
  local output_dir

  deployed_at="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  output_dir="$(dirname "$OUTPUT_FILE")"
  mkdir -p "$output_dir"

  jq -n \
    --arg schema_version "1.0" \
    --arg app "$APP_NAME" \
    --arg environment "$ENVIRONMENT" \
    --arg release_manifest_uri "$RELEASE_MANIFEST_URI" \
    --arg git_sha "$GIT_SHA" \
    --arg image_digest "$IMAGE_DIGEST" \
    --arg image_uri "$IMAGE_URI" \
    --arg deployed_at "$deployed_at" \
    --arg github_run_id "$GITHUB_RUN_ID_VALUE" \
    --arg previous_color "$PREVIOUS_COLOR" \
    --arg new_color "$NEW_COLOR" \
    --arg active_service "$ACTIVE_SERVICE_NAME" \
    --arg inactive_service "$INACTIVE_SERVICE_NAME" \
    --arg task_definition_arn "$TASK_DEFINITION_ARN" \
    --arg listener_arn "$LISTENER_ARN" \
    --arg target_group_arn "$TARGET_GROUP_ARN" \
    --arg status "$STATUS" \
    --arg rollback_is_rollback "$ROLLBACK_IS_ROLLBACK" \
    --arg rollback_reason "$ROLLBACK_REASON" \
    --arg rollback_selector_type "$ROLLBACK_SELECTOR_TYPE" \
    --arg rollback_selected_manifest_uri "$ROLLBACK_SELECTED_MANIFEST_URI" \
    --arg rollback_previous_current_manifest_uri "$ROLLBACK_PREVIOUS_CURRENT_MANIFEST_URI" \
    --arg rollback_requested_by "$ROLLBACK_REQUESTED_BY" \
    '{
      schemaVersion: $schema_version,
      app: $app,
      environment: $environment,
      releaseManifestUri: $release_manifest_uri,
      gitSha: $git_sha,
      imageDigest: $image_digest,
      imageUri: $image_uri,
      deployedAt: $deployed_at,
      githubRunId: $github_run_id,
      deployment: {
        strategy: "blue-green",
        previousColor: (if $previous_color == "" or $previous_color == "null" then null else $previous_color end),
        newColor: $new_color,
        activeService: $active_service,
        inactiveService: $inactive_service,
        taskDefinitionArn: $task_definition_arn,
        listenerArn: $listener_arn,
        targetGroupArn: $target_group_arn
      },
      status: $status
    }
    + (
      if $rollback_is_rollback == "true" then
        {
          rollback: {
            isRollback: true,
            reason: $rollback_reason,
            selectorType: $rollback_selector_type,
            selectedManifestUri: $rollback_selected_manifest_uri,
            previousCurrentManifestUri: $rollback_previous_current_manifest_uri,
            requestedBy: $rollback_requested_by
          }
        }
      else
        {}
      end
    )' > "$OUTPUT_FILE"

  "$ROOT_DIR/scripts/validate-deployment-record.sh" "$OUTPUT_FILE"
}

main() {
  parse_args "$@"
  require_command jq
  validate_args
  render_record
}

main "$@"
