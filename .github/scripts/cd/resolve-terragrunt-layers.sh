#!/usr/bin/env bash
set -euo pipefail

TARGET_ENV="${TARGET_ENV:-dev}"
SAFE_PATHS_FILE="${SAFE_PATHS_FILE:-}"
HIGH_RISK_PATHS_FILE="${HIGH_RISK_PATHS_FILE:-}"
INFRA_PATHS_FILE="${INFRA_PATHS_FILE:-}"
OUTPUT_DIR="${OUTPUT_DIR:-}"

usage() {
  cat <<'EOF'
Usage:
  resolve-terragrunt-layers.sh --target-env dev \
    --safe-paths-file FILE --high-risk-paths-file FILE --infra-paths-file FILE \
    --output-dir DIR

Input files may be newline-delimited paths or JSON arrays. The script writes
deterministic newline-delimited outputs to OUTPUT_DIR:
  safe-layers.txt
  high-risk-layers.txt
  critical-manual-only-layers.txt
  critical-manual-only-paths.txt
  unmapped-high-risk-paths.txt
  changed-high-risk-paths.txt
EOF
}

die() {
  echo "::error::$*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --target-env)
        TARGET_ENV="${2:-}"
        shift 2
        ;;
      --safe-paths-file)
        SAFE_PATHS_FILE="${2:-}"
        shift 2
        ;;
      --high-risk-paths-file)
        HIGH_RISK_PATHS_FILE="${2:-}"
        shift 2
        ;;
      --infra-paths-file)
        INFRA_PATHS_FILE="${2:-}"
        shift 2
        ;;
      --output-dir)
        OUTPUT_DIR="${2:-}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done
}

validate_inputs() {
  case "$TARGET_ENV" in
    dev|prod) ;;
    *) die "Unsupported TARGET_ENV=${TARGET_ENV}." ;;
  esac

  [ -n "$SAFE_PATHS_FILE" ] || die "--safe-paths-file is required."
  [ -n "$HIGH_RISK_PATHS_FILE" ] || die "--high-risk-paths-file is required."
  [ -n "$INFRA_PATHS_FILE" ] || die "--infra-paths-file is required."
  [ -n "$OUTPUT_DIR" ] || die "--output-dir is required."

  [ -f "$SAFE_PATHS_FILE" ] || die "Safe paths file not found: $SAFE_PATHS_FILE"
  [ -f "$HIGH_RISK_PATHS_FILE" ] || die "High-risk paths file not found: $HIGH_RISK_PATHS_FILE"
  [ -f "$INFRA_PATHS_FILE" ] || die "Infra paths file not found: $INFRA_PATHS_FILE"

  mkdir -p "$OUTPUT_DIR"
}

first_non_space_char() {
  tr -d '\n\r\t ' < "$1" | cut -c 1
}

normalize_paths_file() {
  local input_file="$1"
  local output_file="$2"
  local first_char

  : > "$output_file"
  first_char="$(first_non_space_char "$input_file")"

  if [ -z "$first_char" ]; then
    return 0
  fi

  if [ "$first_char" = "[" ]; then
    require_command jq
    jq -r '.[] | select(type == "string" and length > 0)' "$input_file" > "$output_file"
  else
    while IFS= read -r path || [ -n "$path" ]; do
      [ -n "$path" ] && printf '%s\n' "$path"
    done < "$input_file" > "$output_file"
  fi
}

add_unique() {
  local file="$1"
  local value="$2"

  if [ -n "$value" ] && ! grep -Fxq "$value" "$file"; then
    printf '%s\n' "$value" >> "$file"
  fi
}

mark_classified() {
  local path="$1"

  add_unique "$CLASSIFIED_PATHS_FILE" "$path"
}

mark_critical_path() {
  local path="$1"
  local layer="$2"
  local unmapped="${3:-false}"

  add_unique "$CRITICAL_PATHS_FILE" "$path"
  add_unique "$CRITICAL_LAYERS_RAW_FILE" "$layer"
  if [ "$unmapped" = "true" ]; then
    add_unique "$UNMAPPED_PATHS_FILE" "$path"
  fi
  mark_classified "$path"
}

ordered_layers() {
  local order="$1"
  local raw_file="$2"
  local output_file="$3"
  local layer

  : > "$output_file"
  for layer in $order; do
    if grep -Fxq "$layer" "$raw_file"; then
      printf '%s\n' "$layer" >> "$output_file"
    fi
  done
}

