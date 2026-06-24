#!/usr/bin/env bash
set -euo pipefail

APP_CHANGED="${APP_CHANGED:-}"
SAFE_DEV_INFRA_CHANGED="${SAFE_DEV_INFRA_CHANGED:-}"
HIGH_RISK_DEV_INFRA_CHANGED="${HIGH_RISK_DEV_INFRA_CHANGED:-}"
HIGH_RISK_LAYERS="${HIGH_RISK_LAYERS:-}"
CRITICAL_MANUAL_ONLY_PATHS="${CRITICAL_MANUAL_ONLY_PATHS:-}"
UNMAPPED_HIGH_RISK_PATHS="${UNMAPPED_HIGH_RISK_PATHS:-}"
DEV_INFRA_APPLY_RESULT="${DEV_INFRA_APPLY_RESULT:-}"
CRITICAL_MANUAL_ONLY_RESULT="${CRITICAL_MANUAL_ONLY_RESULT:-skipped}"
HIGH_RISK_PLAN_RESULT="${HIGH_RISK_PLAN_RESULT:-}"
HIGH_RISK_APPLY_RESULT="${HIGH_RISK_APPLY_RESULT:-}"
TARGET_ENV="${TARGET_ENV:-}"
GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-}"

die_input() {
  echo "::error::$*" >&2
  exit 2
}

error() {
  echo "::error::$*" >&2
}

is_bool() {
  case "$1" in
    true|false) return 0 ;;
    *) return 1 ;;
  esac
}

is_job_result() {
  case "$1" in
    success|failure|cancelled|skipped) return 0 ;;
    *) return 1 ;;
  esac
}

write_blocking_paths() {
  local title="$1"
  local paths="$2"

  if [ -z "$paths" ]; then
    return 0
  fi

  echo "### ${title}"
  echo
  while IFS= read -r path; do
    [ -n "$path" ] && echo "- \`${path}\`"
  done <<< "$paths"
}

validate_inputs() {
  [ -n "$GITHUB_STEP_SUMMARY" ] || die_input "GITHUB_STEP_SUMMARY is required."
  [ -n "$TARGET_ENV" ] || die_input "TARGET_ENV is required."
  [ -n "$APP_CHANGED" ] || die_input "APP_CHANGED is required."
  [ -n "$SAFE_DEV_INFRA_CHANGED" ] || die_input "SAFE_DEV_INFRA_CHANGED is required."
  [ -n "$HIGH_RISK_DEV_INFRA_CHANGED" ] || die_input "HIGH_RISK_DEV_INFRA_CHANGED is required."
  [ -n "$DEV_INFRA_APPLY_RESULT" ] || die_input "DEV_INFRA_APPLY_RESULT is required."
  [ -n "$HIGH_RISK_PLAN_RESULT" ] || die_input "HIGH_RISK_PLAN_RESULT is required."
  [ -n "$HIGH_RISK_APPLY_RESULT" ] || die_input "HIGH_RISK_APPLY_RESULT is required."

  is_bool "$APP_CHANGED" || die_input "APP_CHANGED must be true or false."
  is_bool "$SAFE_DEV_INFRA_CHANGED" || die_input "SAFE_DEV_INFRA_CHANGED must be true or false."
  is_bool "$HIGH_RISK_DEV_INFRA_CHANGED" || die_input "HIGH_RISK_DEV_INFRA_CHANGED must be true or false."

  is_job_result "$DEV_INFRA_APPLY_RESULT" || die_input "DEV_INFRA_APPLY_RESULT must be one of success, failure, cancelled, skipped."
  is_job_result "$CRITICAL_MANUAL_ONLY_RESULT" || die_input "CRITICAL_MANUAL_ONLY_RESULT must be one of success, failure, cancelled, skipped."
  is_job_result "$HIGH_RISK_PLAN_RESULT" || die_input "HIGH_RISK_PLAN_RESULT must be one of success, failure, cancelled, skipped."
  is_job_result "$HIGH_RISK_APPLY_RESULT" || die_input "HIGH_RISK_APPLY_RESULT must be one of success, failure, cancelled, skipped."
}

main() {
  validate_inputs

  local blocked="false"

  {
    echo "## Infra ready gate"
    echo
    echo "| Gate | Result |"
    echo "| --- | --- |"
    echo "| Safe infra apply job | ${DEV_INFRA_APPLY_RESULT} |"
    echo "| Critical/manual-only notice job | ${CRITICAL_MANUAL_ONLY_RESULT} |"
    echo "| High-risk plan job | ${HIGH_RISK_PLAN_RESULT} |"
    echo "| High-risk apply job | ${HIGH_RISK_APPLY_RESULT} |"
  } >> "$GITHUB_STEP_SUMMARY"

  if [ "$SAFE_DEV_INFRA_CHANGED" = "true" ] && [ "$DEV_INFRA_APPLY_RESULT" != "success" ]; then
    error "Safe dev infra changed, but dev_infra_apply result was ${DEV_INFRA_APPLY_RESULT}."
    blocked="true"
  fi

  if [ -n "$UNMAPPED_HIGH_RISK_PATHS" ]; then
    error "Unmapped high-risk infra paths are present."
    blocked="true"
  fi

  if [ -n "$CRITICAL_MANUAL_ONLY_PATHS" ]; then
    error "Critical/manual-only infra changed. App deploy is blocked until manual infra operation is completed."
    blocked="true"
  fi

  if [ -n "$HIGH_RISK_LAYERS" ]; then
    if [ "$HIGH_RISK_PLAN_RESULT" != "success" ]; then
      error "High-risk managed infra changed, but plan result was ${HIGH_RISK_PLAN_RESULT}."
      blocked="true"
    fi

    if [ -z "$CRITICAL_MANUAL_ONLY_PATHS" ] && [ -z "$UNMAPPED_HIGH_RISK_PATHS" ] && [ "$HIGH_RISK_APPLY_RESULT" != "success" ]; then
      error "High-risk managed infra changed, but apply result was ${HIGH_RISK_APPLY_RESULT}."
      blocked="true"
    fi
  fi

  if [ "$blocked" = "true" ]; then
    {
      echo
      echo "Status: blocked. Demo API deploy will not run."
      echo
      write_blocking_paths "Blocking critical/manual-only paths" "$CRITICAL_MANUAL_ONLY_PATHS"
      if [ -n "$CRITICAL_MANUAL_ONLY_PATHS" ] && [ -n "$UNMAPPED_HIGH_RISK_PATHS" ]; then
        echo
      fi
      write_blocking_paths "Blocking unmapped high-risk paths" "$UNMAPPED_HIGH_RISK_PATHS"
    } >> "$GITHUB_STEP_SUMMARY"
    exit 1
  fi

  {
    echo
    echo "Status: infra job dependencies are ready. Validating Demo API resources next."
  } >> "$GITHUB_STEP_SUMMARY"
}

main "$@"
