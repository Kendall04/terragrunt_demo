#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET_ENV="${TARGET_ENV:-}"
APP_CHANGED="${APP_CHANGED:-false}"
INFRA_RAW_CHANGED="${INFRA_RAW_CHANGED:-false}"
SAFE_INFRA_CHANGED="${SAFE_INFRA_CHANGED:-false}"
HIGH_RISK_INFRA_CHANGED="${HIGH_RISK_INFRA_CHANGED:-false}"
PROD_INFRA_CHANGED="${PROD_INFRA_CHANGED:-false}"
INFRA_WORKFLOW_CHANGED="${INFRA_WORKFLOW_CHANGED:-false}"
DOCS_CHANGED="${DOCS_CHANGED:-false}"
APP_PATHS="${APP_PATHS:-[]}"
INFRA_PATHS="${INFRA_PATHS:-[]}"
SAFE_INFRA_PATHS="${SAFE_INFRA_PATHS:-[]}"
HIGH_RISK_PATHS="${HIGH_RISK_PATHS:-[]}"
PROD_INFRA_PATHS="${PROD_INFRA_PATHS:-[]}"
INFRA_WORKFLOW_PATHS="${INFRA_WORKFLOW_PATHS:-[]}"
RUNNER_TEMP="${RUNNER_TEMP:-}"
GITHUB_OUTPUT="${GITHUB_OUTPUT:-}"
GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-}"

die() {
  echo "::error::$*" >&2
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

is_bool() {
  case "$1" in
    true|false) return 0 ;;
    *) return 1 ;;
  esac
}

validate_inputs() {
  [ -n "$TARGET_ENV" ] || die "TARGET_ENV is required."
  [ -n "$RUNNER_TEMP" ] || die "RUNNER_TEMP is required."
  [ -n "$GITHUB_OUTPUT" ] || die "GITHUB_OUTPUT is required."
  [ -n "$GITHUB_STEP_SUMMARY" ] || die "GITHUB_STEP_SUMMARY is required."

  case "$TARGET_ENV" in
    dev|prod) ;;
    *) die "Unsupported TARGET_ENV=${TARGET_ENV}." ;;
  esac

  is_bool "$APP_CHANGED" || die "APP_CHANGED must be true or false."
  is_bool "$INFRA_RAW_CHANGED" || die "INFRA_RAW_CHANGED must be true or false."
  is_bool "$SAFE_INFRA_CHANGED" || die "SAFE_INFRA_CHANGED must be true or false."
  is_bool "$HIGH_RISK_INFRA_CHANGED" || die "HIGH_RISK_INFRA_CHANGED must be true or false."
  is_bool "$PROD_INFRA_CHANGED" || die "PROD_INFRA_CHANGED must be true or false."
  is_bool "$INFRA_WORKFLOW_CHANGED" || die "INFRA_WORKFLOW_CHANGED must be true or false."
  is_bool "$DOCS_CHANGED" || die "DOCS_CHANGED must be true or false."
}

first_non_space_char_from_value() {
  printf '%s' "$1" | tr -d '\n\r\t ' | cut -c 1
}

env_paths_to_file() {
  local value="$1"
  local output_file="$2"
  local first_char

  : > "$output_file"
  if [ -z "$value" ] || [ "$value" = "null" ]; then
    value="[]"
  fi

  first_char="$(first_non_space_char_from_value "$value")"
  if [ -z "$first_char" ]; then
    return 0
  fi

  if [ "$first_char" = "[" ]; then
    jq -r '.[] | select(type == "string" and length > 0)' <<< "$value" > "$output_file"
  else
    while IFS= read -r path || [ -n "$path" ]; do
      [ -n "$path" ] && printf '%s\n' "$path"
    done <<< "$value" > "$output_file"
  fi
}

file_to_string() {
  local file="$1"

  if [ -s "$file" ]; then
    cat "$file"
  fi
}

file_to_json_array() {
  local file="$1"

  jq -Rn '[inputs | select(length > 0)]' < "$file"
}

inline_list() {
  local value="$1"

  if [ -z "$value" ]; then
    printf 'none'
  else
    paste -sd ', ' - <<< "$value" | sed 's/,/, /g'
  fi
}

