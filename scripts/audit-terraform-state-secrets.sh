#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="dev"
AWS_REGION_NAME="us-east-1"
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
SCAN_HISTORICAL="false"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  scripts/audit-terraform-state-secrets.sh [options]

Read-only Terraform state secret-risk audit. The script never prints full state,
secret values, state object keys, S3 bucket names, ARNs, or AWS account IDs.

Options:
  --env ENV            Environment name: dev or prod. Default: dev
  --region REGION      AWS region. Default: us-east-1
  --profile PROFILE    AWS CLI profile to use
  --use-instance-role  Use the default AWS credential chain / EC2 instance role
  --historical         Also scan historical S3 object versions
  --dry-run            Show what would be scanned without reading state objects
  -h, --help           Show this help

Exit codes:
  0  No exact secret-value resource types found
  2  Exact secret-value resource type or credential random_string found
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

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

validate_env_name() {
  case "$ENV_NAME" in
    dev|prod) ;;
    *) die "Unsupported --env '$ENV_NAME'. Supported values: dev, prod." ;;
  esac
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
      --historical)
        SCAN_HISTORICAL="true"
        shift
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

redact_text() {
  sed -E \
    -e 's/[0-9]{12}/<aws-account-id>/g' \
    -e 's#arn:aws:[^[:space:]"'"'"']+#<aws-arn>#g' \
    -e 's#s3://[^[:space:]"'"'"']+#s3://<redacted>#g' \
    -e 's#tfstate-demo-[A-Za-z0-9._-]+-[0-9]{12}#tfstate-demo-<env>-<aws-account-id>#g' \
    -e 's#tfstate-locks-[0-9]{12}#tfstate-locks-<aws-account-id>#g'
}

