#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BUCKET=""
ENVIRONMENT=""
HISTORY_INDEX="1"
OUTPUT_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/list-deployment-history-s3.sh --bucket BUCKET --environment dev|prod \
    [--history-index N] [--output FILE]

Reads environments/<env>/current.json and environments/<env>/history/ from S3,
then selects the Nth previous deployment record before current. N=1 means the
deployment immediately before current. This script is read-only.
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
      --bucket)
        BUCKET="${2:-}"
        shift 2
        ;;
      --environment)
        ENVIRONMENT="${2:-}"
        shift 2
        ;;
      --history-index)
        HISTORY_INDEX="${2:-}"
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
  [ -n "$BUCKET" ] || die "--bucket is required."

  case "$ENVIRONMENT" in
    dev|prod) ;;
    *) die "--environment must be dev or prod." ;;
  esac

  if ! [[ "$HISTORY_INDEX" =~ ^[0-9]+$ ]] || [ "$HISTORY_INDEX" -lt 1 ]; then
    die "--history-index must be a positive integer."
  fi
}

write_output_json() {
  local json="$1"

  if [ -n "$OUTPUT_FILE" ]; then
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    printf '%s\n' "$json" > "$OUTPUT_FILE"
  else
    printf '%s\n' "$json"
  fi
}

select_previous_record() {
  local work_dir
  local current_file
  local current_uri
  local current_run_id
  local current_deployed_at
  local prefix
  local keys_json
  local selected_count=0
  local selected_key=""
  local selected_file=""
  local key
  local record_file
  local record_run_id
  local record_deployed_at
  local json

  work_dir="$(mktemp -d)"
  current_file="${work_dir}/current.json"
  prefix="environments/${ENVIRONMENT}/history/"

  if ! aws s3 cp "s3://${BUCKET}/environments/${ENVIRONMENT}/current.json" "$current_file" --no-progress >/dev/null; then
    rm -rf "$work_dir"
    die "Could not read s3://${BUCKET}/environments/${ENVIRONMENT}/current.json."
  fi

  "$ROOT_DIR/scripts/validate-deployment-record.sh" "$current_file"
  current_uri="$(jq -er '.releaseManifestUri' "$current_file")"
  current_run_id="$(jq -er '.githubRunId' "$current_file")"
  current_deployed_at="$(jq -er '.deployedAt' "$current_file")"

  if ! keys_json="$(aws s3api list-objects-v2 \
    --bucket "$BUCKET" \
    --prefix "$prefix" \
    --query 'Contents[].Key' \
    --output json)"; then
    rm -rf "$work_dir"
    die "Could not list s3://${BUCKET}/${prefix}."
  fi

  while IFS= read -r key; do
    [ -n "$key" ] || continue

    record_file="${work_dir}/$(basename "$key")"
    if ! aws s3 cp "s3://${BUCKET}/${key}" "$record_file" --no-progress >/dev/null 2>&1; then
      continue
    fi

    if ! "$ROOT_DIR/scripts/validate-deployment-record.sh" "$record_file" >/dev/null 2>&1; then
      continue
    fi

    record_run_id="$(jq -er '.githubRunId' "$record_file")"
    record_deployed_at="$(jq -er '.deployedAt' "$record_file")"

    if [ "$record_run_id" = "$current_run_id" ] && [ "$record_deployed_at" = "$current_deployed_at" ]; then
      continue
    fi

    selected_count=$((selected_count + 1))
    if [ "$selected_count" -eq "$HISTORY_INDEX" ]; then
      selected_key="$key"
      selected_file="$record_file"
      break
    fi
  done < <(jq -r '.[]?' <<<"$keys_json" | sort -r)

  if [ -z "$selected_key" ]; then
    rm -rf "$work_dir"
    die "No previous deployment record found for environment=${ENVIRONMENT} at history_index=${HISTORY_INDEX}."
  fi

  json="$(jq -n \
    --arg bucket "$BUCKET" \
    --arg environment "$ENVIRONMENT" \
    --arg history_index "$HISTORY_INDEX" \
    --arg current_deployment_record_uri "s3://${BUCKET}/environments/${ENVIRONMENT}/current.json" \
    --arg current_manifest_uri "$current_uri" \
    --arg selected_deployment_record_uri "s3://${BUCKET}/${selected_key}" \
    --arg selected_release_manifest_uri "$(jq -er '.releaseManifestUri' "$selected_file")" \
    --arg selected_git_sha "$(jq -er '.gitSha' "$selected_file")" \
    --arg selected_image_digest "$(jq -er '.imageDigest' "$selected_file")" \
    '{
      bucket: $bucket,
      environment: $environment,
      historyIndex: ($history_index | tonumber),
      currentDeploymentRecordUri: $current_deployment_record_uri,
      currentManifestUri: $current_manifest_uri,
      selectedDeploymentRecordUri: $selected_deployment_record_uri,
      selectedReleaseManifestUri: $selected_release_manifest_uri,
      selectedGitSha: $selected_git_sha,
      selectedImageDigest: $selected_image_digest
    }')"

  rm -rf "$work_dir"
  write_output_json "$json"
}

main() {
  parse_args "$@"
  require_command aws
  require_command jq
  validate_args
  select_previous_record
}

main "$@"