write_multiline_output() {
  local name="$1"
  local value="$2"

  {
    echo "${name}<<EOF"
    printf '%s\n' "$value"
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
}

write_paths() {
  local title="$1"
  local paths="$2"

  if [ -z "$paths" ]; then
    return 0
  fi

  echo
  echo "### ${title}"
  echo
  while IFS= read -r path; do
    [ -n "$path" ] && echo "- \`$path\`"
  done <<< "$paths"
}

write_scope_json() {
  local output_file="$1"

  jq -n \
    --arg target_env "$TARGET_ENV" \
    --arg app_changed "$app_changed" \
    --arg infra_changed "$infra_changed" \
    --arg safe_dev_infra_changed "$safe_dev_infra_changed" \
    --arg high_risk_dev_infra_changed "$high_risk_dev_infra_changed" \
    --arg high_risk_managed_changed "$high_risk_managed_changed" \
    --arg critical_manual_only_changed "$critical_manual_only_changed" \
    --arg prod_infra_changed "$prod_infra_changed" \
    --arg infra_workflow_changed "$infra_workflow_changed" \
    --arg docs_only "$docs_only" \
    --argjson safe_layers "$(file_to_json_array "$SAFE_LAYERS_FILE")" \
    --argjson high_risk_layers "$(file_to_json_array "$HIGH_RISK_LAYERS_FILE")" \
    --argjson critical_manual_only_layers "$(file_to_json_array "$CRITICAL_LAYERS_FILE")" \
    --argjson unmapped_high_risk_paths "$(file_to_json_array "$UNMAPPED_PATHS_FILE")" \
    --argjson changed_app_paths "$(file_to_json_array "$APP_PATHS_FILE")" \
    --argjson changed_infra_paths "$(file_to_json_array "$INFRA_PATHS_FILE")" \
    --argjson changed_high_risk_paths "$(file_to_json_array "$CHANGED_HIGH_RISK_PATHS_FILE")" \
    --argjson critical_manual_only_paths "$(file_to_json_array "$CRITICAL_PATHS_FILE")" \
    --argjson safe_infra_paths "$(file_to_json_array "$SAFE_INFRA_PATHS_FILE")" \
    --argjson prod_infra_paths "$(file_to_json_array "$PROD_INFRA_PATHS_FILE")" \
    --argjson infra_workflow_paths "$(file_to_json_array "$INFRA_WORKFLOW_PATHS_FILE")" \
    '{
      outputs: {
        target_env: $target_env,
        app_changed: $app_changed,
        infra_changed: $infra_changed,
        safe_dev_infra_changed: $safe_dev_infra_changed,
        safe_infra_changed: $safe_dev_infra_changed,
        high_risk_dev_infra_changed: $high_risk_dev_infra_changed,
        high_risk_managed_changed: $high_risk_managed_changed,
        critical_manual_only_changed: $critical_manual_only_changed,
        prod_infra_changed: $prod_infra_changed,
        infra_workflow_changed: $infra_workflow_changed,
        docs_only: $docs_only,
        safe_layers: $safe_layers,
        high_risk_layers: $high_risk_layers,
        critical_manual_only_layers: $critical_manual_only_layers,
        unmapped_high_risk_paths: $unmapped_high_risk_paths,
        changed_app_paths: $changed_app_paths,
        changed_infra_paths: $changed_infra_paths,
        changed_high_risk_paths: $changed_high_risk_paths,
        critical_manual_only_paths: $critical_manual_only_paths,
        safe_infra_paths: $safe_infra_paths,
        prod_infra_paths: $prod_infra_paths,
        infra_workflow_paths: $infra_workflow_paths,
        infra_paths: $changed_infra_paths,
        high_risk_paths: $changed_high_risk_paths
      }
    }' > "$output_file"
}

