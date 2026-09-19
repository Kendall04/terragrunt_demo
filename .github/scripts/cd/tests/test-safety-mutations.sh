#!/usr/bin/env bash
set -euo pipefail
# Local evidence only: corrupt disposable copies, never the repository fixtures.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
passed=0
copy_case() {
  case_dir="$scratch/$1"
  mkdir -p "$case_dir"
  cp -a "$ROOT/.github" "$case_dir/"
}
expect_failure() {
  local script="$1" diagnostic="$2" status=0
  bash "$case_dir/.github/scripts/cd/tests/$script" > "$scratch/log" 2>&1 || status=$?
  if [[ $status == 0 ]] || ! grep -Fq "$diagnostic" "$scratch/log"; then
    echo "FAIL mutation $(basename "$case_dir"): exit=$status expected diagnostic=$diagnostic"
    cat "$scratch/log"
    exit 1
  fi
  passed=$((passed + 1))
  echo "ok mutation $(basename "$case_dir") (exit=$status; $diagnostic)"
}
for variable in EXPECTED_SAFE_LAYERS EXPECTED_CRITICAL_LAYERS EXPECTED_CHANGED_HIGH_RISK_PATHS; do
  copy_case "$variable"
  printf '\n%s=deliberately-wrong\n' "$variable" >> "$case_dir/.github/scripts/cd/tests/fixtures/resolve-layers/app-only.env"
  expect_failure test-resolve-terragrunt-layers.sh 'not ok - app-only'
done
copy_case scope-canonical
golden="$case_dir/.github/scripts/cd/tests/fixtures/detect-scope/golden-outputs.json"
jq '.scenarios[0].expected_outputs.app_changed = "deliberately-wrong"' "$golden" > "$scratch/golden"
cp "$scratch/golden" "$golden"
expect_failure test-detect-scope.sh 'canonical outputs mismatch'

copy_case scope-output-name
sed -i 's/echo "target_env=${TARGET_ENV}"/echo "removed_target_env=${TARGET_ENV}"/' "$case_dir/.github/scripts/cd/detect-scope.sh"
expect_failure test-detect-scope.sh 'missing scalar output: target_env'

copy_case gate-exit
printf '\nEXPECTED_EXIT=1\n' >> "$case_dir/.github/scripts/cd/tests/fixtures/infra-gate/app-only.env"
expect_failure test-validate-infra-gate.sh 'expected exit 1, got 0'

copy_case selector-policy
# Broaden only the implementation policy. Independent history-test expectations
# must reject it before it could exempt the main fixture suite.
sed -i 's@README.md|terraform/docs/\*.md@*|terraform/docs/*.md@' "$case_dir/.github/scripts/cd/select-safety-tests.sh"
expect_failure test-select-safety-tests.sh 'FAIL relevant: .github/scripts/cd/detect-scope.sh'
echo "$passed controlled mutation checks passed."
