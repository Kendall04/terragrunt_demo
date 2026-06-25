#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MANIFEST_FILE=""
BUCKET=""
APP_NAME="demo-api"
SOURCE_BRANCH="develop"
OUTPUT_FILE=""
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  scripts/publish-release-manifest-s3.sh --manifest FILE --bucket BUCKET \
    --app demo-api --source-branch develop [--output FILE] [--dry-run]

Publishes a validated release manifest to durable S3 indexes:
  releases/demo-api/by-digest/sha256-<digest-without-colon>.json
  releases/demo-api/by-commit/<git-sha>/<github-run-id>.json
  releases/demo-api/candidates/develop/<git-sha>.json
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
      --manifest)
        MANIFEST_FILE="${2:-}"
        shift 2
        ;;
      --bucket)
        BUCKET="${2:-}"
        shift 2
        ;;
      --app)
        APP_NAME="${2:-}"
        shift 2
        ;;
      --source-branch)
        SOURCE_BRANCH="${2:-}"
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
  local manifest_source_branch

  [ "$APP_NAME" = "demo-api" ] || die "--app must be demo-api."
  [ "$SOURCE_BRANCH" = "develop" ] || die "--source-branch must be develop for Phase 4 candidate publishing."
  [ -n "$MANIFEST_FILE" ] || die "--manifest is required."
  [ -f "$MANIFEST_FILE" ] || die "Manifest file not found: $MANIFEST_FILE"
  [ -n "$BUCKET" ] || die "--bucket is required."

  "$ROOT_DIR/scripts/validate-release-manifest.sh" "$MANIFEST_FILE"

  manifest_source_branch="$(jq -er '.sourceBranch' "$MANIFEST_FILE")"
  [ "$manifest_source_branch" = "$SOURCE_BRANCH" ] || die "Manifest sourceBranch does not match --source-branch."
}

require_bucket() {
  if [ "$DRY_RUN" = "true" ]; then
    return 0
  fi

  if ! aws s3api get-bucket-location --bucket "$BUCKET" >/dev/null 2>&1; then
    die "Release artifacts bucket '$BUCKET' was not found or is not accessible. Bootstrap terraform/live/dev/shared before running Phase 4 app CD."
  fi
}

write_output_json() {
  local by_digest_uri="$1"
  local by_commit_uri="$2"
  local candidate_uri="$3"
  local digest="$4"
  local git_sha="$5"
  local github_run_id="$6"
  local output_dir
  local json

  if [ -n "$OUTPUT_FILE" ]; then
    output_dir="$(dirname "$OUTPUT_FILE")"
    mkdir -p "$output_dir"
  fi

  json="$(jq -n \
    --arg bucket "$BUCKET" \
    --arg by_digest_uri "$by_digest_uri" \
    --arg by_commit_uri "$by_commit_uri" \
    --arg candidate_uri "$candidate_uri" \
    --arg digest "$digest" \
    --arg git_sha "$git_sha" \
    --arg github_run_id "$github_run_id" \
    '{
      bucket: $bucket,
      byDigestUri: $by_digest_uri,
      byCommitUri: $by_commit_uri,
      candidateUri: $candidate_uri,
      digest: $digest,
      gitSha: $git_sha,
      githubRunId: $github_run_id
    }')"

  if [ -n "$OUTPUT_FILE" ]; then
    printf '%s\n' "$json" > "$OUTPUT_FILE"
  else
    printf '%s\n' "$json"
  fi
}

put_manifest() {
  local key="$1"

  if [ "$DRY_RUN" = "true" ]; then
    log "Dry run: would publish s3://${BUCKET}/${key}"
    return 0
  fi

  aws s3 cp "$MANIFEST_FILE" "s3://${BUCKET}/${key}" \
    --content-type "application/json" \
    --no-progress >/dev/null
}

publish_manifest() {
  local git_sha
  local github_run_id
  local digest
  local digest_key
  local by_digest_key
  local by_commit_key
  local candidate_key

  git_sha="$(jq -er '.gitSha' "$MANIFEST_FILE")"
  github_run_id="$(jq -er '.githubRunId' "$MANIFEST_FILE")"
  digest="$(jq -er '.image.digest' "$MANIFEST_FILE")"

  "$ROOT_DIR/scripts/validate-image-digest.sh" --digest "$digest"

  digest_key="${digest/:/-}"
  by_digest_key="releases/${APP_NAME}/by-digest/${digest_key}.json"
  by_commit_key="releases/${APP_NAME}/by-commit/${git_sha}/${github_run_id}.json"
  candidate_key="releases/${APP_NAME}/candidates/${SOURCE_BRANCH}/${git_sha}.json"

  put_manifest "$by_digest_key"
  put_manifest "$by_commit_key"
  put_manifest "$candidate_key"

  write_output_json \
    "s3://${BUCKET}/${by_digest_key}" \
    "s3://${BUCKET}/${by_commit_key}" \
    "s3://${BUCKET}/${candidate_key}" \
    "$digest" \
    "$git_sha" \
    "$github_run_id"
}

main() {
  parse_args "$@"
  require_command jq
  if [ "$DRY_RUN" != "true" ]; then
    require_command aws
  fi
  validate_args
  require_bucket
  publish_manifest
}

main "$@"