write_github_outputs() {
  {
    echo "target_env=${TARGET_ENV}"
    echo "app_changed=$app_changed"
    echo "infra_changed=$infra_changed"
    echo "safe_dev_infra_changed=$safe_dev_infra_changed"
    echo "safe_infra_changed=$safe_dev_infra_changed"
    echo "high_risk_dev_infra_changed=$high_risk_dev_infra_changed"
    echo "high_risk_managed_changed=$high_risk_managed_changed"
    echo "critical_manual_only_changed=$critical_manual_only_changed"
    echo "prod_infra_changed=$prod_infra_changed"
    echo "infra_workflow_changed=$infra_workflow_changed"
    echo "docs_only=$docs_only"
  } >> "$GITHUB_OUTPUT"

  write_multiline_output "safe_layers" "$safe_layers"
  write_multiline_output "high_risk_layers" "$high_risk_layers"
  write_multiline_output "critical_manual_only_layers" "$critical_manual_only_layers"
  write_multiline_output "unmapped_high_risk_paths" "$unmapped_high_risk_paths"
  write_multiline_output "changed_app_paths" "$app_paths"
  write_multiline_output "changed_infra_paths" "$infra_paths"
  write_multiline_output "changed_high_risk_paths" "$changed_high_risk_paths"
  write_multiline_output "critical_manual_only_paths" "$critical_manual_only_paths"
  write_multiline_output "safe_infra_paths" "$safe_infra_paths"
  write_multiline_output "prod_infra_paths" "$prod_infra_paths"
  write_multiline_output "infra_workflow_paths" "$infra_workflow_paths"
  write_multiline_output "infra_paths" "$infra_paths"
  write_multiline_output "high_risk_paths" "$changed_high_risk_paths"
}

write_summary() {
  {
    echo "## CD scope"
    echo
    echo "| Scope | Value |"
    echo "| --- | --- |"
    echo "| Target environment | ${TARGET_ENV} |"
    echo "| App changed | $app_changed |"
    echo "| Infra changed | $infra_changed |"
    echo "| Safe dev infra changed | $safe_dev_infra_changed |"
    echo "| High-risk dev infra changed | $high_risk_dev_infra_changed |"
    echo "| High-risk managed layers | $(inline_list "$high_risk_layers") |"
    echo "| Critical/manual-only changed | $critical_manual_only_changed |"
    echo "| Critical/manual-only layers | $(inline_list "$critical_manual_only_layers") |"
    echo "| Prod infra changed | $prod_infra_changed |"
    echo "| Infra workflow changed | $infra_workflow_changed |"
    echo "| Docs only | $docs_only |"
    echo
    echo "### Classification"
    echo
    echo "- Safe dev infra layers are eligible for automatic dev apply."
    echo "- High-risk managed layers require the \`dev-infra-approval\` environment gate before apply."
    echo "- Critical/manual-only paths are not applied by this orchestrator; use **CD - Terragrunt Layer** or explicit human ops."
    echo
    echo "### Safe dev layers"
    echo
    if [ -n "$safe_layers" ]; then
      while IFS= read -r layer; do
        [ -n "$layer" ] && echo "- \`${layer}\`"
      done <<< "$safe_layers"
    else
      echo "- none"
    fi
    echo
    echo "### High-risk managed layers"
    echo
    if [ -n "$high_risk_layers" ]; then
      while IFS= read -r layer; do
        [ -n "$layer" ] && echo "- \`${layer}\`"
      done <<< "$high_risk_layers"
    else
      echo "- none"
    fi
    write_paths "App paths" "$app_paths"
    write_paths "Infra paths" "$infra_paths"
    write_paths "Safe dev infra paths" "$safe_infra_paths"
    write_paths "High-risk dev infra paths" "$changed_high_risk_paths"
    write_paths "Critical/manual-only paths" "$critical_manual_only_paths"
    write_paths "Unmapped high-risk paths" "$unmapped_high_risk_paths"
    write_paths "Prod infra paths" "$prod_infra_paths"
    write_paths "Infra workflow paths" "$infra_workflow_paths"
  } >> "$GITHUB_STEP_SUMMARY"
}