scan_state_file() {
  local state_file="$1"
  local layer_label="$2"
  local scan_label="$3"
  local findings_tmp="$4"
  local result_tmp

  result_tmp="$(mktemp "$TMP_DIR/findings.XXXXXX")"

  jq -r '
    def patt: "password|passwd|credential|secret|token|connection[_-]?string|private[_-]?key";
    def addr:
      (((.module // "") + (if .module then "." else "" end) + .type + "." + .name));

    (
      .resources[]?
      | addr as $addr
      | .type as $type
      | [
          if ($type == "random_password"
              or $type == "aws_secretsmanager_secret_version"
              or $type == "aws_ssm_parameter") then
            "exact-secret-value-resource|" + $addr
          else empty end,
          if ($type == "random_string" and ($addr | test(patt; "i"))) then
            "credential-random-string|" + $addr
          else empty end,
          if (($addr | test(patt; "i")) or ($type | test(patt; "i"))) then
            "metadata-pattern|" + $addr
          else empty end
        ][]
    ),
    (
      (.outputs // {})
      | to_entries[]?
      | select(.key | test(patt; "i"))
      | "output-pattern|output." + .key
    )
  ' "$state_file" | sort -u >"$result_tmp"

  if [ -s "$result_tmp" ]; then
    printf '[%s] %s\n' "$scan_label" "$layer_label"
    while IFS='|' read -r category address; do
      printf '  finding: category=%s address=%s\n' "$category" "$address" | redact_text
    done <"$result_tmp"
    cat "$result_tmp" >>"$findings_tmp"
  else
    printf '[%s] %s: no risky resource/output names found\n' "$scan_label" "$layer_label"
  fi
}

latest_scan() {
  local state_bucket="$1"
  local findings_tmp="$2"
  local layer_spec
  local layer_label
  local state_key
  local state_tmp

  log "Latest state scan started. State bucket and object keys are redacted."

  for layer_spec in "${STATE_LAYERS[@]}"; do
    layer_label="${layer_spec%%:*}"
    state_key="${layer_spec#*:}"
    state_tmp="$(mktemp "$TMP_DIR/latest.XXXXXX")"

    if aws s3 cp "s3://${state_bucket}/${state_key}" "$state_tmp" --only-show-errors "${AWS_ARGS[@]}" 2>/dev/null; then
      scan_state_file "$state_tmp" "$layer_label" "latest" "$findings_tmp"
    else
      printf '[latest] %s: state not found or inaccessible\n' "$layer_label"
    fi
  done
}

historical_scan() {
  local state_bucket="$1"
  local findings_tmp="$2"
  local layer_spec
  local layer_label
  local state_key
  local versions_tmp
  local row
  local version_id
  local is_latest
  local state_tmp
  local version_index

  log "Historical state version scan started. Version IDs, state bucket, and object keys are redacted."

  for layer_spec in "${STATE_LAYERS[@]}"; do
    layer_label="${layer_spec%%:*}"
    state_key="${layer_spec#*:}"
    versions_tmp="$(mktemp "$TMP_DIR/versions.XXXXXX")"

    if ! aws s3api list-object-versions \
      --bucket "$state_bucket" \
      --prefix "$state_key" \
      --query 'Versions[].{VersionId:VersionId,IsLatest:IsLatest}' \
      --output json \
      "${AWS_ARGS[@]}" >"$versions_tmp" 2>/dev/null; then
      printf '[historical] %s: versions not found or inaccessible\n' "$layer_label"
      continue
    fi

    if [ "$(jq 'length' "$versions_tmp")" -eq 0 ]; then
      printf '[historical] %s: no versions found\n' "$layer_label"
      continue
    fi

    version_index=0
    while IFS= read -r row; do
      version_index=$((version_index + 1))
      version_id="$(printf '%s' "$row" | base64 -d | jq -r '.VersionId')"
      is_latest="$(printf '%s' "$row" | base64 -d | jq -r '.IsLatest')"
      state_tmp="$(mktemp "$TMP_DIR/historical.XXXXXX")"

      if aws s3api get-object \
        --bucket "$state_bucket" \
        --key "$state_key" \
        --version-id "$version_id" \
        "$state_tmp" \
        "${AWS_ARGS[@]}" >/dev/null 2>&1; then
        scan_state_file "$state_tmp" "${layer_label} version #${version_index} latest=${is_latest}" "historical" "$findings_tmp"
      else
        printf '[historical] %s version #%s: unreadable\n' "$layer_label" "$version_index"
      fi
    done < <(jq -r '.[] | @base64' "$versions_tmp")
  done
}

main() {
  parse_args "$@"
  validate_env_name
  require_command aws
  require_command jq

  AWS_ARGS=(--region "$AWS_REGION_NAME")
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    AWS_ARGS+=(--profile "$AWS_PROFILE_NAME")
  fi

  TMP_DIR="$(mktemp -d)"
  chmod 700 "$TMP_DIR"
  trap 'rm -rf "$TMP_DIR"' EXIT

  STATE_LAYERS=(
    "shared:shared/terraform.tfstate"
    "secrets:secrets/terraform.tfstate"
    "global:global/terraform.tfstate"
    "data:data/terraform.tfstate"
    "platform:platform/terraform.tfstate"
    "apps-fargate:apps/fargate/terraform.tfstate"
    "edge:edge/terraform.tfstate"
  )

  log "State secret-risk audit target: env=${ENV_NAME}, region=${AWS_REGION_NAME}, credential_mode=$([ "$USE_INSTANCE_ROLE" = "true" ] && printf 'default-chain' || printf 'profile-or-default')."

  if [ "$DRY_RUN" = "true" ]; then
    log "Dry run only. Would scan latest state for known Terragrunt layers."
    if [ "$SCAN_HISTORICAL" = "true" ]; then
      log "Dry run only. Would also scan historical S3 object versions."
    fi
    exit 0
  fi

  local_account_id="$(aws sts get-caller-identity --query Account --output text "${AWS_ARGS[@]}")"
  if [ -z "$local_account_id" ] || [ "$local_account_id" = "None" ]; then
    die "Could not resolve AWS account ID."
  fi

  state_bucket="${TF_STATE_BUCKET:-tfstate-demo-${ENV_NAME}-${local_account_id}}"
  findings_tmp="$(mktemp "$TMP_DIR/all-findings.XXXXXX")"

  latest_scan "$state_bucket" "$findings_tmp"

  if [ "$SCAN_HISTORICAL" = "true" ]; then
    historical_scan "$state_bucket" "$findings_tmp"
  else
    log "Historical scan skipped. Pass --historical to scan prior S3 state object versions safely."
  fi

  if grep -Eq '^(exact-secret-value-resource|credential-random-string)\|' "$findings_tmp"; then
    warn "Exact secret-value state resource types were found. No values were printed."
    exit 2
  fi

  log "No exact secret-value state resource types found. Review metadata-pattern/output-pattern findings manually; they may be expected references, not leaked values."
}

main "$@"
