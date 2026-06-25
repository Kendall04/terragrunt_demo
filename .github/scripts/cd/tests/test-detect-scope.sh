#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="${ROOT_DIR}/.github/scripts/cd/detect-scope.sh"
GOLDEN="${ROOT_DIR}/.github/scripts/cd/tests/fixtures/detect-scope/golden-outputs.json"

SCALAR_OUTPUTS=(
  target_env
  app_changed
  infra_changed
  safe_dev_infra_changed
  safe_infra_changed
  high_risk_dev_infra_changed
  high_risk_managed_changed
  critical_manual_only_changed
  prod_infra_changed
  infra_workflow_changed
  docs_only
)

MULTILINE_OUTPUTS=(
  safe_layers
  high_risk_layers
  critical_manual_only_layers
  unmapped_high_risk_paths
  changed_app_paths
  changed_infra_paths
  changed_high_risk_paths
  critical_manual_only_paths
  safe_infra_paths
  prod_infra_paths
  infra_workflow_paths
  infra_paths
  high_risk_paths
)

failures=0

scenario_value() {
  local scenario="$1"
  local query="$2"

  jq -r "$query" <<< "$scenario"
}

scenario_json_array() {
  local scenario="$1"
  local query="$2"

  jq -c "$query" <<< "$scenario"
}

assert_github_output_names() {
  local output_file="$1"
  local name

  for name in "${SCALAR_OUTPUTS[@]}"; do
    if ! grep -Eq "^${name}=" "$output_file"; then
      echo "missing scalar output: ${name}"
      return 1
    fi
  done

  for name in "${MULTILINE_OUTPUTS[@]}"; do
    if ! grep -Eq "^${name}<<EOF$" "$output_file"; then
      echo "missing multiline output: ${name}"
      return 1
    fi
  done
}

run_scenario() {
  local index="$1"
  local scenario
  local name
  local tmpdir
  local output_file
  local summary_file

  scenario="$(jq -c ".scenarios[$index]" "$GOLDEN")"
  name="$(scenario_value "$scenario" '.name')"
  tmpdir="$(mktemp -d)"
  output_file="${tmpdir}/github-output.txt"
  summary_file="${tmpdir}/summary.md"

  (
    export RUNNER_TEMP="$tmpdir"
    export GITHUB_OUTPUT="$output_file"
    export GITHUB_STEP_SUMMARY="$summary_file"
    export TARGET_ENV
    export APP_CHANGED
    export INFRA_RAW_CHANGED
    export SAFE_INFRA_CHANGED
    export HIGH_RISK_INFRA_CHANGED
    export PROD_INFRA_CHANGED
    export INFRA_WORKFLOW_CHANGED
    export DOCS_CHANGED
    export APP_PATHS
    export INFRA_PATHS
    export SAFE_INFRA_PATHS
    export HIGH_RISK_PATHS
    export PROD_INFRA_PATHS
    export INFRA_WORKFLOW_PATHS

    TARGET_ENV="$(scenario_value "$scenario" '.target_env')"
    APP_CHANGED="$(scenario_value "$scenario" '.inputs.app_changed')"
    INFRA_RAW_CHANGED="$(scenario_value "$scenario" '.inputs.infra_raw_changed')"
    SAFE_INFRA_CHANGED="$(scenario_value "$scenario" '.inputs.safe_infra_changed')"
    HIGH_RISK_INFRA_CHANGED="$(scenario_value "$scenario" '.inputs.high_risk_infra_changed')"
    PROD_INFRA_CHANGED="$(scenario_value "$scenario" '.inputs.prod_infra_changed')"
    INFRA_WORKFLOW_CHANGED="$(scenario_value "$scenario" '.inputs.infra_workflow_changed')"
    DOCS_CHANGED="$(scenario_value "$scenario" '.inputs.docs_changed')"
    APP_PATHS="$(scenario_json_array "$scenario" '.inputs.app_paths')"
    INFRA_PATHS="$(scenario_json_array "$scenario" '.inputs.infra_paths')"
    SAFE_INFRA_PATHS="$(scenario_json_array "$scenario" '.inputs.safe_infra_paths')"
    HIGH_RISK_PATHS="$(scenario_json_array "$scenario" '.inputs.high_risk_paths')"
    PROD_INFRA_PATHS="$(scenario_json_array "$scenario" '.inputs.prod_infra_paths')"
    INFRA_WORKFLOW_PATHS="$(scenario_json_array "$scenario" '.inputs.infra_workflow_paths')"

    "$SCRIPT"

    jq -e --argjson expected "$(jq '.expected_outputs' <<< "$scenario")" '
      .outputs == $expected
    ' "${tmpdir}/cd-scope.json" >/dev/null || {
      echo "canonical outputs mismatch for ${name}"
      echo "--- expected"
      jq '.expected_outputs' <<< "$scenario"
      echo "--- actual"
      jq '.outputs' "${tmpdir}/cd-scope.json"
      exit 1
    }

    assert_github_output_names "$output_file"

    if ! grep -Fq "## CD scope" "$summary_file"; then
      echo "summary missing CD scope heading for ${name}"
      exit 1
    fi
  ) || failures=$((failures + 1))

  rm -rf "$tmpdir"
}

main() {
  local count
  local index

  [ -x "$SCRIPT" ] || {
    echo "Script is not executable: $SCRIPT"
    exit 1
  }

  jq empty "$GOLDEN"

  count="$(jq '.scenarios | length' "$GOLDEN")"
  for ((index = 0; index < count; index++)); do
    run_scenario "$index"
  done

  if [ "$failures" -ne 0 ]; then
    echo "${failures} detect scope scenario(s) failed."
    exit 1
  fi

  echo "detect-scope golden outputs passed."
}

main "$@"