classify_safe_paths() {
  local path

  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    case "$path" in
      terraform/live/dev/root.hcl|terraform/live/dev/*/root.hcl)
        mark_critical_path "$path" "dev-root-review"
        ;;
      terraform/infra/modules/*|terraform/infra/*/modules/*)
        mark_critical_path "$path" "shared-module-review"
        ;;
      terraform/live/dev/shared/*|terraform/infra/shared/*)
        add_unique "$SAFE_LAYERS_RAW_FILE" "shared"
        mark_classified "$path"
        ;;
      terraform/live/dev/secrets/*|terraform/infra/secrets/*)
        add_unique "$SAFE_LAYERS_RAW_FILE" "secrets"
        mark_classified "$path"
        ;;
      terraform/live/dev/global/*|terraform/infra/global/*)
        add_unique "$SAFE_LAYERS_RAW_FILE" "global"
        mark_classified "$path"
        ;;
      terraform/live/dev/platform/*|terraform/infra/platform/*)
        add_unique "$SAFE_LAYERS_RAW_FILE" "platform"
        mark_classified "$path"
        ;;
      terraform/live/dev/edge/*|terraform/infra/edge/*)
        add_unique "$SAFE_LAYERS_RAW_FILE" "edge"
        mark_classified "$path"
        ;;
    esac
  done < "$SAFE_PATHS_NORMALIZED_FILE"
}

classify_high_risk_paths() {
  local path

  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    add_unique "$CHANGED_HIGH_RISK_PATHS_FILE" "$path"
    case "$path" in
      terraform/live/dev/root.hcl|terraform/live/dev/*/root.hcl)
        mark_critical_path "$path" "dev-root-review"
        ;;
      terraform/infra/modules/*|terraform/infra/*/modules/*)
        mark_critical_path "$path" "shared-module-review"
        ;;
      terraform/live/dev/data/*|terraform/infra/data/*)
        add_unique "$HIGH_RISK_LAYERS_RAW_FILE" "data"
        mark_classified "$path"
        ;;
      terraform/live/dev/apps/*|terraform/infra/apps/*)
        add_unique "$HIGH_RISK_LAYERS_RAW_FILE" "apps/fargate"
        mark_classified "$path"
        ;;
      *)
        mark_critical_path "$path" "unmapped-review" "true"
        ;;
    esac
  done < "$HIGH_RISK_PATHS_NORMALIZED_FILE"
}

classify_unmapped_infra_paths() {
  local path

  while IFS= read -r path || [ -n "$path" ]; do
    [ -n "$path" ] || continue
    if grep -Fxq "$path" "$CLASSIFIED_PATHS_FILE"; then
      continue
    fi

    case "$path" in
      terraform/docs/*|terraform/live/prod/*|.github/workflows/*|.github/actions/*|.github/scripts/*|scripts/*|ci/schemas/*)
        ;;
      terraform/live/dev/root.hcl|terraform/live/dev/*/root.hcl)
        mark_critical_path "$path" "dev-root-review"
        ;;
      terraform/infra/modules/*|terraform/infra/*/modules/*)
        mark_critical_path "$path" "shared-module-review"
        ;;
      terraform/live/dev/*|terraform/infra/*)
        mark_critical_path "$path" "unmapped-review" "true"
        ;;
    esac
  done < "$INFRA_PATHS_NORMALIZED_FILE"
}

main() {
  parse_args "$@"
  validate_inputs

  SAFE_PATHS_NORMALIZED_FILE="${OUTPUT_DIR}/safe-paths.normalized.txt"
  HIGH_RISK_PATHS_NORMALIZED_FILE="${OUTPUT_DIR}/high-risk-paths.normalized.txt"
  INFRA_PATHS_NORMALIZED_FILE="${OUTPUT_DIR}/infra-paths.normalized.txt"
  SAFE_LAYERS_RAW_FILE="${OUTPUT_DIR}/safe-layers.raw.txt"
  HIGH_RISK_LAYERS_RAW_FILE="${OUTPUT_DIR}/high-risk-layers.raw.txt"
  CRITICAL_LAYERS_RAW_FILE="${OUTPUT_DIR}/critical-manual-only-layers.raw.txt"
  CLASSIFIED_PATHS_FILE="${OUTPUT_DIR}/classified-infra-paths.txt"
  SAFE_LAYERS_FILE="${OUTPUT_DIR}/safe-layers.txt"
  HIGH_RISK_LAYERS_FILE="${OUTPUT_DIR}/high-risk-layers.txt"
  CRITICAL_LAYERS_FILE="${OUTPUT_DIR}/critical-manual-only-layers.txt"
  CRITICAL_PATHS_FILE="${OUTPUT_DIR}/critical-manual-only-paths.txt"
  UNMAPPED_PATHS_FILE="${OUTPUT_DIR}/unmapped-high-risk-paths.txt"
  CHANGED_HIGH_RISK_PATHS_FILE="${OUTPUT_DIR}/changed-high-risk-paths.txt"

  normalize_paths_file "$SAFE_PATHS_FILE" "$SAFE_PATHS_NORMALIZED_FILE"
  normalize_paths_file "$HIGH_RISK_PATHS_FILE" "$HIGH_RISK_PATHS_NORMALIZED_FILE"
  normalize_paths_file "$INFRA_PATHS_FILE" "$INFRA_PATHS_NORMALIZED_FILE"

  : > "$SAFE_LAYERS_RAW_FILE"
  : > "$HIGH_RISK_LAYERS_RAW_FILE"
  : > "$CRITICAL_LAYERS_RAW_FILE"
  : > "$CLASSIFIED_PATHS_FILE"
  : > "$CRITICAL_PATHS_FILE"
  : > "$UNMAPPED_PATHS_FILE"
  : > "$CHANGED_HIGH_RISK_PATHS_FILE"

  classify_safe_paths
  classify_high_risk_paths
  classify_unmapped_infra_paths

  ordered_layers "shared secrets global platform edge" "$SAFE_LAYERS_RAW_FILE" "$SAFE_LAYERS_FILE"
  ordered_layers "data apps/fargate" "$HIGH_RISK_LAYERS_RAW_FILE" "$HIGH_RISK_LAYERS_FILE"
  ordered_layers "dev-root-review shared-module-review unmapped-review" "$CRITICAL_LAYERS_RAW_FILE" "$CRITICAL_LAYERS_FILE"
}

main "$@"
