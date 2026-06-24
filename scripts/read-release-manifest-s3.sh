#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MANIFEST_URI=""
BUCKET=""
APP_NAME="demo-api"
GIT_SHA=""
RUN_ID=""
DIGEST=""
ENVIRONMENT_CURRENT=""
OUTPUT_FILE=""
RESOLUTION_OUTPUT=""

usage() {
  cat <<'EOF'
Usage:
  scripts/read-release-manifest-s3.sh --manifest-uri s3://bucket/key --output FILE
  scripts/read-release-manifest-s3.sh --bucket BUCKET --git-sha SHA --run-id ID --output FILE
  scripts/read-release-manifest-s3.sh --bucket BUCKET --digest sha256:<64 lowercase hex> --output FILE
  scripts/read-release-manifest-s3.sh --bucket BUCKET --environment-current dev|prod --output FILE

Downloads and validates a release manifest from S3. With --environment-current,
the script reads environments/<env>/current.json as a deployment record, then
downloads the release manifest referenced by releaseManifestUri.
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
      --manifest-uri)
        MANIFEST_URI="${2:-}"
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
      --git-sha)
        GIT_SHA="${2:-}"
        shift 2
        ;;
      --run-id)
        RUN_ID="${2:-}"
        shift 2
        ;;
      --digest)
        DIGEST="${2:-}"
        shift 2
        ;;
      --environment-current)
        ENVIRONMENT_CURRENT="${2:-}"
        shift 2
        ;;
      --output)
        OUTPUT_FILE="${2:-}"
        shift 2
        ;;
      --resolution-output)
        RESOLUTION_OUTPUT="${2:-}"
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

selector_count() {
  local count=0

  [ -n "$MANIFEST_URI" ] && count=$((count + 1))
  [ -n "$DIGEST" ] && count=$((count + 1))
  [ -n "$ENVIRONMENT_CURRENT" ] && count=$((count + 1))
  if [ -n "$GIT_SHA" ] || [ -n "$RUN_ID" ]; then
    if [ -z "$GIT_SHA" ] || [ -z "$RUN_ID" ]; then
      die "--git-sha and --run-id must be provided together."
    fi
    count=$((count + 1))
  fi

  printf '%s\n' "$count"
}

parse_s3_uri() {
  local uri="$1"
  local without_scheme

  [[ "$uri" == s3://*/* ]] || die "Invalid S3 URI: $uri"
  without_scheme="${uri#s3://}"
  printf '%s\t%s\n' "${without_scheme%%/*}" "${without_scheme#*/}"
}

resolve_manifest_uri() {
  local digest_key
  local current_file

  [ "$APP_NAME" = "demo-api" ] || die "--app must be demo-api."
  [ -n "$OUTPUT_FILE" ] || die "--output is required."

  if [ "$(selector_count)" != "1" ]; then
    die "Provide exactly one selector: --manifest-uri, --git-sha/--run-id, --digest, or --environment-current."
  fi

  if [ -n "$MANIFEST_URI" ]; then
    return 0
  fi

  [ -n "$BUCKET" ] || die "--bucket is required for selector-based resolution."

  if [ -n "$GIT_SHA" ]; then
    [[ "$GIT_SHA" =~ ^[A-Fa-f0-9]{7,40}$ ]] || die "--git-sha must be a 7 to 40 character git SHA."
    [[ "$RUN_ID" =~ ^[0-9]+$ ]] || die "--run-id must be numeric."
    MANIFEST_URI="s3://${BUCKET}/releases/${APP_NAME}/by-commit/${GIT_SHA}/${RUN_ID}.json"
    return 0
  fi

  if [ -n "$DIGEST" ]; then
    "$ROOT_DIR/scripts/validate-image-digest.sh" --digest "$DIGEST"
    digest_key="${DIGEST/:/-}"
    MANIFEST_URI="s3://${BUCKET}/releases/${APP_NAME}/by-digest/${digest_key}.json"
    return 0
  fi

  case "$ENVIRONMENT_CURRENT" in
    dev|prod) ;;
    *) die "--environment-current must be dev or prod." ;;
  esac

  current_file="$(mktemp)"
  if ! aws s3 cp "s3://${BUCKET}/environments/${ENVIRONMENT_CURRENT}/current.json" "$current_file" --no-progress >/dev/null; then
    rm -f "$current_file"
    die "Could not read s3://${BUCKET}/environments/${ENVIRONMENT_CURRENT}/current.json."
  fi

  "$ROOT_DIR/scripts/validate-deployment-record.sh" "$current_file"
  MANIFEST_URI="$(jq -er '.releaseManifestUri' "$current_file")"
  rm -f "$current_file"
}

download_manifest() {
  local output_dir
  local parsed
  local resolved_bucket
  local resolved_key

  output_dir="$(dirname "$OUTPUT_FILE")"
  mkdir -p "$output_dir"

  if ! aws s3 cp "$MANIFEST_URI" "$OUTPUT_FILE" --no-progress >/dev/null; then
    die "Could not download release manifest: $MANIFEST_URI"
  fi

  "$ROOT_DIR/scripts/validate-release-manifest.sh" "$OUTPUT_FILE"

  parsed="$(parse_s3_uri "$MANIFEST_URI")"
  resolved_bucket="$(cut -f1 <<<"$parsed")"
  resolved_key="$(cut -f2 <<<"$parsed")"

  if [ -n "$RESOLUTION_OUTPUT" ]; then
    mkdir -p "$(dirname "$RESOLUTION_OUTPUT")"
    jq -n \
      --arg bucket "$resolved_bucket" \
      --arg key "$resolved_key" \
      --arg manifest_uri "$MANIFEST_URI" \
      --arg manifest_path "$OUTPUT_FILE" \
      '{
        bucket: $bucket,
        key: $key,
        manifestUri: $manifest_uri,
        manifestPath: $manifest_path
      }' > "$RESOLUTION_OUTPUT"
  else
    jq -n \
      --arg bucket "$resolved_bucket" \
      --arg key "$resolved_key" \
      --arg manifest_uri "$MANIFEST_URI" \
      --arg manifest_path "$OUTPUT_FILE" \
      '{
        bucket: $bucket,
        key: $key,
        manifestUri: $manifest_uri,
        manifestPath: $manifest_path
      }'
  fi
}

main() {
  parse_args "$@"
  require_command aws
  require_command jq
  resolve_manifest_uri
  download_manifest
}

main "$@"
