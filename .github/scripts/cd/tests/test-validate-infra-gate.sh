#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="${ROOT_DIR}/.github/scripts/cd/validate-infra-gate.sh"
FIXTURE_DIR="${ROOT_DIR}/.github/scripts/cd/tests/fixtures/infra-gate"

failures=0

run_fixture() {
  local fixture="$1"
  local name
  local summary
  local stdout_file
  local stderr_file
  local status

  name="$(basename "$fixture" .env)"
  summary="$(mktemp)"
  stdout_file="$(mktemp)"
  stderr_file="$(mktemp)"

  (
    set -a
    # shellcheck source=/dev/null
    . "$fixture"
    set +a
    export GITHUB_STEP_SUMMARY="$summary"

    set +e
    "$SCRIPT" >"$stdout_file" 2>"$stderr_file"
    status=$?
    set -e

    if [ "$status" -ne "$EXPECTED_EXIT" ]; then
      echo "not ok - ${name}: expected exit ${EXPECTED_EXIT}, got ${status}"
      echo "--- stderr"
      sed 's/^/  /' "$stderr_file"
      exit 1
    fi

    case "$EXPECTED_EXIT" in
      0)
        if ! grep -Fq "Status: infra job dependencies are ready." "$summary"; then
          echo "not ok - ${name}: success summary missing ready status"
          exit 1
        fi
        ;;
      1)
        if ! grep -Fq "Status: blocked. Demo API deploy will not run." "$summary"; then
          echo "not ok - ${name}: blocked summary missing blocked status"
          exit 1
        fi
        ;;
      *)
        echo "not ok - ${name}: unsupported EXPECTED_EXIT=${EXPECTED_EXIT}"
        exit 1
        ;;
    esac
  ) || failures=$((failures + 1))

  rm -f "$summary" "$stdout_file" "$stderr_file"
}

main() {
  local fixture

  [ -x "$SCRIPT" ] || {
    echo "Script is not executable: $SCRIPT"
    exit 1
  }

  for fixture in "$FIXTURE_DIR"/*.env; do
    run_fixture "$fixture"
  done

  if [ "$failures" -ne 0 ]; then
    echo "${failures} infra gate fixture(s) failed."
    exit 1
  fi

  echo "validate-infra-gate fixtures passed."
}

main "$@"
