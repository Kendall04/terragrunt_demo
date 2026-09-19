#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

# Execute the workflow's actual Bash, rather than a duplicate implementation.
for block in SUITE RESULT; do
  awk -v block="$block" '
    $0 ~ "# END SAFETY " block { active=0 }
    active { sub(/^          /, ""); print }
    $0 ~ "# BEGIN SAFETY " block { active=1 }
  ' "$ROOT/.github/workflows/ci-cd-safety.yml" > "$scratch/$block.sh"
  [[ -s $scratch/$block.sh ]] || exit 1
  bash -n "$scratch/$block.sh"
done
export GITHUB_OUTPUT="$scratch/output" GITHUB_STEP_SUMMARY="$scratch/summary"
export GITHUB_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export GITHUB_EVENT_NAME=pull_request GITHUB_REF=refs/pull/1/merge
export GITHUB_BASE_REF=main GITHUB_RUN_ID=local GITHUB_RUN_ATTEMPT=1 PR_NUMBER=1
export BASE_SHA=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
export HEAD_SHA=cccccccccccccccccccccccccccccccccccccccc MERGE_BASE=''
export ACTUAL_SHA="$GITHUB_SHA" CANCELLED=false
export DEPENDENCIES=success SELF_TESTS=success SELECTOR=success
export SELECTION=RUN REASON=relevant-path SUITE_OUTCOME=success
export SCOPE_EXIT=0 LAYERS_EXIT=0 GATE_EXIT=0
passed=0
expect_result() {
  local label="$1" expected="$2" status=0
  : > "$GITHUB_STEP_SUMMARY"
  bash "$scratch/RESULT.sh" > "$scratch/log" 2>&1 || status=$?
  [[ $status == "$expected" ]] || { echo "FAIL $label: exit=$status expected=$expected"; cat "$scratch/log"; exit 1; }
  passed=$((passed + 1))
  echo "ok $label (exit=$status)"
}
expect_result passing-execution 0
grep -Fq 'Result: suite passed' "$GITHUB_STEP_SUMMARY"
SELF_TESTS=failure expect_result failed-selector-tests 1
SELF_TESTS=skipped expect_result skipped-selector-tests 1
DEPENDENCIES=failure expect_result failed-dependency-check 1
SELECTOR=failure expect_result crashed-selector 1
SELECTOR=skipped expect_result skipped-selector 1
SELECTION=unknown expect_result invalid-selection 1
SELECTION='' expect_result missing-selection 1
REASON='' expect_result missing-reason 1
ACTUAL_SHA="$BASE_SHA" expect_result identity-mismatch 1
ACTUAL_SHA='' expect_result missing-identity 1
CANCELLED=true expect_result cancelled-run 1
SUITE_OUTCOME=skipped expect_result skipped-relevant-suite 1
SUITE_OUTCOME=failure expect_result failed-suite-process 1
SUITE_OUTCOME=cancelled expect_result cancelled-suite 1
SCOPE_EXIT=1 expect_result failed-scope 1
LAYERS_EXIT=1 expect_result failed-layers 1
GATE_EXIT=1 expect_result failed-gate 1
SCOPE_EXIT='' expect_result missing-scope-execution 1
LAYERS_EXIT='' expect_result missing-layers-execution 1
GATE_EXIT='' expect_result missing-gate-execution 1
GATE_EXIT=garbage expect_result malformed-exit-code 1
SELECTION=EXEMPT expect_result unproven-exemption 1
export SELECTION=EXEMPT REASON=complete-unrelated-diff SUITE_OUTCOME=skipped
export SCOPE_EXIT='' LAYERS_EXIT='' GATE_EXIT=''
expect_result proven-exemption 0
grep -Fq 'Result: suite not required' "$GITHUB_STEP_SUMMARY"
if grep -Fq 'suite passed' "$GITHUB_STEP_SUMMARY"; then exit 1; fi
SELF_TESTS=failure expect_result exemption-cannot-hide-failed-self-tests 1
CANCELLED=true expect_result exemption-cannot-hide-cancellation 1
SUITE_OUTCOME=failure expect_result exemption-cannot-hide-failure 1

# Controlled stand-ins prove the real workflow runner attempts every process,
# propagates failures at every position, and records missing scripts as failure.
mkdir -p "$scratch/.github/scripts/cd/tests"
cd "$scratch"
names=(detect-scope resolve-terragrunt-layers validate-infra-gate)
for failing in none "${names[@]}" missing; do
  for name in "${names[@]}"; do
    code=0
    [[ $name != "$failing" ]] || code=7
    printf '#!/usr/bin/env bash\nexit %s\n' "$code" > ".github/scripts/cd/tests/test-$name.sh"
  done
  if [[ $failing == missing ]]; then rm .github/scripts/cd/tests/test-detect-scope.sh; fi
  : > "$GITHUB_OUTPUT"
  status=0
  bash "$scratch/SUITE.sh" > "$scratch/log" 2>&1 || status=$?
  expected=1
  [[ $failing != none ]] || expected=0
  [[ $status == "$expected" ]] || { cat "$scratch/log"; exit 1; }
  for name in "${names[@]}"; do grep -Eq "^${name}=[0-9]+$" "$GITHUB_OUTPUT"; done
  if [[ $failing != none && $failing != missing ]]; then grep -Fxq "$failing=7" "$GITHUB_OUTPUT"; fi
  passed=$((passed + 1))
  echo "ok suite process failure=$failing (exit=$status; all three attempted)"
done
echo "$passed workflow result/process checks passed."
