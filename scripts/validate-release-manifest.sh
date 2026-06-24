#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/validate-release-manifest.sh FILE

Validates a Demo API release manifest. The manifest records what was built and
must use an immutable image URI in the form <registry>/<repo>@sha256:...
EOF
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

json_value() {
  local query="$1"

  jq -er "$query" "$MANIFEST_FILE"
}

validate_required_json() {
  jq -e '
    type == "object"
    and .schemaVersion == "1.0"
    and .app == "demo-api"
    and (.repository | type == "string" and length > 0)
    and (.gitSha | test("^[A-Fa-f0-9]{7,40}$"))
    and (.sourceBranch | type == "string" and length > 0)
    and (.githubRunId | test("^[0-9]+$"))
    and (.githubRunAttempt | test("^[0-9]+$"))
    and (.createdAt | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"))
    and (.image.registry | type == "string" and length > 0)
    and (.image.repository | type == "string" and length > 0)
    and (.image.tag | test("^[A-Za-z0-9_.-]+$"))
    and (.image.digest | test("^sha256:[a-f0-9]{64}$"))
    and (.image.uri | type == "string" and length > 0)
    and (.quality.dotnetTests as $dotnet_tests | ["passed", "failed", "skipped"] | index($dotnet_tests) != null)
    and (.quality.dockerBuild as $docker_build | ["passed", "failed", "skipped"] | index($docker_build) != null)
    and (.quality.scanStatus as $scan_status | ["passed", "failed", "skipped", "unknown"] | index($scan_status) != null)
  ' "$MANIFEST_FILE" >/dev/null || die "Release manifest is missing required fields or has invalid values."
}

validate_image_fields() {
  local registry
  local image_repo
  local digest
  local image_uri
  local expected_uri

  registry="$(json_value '.image.registry')"
  image_repo="$(json_value '.image.repository')"
  digest="$(json_value '.image.digest')"
  image_uri="$(json_value '.image.uri')"
  expected_uri="${registry}/${image_repo}@${digest}"

  "$ROOT_DIR/scripts/validate-image-digest.sh" \
    --digest "$digest" \
    --image-uri "$image_uri"

  if [ "$image_uri" != "$expected_uri" ]; then
    die "Release manifest image.uri must equal image.registry/image.repository@image.digest."
  fi
}

main() {
  if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
  fi

  MANIFEST_FILE="${1:-}"
  [ -n "$MANIFEST_FILE" ] || die "Manifest file is required."
  [ -f "$MANIFEST_FILE" ] || die "Manifest file not found."

  require_command jq
  validate_required_json
  validate_image_fields
}

main "$@"
