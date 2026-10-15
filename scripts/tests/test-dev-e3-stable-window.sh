#!/usr/bin/env bash
set -euo pipefail
# Exercise the real extracted DEV run_gate loop. AWS observers are replaced by
# deterministic complete/incomplete fingerprints; no CLI, jq or network call.
gate="${1:?exact extracted DEV readiness gate required}"
run_case() (
  local scenario="$1" expected="$2" output status=0
  set +e
  output="$( (
    set -euo pipefail
    source "$gate"
    ticks=0; reads=0; STABLE_OBSERVATIONS=2
    validate_registered_definition() { :; }
    check_deadline() { ticks=$((ticks + 1)); [ "$ticks" -le 8 ] || die 'TEST original deadline expired'; }
    sleep_until_next_poll() { :; }
    observe_once() {
      reads=$((reads + 1)); OBSERVATION_STATUS=complete
      case "$scenario" in
        settle) if [ "$reads" -eq 1 ]; then OBSERVATION_FINGERPRINT=A; else OBSERVATION_FINGERPRINT=B; fi ;;
        incomplete) OBSERVATION_FINGERPRINT=B; [ "$reads" -ne 1 ] || OBSERVATION_STATUS=incomplete ;;
        flapping) OBSERVATION_FINGERPRINT="$((reads % 2))" ;;
        final-change) if [ "$reads" -lt 3 ]; then OBSERVATION_FINGERPRINT=A; else OBSERVATION_FINGERPRINT=B; fi ;;
        identity-rejected) die 'TEST frozen identity rejected' ;;
        read-error) die 'TEST AWS read failed' ;;
      esac
    }
    run_gate
    [ "$reads" -eq 4 ] || die 'TEST premature success'
    printf 'TEST_REAL_DEV_LOOP_SUCCESS\n'
  ) 2>&1)"
  status=$?
  set -e
  if [ "$expected" = success ]; then
    [ "$status" -eq 0 ] && [[ "$output" == *TEST_REAL_DEV_LOOP_SUCCESS* ]] || { printf '%s\n' "$output"; exit 1; }
  else
    [ "$status" -ne 0 ] && [[ "$output" == *"$expected"* ]] || { printf '%s\n' "$output"; exit 1; }
  fi
  printf 'DEV_E3_%s_PASS\n' "$scenario"
)
run_case settle success
run_case incomplete success
run_case flapping 'TEST original deadline expired'
run_case final-change 'Final readiness identity changed before traffic switching.'
run_case identity-rejected 'TEST frozen identity rejected'
run_case read-error 'TEST AWS read failed'