main() {
  require_command jq
  validate_inputs

  scope_work_dir="${RUNNER_TEMP}/cd-scope"
  mkdir -p "$scope_work_dir"

  APP_PATHS_FILE="${scope_work_dir}/app-paths.txt"
  INFRA_PATHS_FILE="${scope_work_dir}/infra-paths.txt"
  SAFE_INFRA_PATHS_FILE="${scope_work_dir}/safe-infra-paths.txt"
  HIGH_RISK_PATHS_FILE="${scope_work_dir}/high-risk-paths.txt"
  PROD_INFRA_PATHS_FILE="${scope_work_dir}/prod-infra-paths.txt"
  INFRA_WORKFLOW_PATHS_FILE="${scope_work_dir}/infra-workflow-paths.txt"
  RESOLVED_DIR="${scope_work_dir}/resolved"

  env_paths_to_file "$APP_PATHS" "$APP_PATHS_FILE"
  env_paths_to_file "$INFRA_PATHS" "$INFRA_PATHS_FILE"
  env_paths_to_file "$SAFE_INFRA_PATHS" "$SAFE_INFRA_PATHS_FILE"
  env_paths_to_file "$HIGH_RISK_PATHS" "$HIGH_RISK_PATHS_FILE"
  env_paths_to_file "$PROD_INFRA_PATHS" "$PROD_INFRA_PATHS_FILE"
  env_paths_to_file "$INFRA_WORKFLOW_PATHS" "$INFRA_WORKFLOW_PATHS_FILE"

  "$SCRIPT_DIR/resolve-terragrunt-layers.sh" \
    --target-env "$TARGET_ENV" \
    --safe-paths-file "$SAFE_INFRA_PATHS_FILE" \
    --high-risk-paths-file "$HIGH_RISK_PATHS_FILE" \
    --infra-paths-file "$INFRA_PATHS_FILE" \
    --output-dir "$RESOLVED_DIR"

  SAFE_LAYERS_FILE="${RESOLVED_DIR}/safe-layers.txt"
  HIGH_RISK_LAYERS_FILE="${RESOLVED_DIR}/high-risk-layers.txt"
  CRITICAL_LAYERS_FILE="${RESOLVED_DIR}/critical-manual-only-layers.txt"
  CRITICAL_PATHS_FILE="${RESOLVED_DIR}/critical-manual-only-paths.txt"
  UNMAPPED_PATHS_FILE="${RESOLVED_DIR}/unmapped-high-risk-paths.txt"
  CHANGED_HIGH_RISK_PATHS_FILE="${RESOLVED_DIR}/changed-high-risk-paths.txt"

  app_changed="$APP_CHANGED"
  infra_raw_changed="$INFRA_RAW_CHANGED"
  prod_infra_changed="$PROD_INFRA_CHANGED"
  infra_workflow_changed="$INFRA_WORKFLOW_CHANGED"
  docs_changed="$DOCS_CHANGED"

  safe_layers="$(file_to_string "$SAFE_LAYERS_FILE")"
  high_risk_layers="$(file_to_string "$HIGH_RISK_LAYERS_FILE")"
  critical_manual_only_layers="$(file_to_string "$CRITICAL_LAYERS_FILE")"
  critical_manual_only_paths="$(file_to_string "$CRITICAL_PATHS_FILE")"
  unmapped_high_risk_paths="$(file_to_string "$UNMAPPED_PATHS_FILE")"
  changed_high_risk_paths="$(file_to_string "$CHANGED_HIGH_RISK_PATHS_FILE")"
  app_paths="$(file_to_string "$APP_PATHS_FILE")"
  infra_paths="$(file_to_string "$INFRA_PATHS_FILE")"
  safe_infra_paths="$(file_to_string "$SAFE_INFRA_PATHS_FILE")"
  prod_infra_paths="$(file_to_string "$PROD_INFRA_PATHS_FILE")"
  infra_workflow_paths="$(file_to_string "$INFRA_WORKFLOW_PATHS_FILE")"

  safe_dev_infra_changed="false"
  if [ -n "$safe_layers" ]; then
    safe_dev_infra_changed="true"
  fi

  high_risk_dev_infra_changed="false"
  if [ -n "$high_risk_layers" ] || [ -n "$critical_manual_only_paths" ] || [ -n "$unmapped_high_risk_paths" ]; then
    high_risk_dev_infra_changed="true"
  fi

  high_risk_managed_changed="false"
  if [ -n "$high_risk_layers" ]; then
    high_risk_managed_changed="true"
  fi

  critical_manual_only_changed="false"
  if [ -n "$critical_manual_only_paths" ] || [ -n "$unmapped_high_risk_paths" ]; then
    critical_manual_only_changed="true"
  fi

  docs_only="false"
  if [ "$docs_changed" = "true" ] \
    && [ "$app_changed" != "true" ] \
    && [ "$safe_dev_infra_changed" != "true" ] \
    && [ "$high_risk_dev_infra_changed" != "true" ] \
    && [ "$prod_infra_changed" != "true" ] \
    && [ "$infra_workflow_changed" != "true" ]; then
    docs_only="true"
  fi

  infra_changed="$infra_raw_changed"
  if [ "$docs_only" = "true" ]; then
    infra_changed="false"
  fi

  write_scope_json "${RUNNER_TEMP}/cd-scope.json"
  write_github_outputs
  write_summary
}

main "$@"
