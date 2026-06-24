#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCRIPT="${ROOT_DIR}/.github/scripts/cd/resolve-terragrunt-layers.sh"
FIXTURE_DIR="${ROOT_DIR}/.github/scripts/cd/tests/fixtures/resolve-layers"

failures=0

write_newline_file() {
  local value="$1"
  local file="$2"

  : > "$file"
  if [ -n "$value" ]; then
    printf '%s\n' "$value" > "$file"
  fi
}

write_json_file() {
  local value="$1"
  local file="$2"

  if [ -z "$value" ]; then
    printf '[]\n' > "$file"
    return 0
  fi

  jq -Rn --arg input "$value" '$input | split("\n") | map(select(length > 0))' > "$file"
}

write_input_file() {
  local value="$1"
  local file="$2"
  local format="$3"

  case "$format" in
    json) write_json_file "$value" "$file" ;;
    newline) write_newline_file "$value" "$file" ;;
    *)
      echo "Unsupported INPUT_FORMAT=${format}"
      return 1
      ;;
  esac
}

assert_file_equals() {
  local expected="$1"
  local file="$2"
  local label="$3"

  local expected_file
  expected_file="$(mktemp)"
  write_newline_file "$expected" "$expected_file"

  if ! diff -u "$expected_file" "$file" >/dev/null; then
    echo "not ok - ${label}"
    echo "--- expected"
    sed 's/^/  /' "$expected_file"
    echo "--- actual"
    sed 's/^/  /' "$file"
    rm -f "$expected_file"
    return 1
  fi

  rm -f "$expected_file"
}

run_fixture() {
  local fixture="$1"
  local name
  local tmpdir

  name="$(basename "$fixture" .env)"
  tmpdir="$(mktemp -d)"

  (
    set -a
    # shellcheck source=/dev/null
    . "$fixture"
    set +a

    write_input_file "$SAFE_PATHS" "${tmpdir}/safe-paths.txt" "$INPUT_FORMAT"
    write_input_file "$HIGH_RISK_PATHS" "${tmpdir}/high-risk-paths.txt" "$INPUT_FORMAT"
    write_input_file "$INFRA_PATHS" "${tmpdir}/infra-paths.txt" "$INPUT_FORMAT"

    "$SCRIPT" \
      --target-env dev \
      --safe-paths-file "${tmpdir}/safe-paths.txt" \
      --high-risk-paths-file "${tmpdir}/high-risk-paths.txt" \
      --infra-paths-file "${tmpdir}/infra-paths.txt" \
      --output-dir "${tmpdir}/out"

    assert_file_equals "$EXPECTED_SAFE_LAYERS" "${tmpdir}/out/safe-layers.txt" "${name} safe layers"
    assert_file_equals "$EXPECTED_HIGH_RISK_LAYERS" "${tmpdir}/out/high-risk-layers.txt" "${name} high-risk layers"
    assert_file_equals "$EXPECTED_CRITICAL_LAYERS" "${tmpdir}/out/critical-manual-only-layers.txt" "${name} critical layers"
    assert_file_equals "$EXPECTED_CRITICAL_PATHS" "${tmpdir}/out/critical-manual-only-paths.txt" "${name} critical paths"
    assert_file_equals "$EXPECTED_UNMAPPED_PATHS" "${tmpdir}/out/unmapped-high-risk-paths.txt" "${name} unmapped paths"
    assert_file_equals "$EXPECTED_CHANGED_HIGH_RISK_PATHS" "${tmpdir}/out/changed-high-risk-paths.txt" "${name} changed high-risk paths"
  ) || failures=$((failures + 1))

  rm -rf "$tmpdir"
}

main() {
  local fixture

  [ -x "$SCRIPT" ] || {
    echo "Script is not executable: $SCRIPT"
    exit 1
  }

  if find "$FIXTURE_DIR" -name '*.env' -print -quit | grep -q .; then
    :
  else
    echo "No resolve layer fixtures found."
    exit 1
  fi

  for fixture in "$FIXTURE_DIR"/*.env; do
    run_fixture "$fixture"
  done

  if [ "$failures" -ne 0 ]; then
    echo "${failures} resolve layer fixture(s) failed."
    exit 1
  fi

  echo "resolve-terragrunt-layers fixtures passed."
}

main "$@"
