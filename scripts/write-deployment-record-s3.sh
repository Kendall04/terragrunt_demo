#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DEPLOYMENT_RECORD=""
BUCKET=""
ENVIRONMENT=""
GIT_SHA=""
RUN_ID=""
OUTPUT_FILE=""
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  scripts/write-deployment-record-s3.sh --deployment-record FILE --bucket BUCKET \
    --environment dev|prod --git-sha SHA --run-id ID [--output FILE] [--dry-run]

Writes deployment records to:
  deployments/<env>/<run-id>.json
  environments/<env>/history/<timestamp>-<git-sha>.json
  environments/<env>/current.json

current.json is the full deployment record so readers can validate it without
following a second pointer document.
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

log() {
  printf '[INFO] %s\n' "$*" >&2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --deployment-record)
        DEPLOYMENT_RECORD="${2:-}"
        shift 2
        ;;
      --bucket)
        BUCKET="${2:-}"
        shift 2
        ;;
      --environment)
        ENVIRONMENT="${2:-}"
        shift 2
        ;;
      --git-sha)
        GIT_SHA="${2:-}"
        shift 2
        ;;
      --run-id)
        RUN_ID="${2:-}"
        shift 2
        ;;
      --output)
        OUTPUT_FILE="${2:-}"
        shift 2
        ;;
      --dry-run)
        DRY_RUN="true"
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

validate_args() {
  case "$ENVIRONMENT" in
    dev|prod) ;;
    *) die "--environment must be dev or prod." ;;
  esac

  [ -n "$DEPLOYMENT_RECORD" ] || die "--deployment-record is required."
  [ -f "$DEPLOYMENT_RECORD" ] || die "Deployment record file not found: $DEPLOYMENT_RECORD"
  [ -n "$BUCKET" ] || die "--bucket is required."
  [[ "$GIT_SHA" =~ ^[A-Fa-f0-9]{7,40}$ ]] || die "--git-sha must be a 7 to 40 character git SHA."
  [[ "$RUN_ID" =~ ^[0-9]+$ ]] || die "--run-id must be numeric."

  "$ROOT_DIR/scripts/validate-deployment-record.sh" "$DEPLOYMENT_RECORD"

  [ "$(jq -er '.environment' "$DEPLOYMENT_RECORD")" = "$ENVIRONMENT" ] || die "Deployment record environment does not match --environment."
  [ "$(jq -er '.gitSha' "$DEPLOYMENT_RECORD")" = "$GIT_SHA" ] || die "Deployment record gitSha does not match --git-sha."
  [ "$(jq -er '.githubRunId' "$DEPLOYMENT_RECORD")" = "$RUN_ID" ] || die "Deployment record githubRunId does not match --run-id."
}

require_bucket() {
  if [ "$DRY_RUN" = "true" ]; then
    return 0
  fi

  if ! aws s3api get-bucket-location --bucket "$BUCKET" >/dev/null 2>&1; then
    die "Release artifacts bucket '$BUCKET' was not found or is not accessible."
  fi
}

put_record() {
  local key="$1"

  if [ "$DRY_RUN" = "true" ]; then
    log "Dry run: would write s3://${BUCKET}/${key}"
    return 0
  fi

  aws s3 cp "$DEPLOYMENT_RECORD" "s3://${BUCKET}/${key}" \
    --content-type "application/json" \
    --no-progress >/dev/null
}

write_output_json() {
  local deployment_uri="$1"
  local history_uri="$2"
  local current_uri="$3"
  local json

  if [ -n "$OUTPUT_FILE" ]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
  fi

  json="$(jq -n \
    --arg bucket "$BUCKET" \
    --arg environment "$ENVIRONMENT" \
    --arg deployment_uri "$deployment_uri" \
    --arg history_uri "$history_uri" \
    --arg current_uri "$current_uri" \
    '{
      bucket: $bucket,
      environment: $environment,
      deploymentRecordUri: $deployment_uri,
      historyUri: $history_uri,
      currentUri: $current_uri
    }')"

  if [ -n "$OUTPUT_FILE" ]; then
    printf '%s\n' "$json" > "$OUTPUT_FILE"
  else
    printf '%s\n' "$json"
  fi
}

write_records() {
  local timestamp
  local deployment_key
  local history_key
  local current_key

  timestamp="$(date -u '+%Y-%m-%dT%H%M%SZ')"
  deployment_key="deployments/${ENVIRONMENT}/${RUN_ID}.json"
  history_key="environments/${ENVIRONMENT}/history/${timestamp}-${GIT_SHA}.json"
  current_key="environments/${ENVIRONMENT}/current.json"

  put_record "$deployment_key"
  put_record "$history_key"
  put_record "$current_key"

  write_output_json \
    "s3://${BUCKET}/${deployment_key}" \
    "s3://${BUCKET}/${history_key}" \
    "s3://${BUCKET}/${current_key}"
}

main() {
  parse_args "$@"
  require_command jq
  if [ "$DRY_RUN" != "true" ]; then
    require_command aws
  fi
  validate_args
  require_bucket
  write_records
}

main "$@"
