#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECORD_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/validate-deployment-record.sh FILE

Validates a Demo API deployment record. The record describes where a release
manifest was deployed and must reference a digest-based image URI.
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

  jq -er "$query" "$RECORD_FILE"
}

validate_required_json() {
  jq -e '
    type == "object"
    and .schemaVersion == "1.0"
    and .app == "demo-api"
    and (.environment as $environment | ["dev", "prod"] | index($environment) != null)
    and (.releaseManifestUri | test("^s3://[^/]+/.+"))
    and (.gitSha | test("^[A-Fa-f0-9]{7,40}$"))
    and (.imageDigest | test("^sha256:[a-f0-9]{64}$"))
    and (.imageUri | type == "string" and length > 0)
    and (.deployedAt | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"))
    and (.githubRunId | test("^[0-9]+$"))
    and (.deployment.strategy == "blue-green")
    and ((.deployment.previousColor == null) or (.deployment.previousColor as $previous_color | ["blue", "green"] | index($previous_color) != null))
    and (.deployment.newColor as $new_color | ["blue", "green"] | index($new_color) != null)
    and (.deployment.activeService | type == "string" and length > 0)
    and (.deployment.inactiveService | type == "string" and length > 0)
    and (.deployment.taskDefinitionArn | test("^arn:aws:ecs:[A-Za-z0-9-]+:[0-9]{12}:task-definition/.+:[0-9]+$"))
    and (.deployment.listenerArn | test("^arn:aws:elasticloadbalancing:[A-Za-z0-9-]+:[0-9]{12}:listener/.+"))
    and (.deployment.targetGroupArn | test("^arn:aws:elasticloadbalancing:[A-Za-z0-9-]+:[0-9]{12}:targetgroup/.+"))
    and (
      (.rollback == null)
      or (
        (.rollback | type == "object")
        and (.rollback.isRollback == true)
        and (.rollback.reason | type == "string")
        and (.rollback.selectorType as $selector_type | ["manifest_uri", "git_sha_run_id", "digest", "previous_environment_history"] | index($selector_type) != null)
        and (.rollback.selectedManifestUri | test("^s3://[^/]+/.+"))
        and (.rollback.previousCurrentManifestUri | test("^s3://[^/]+/.+"))
        and (.rollback.requestedBy | type == "string" and length > 0)
      )
    )
    and (.status as $status | ["success", "failed"] | index($status) != null)
  ' "$RECORD_FILE" >/dev/null || die "Deployment record is missing required fields or has invalid values."
}

validate_image_fields() {
  local digest
  local image_uri

  digest="$(json_value '.imageDigest')"
  image_uri="$(json_value '.imageUri')"

  "$ROOT_DIR/scripts/validate-image-digest.sh" \
    --digest "$digest" \
    --image-uri "$image_uri"
}

main() {
  if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
  fi

  RECORD_FILE="${1:-}"
  [ -n "$RECORD_FILE" ] || die "Deployment record file is required."
  [ -f "$RECORD_FILE" ] || die "Deployment record file not found."

  require_command jq
  validate_required_json
  validate_image_fields
}

main "$@"
