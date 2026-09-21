#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GATE="$ROOT_DIR/scripts/ecs-readiness-gate.sh"
DEPLOY="$ROOT_DIR/scripts/ecs-blue-green-deploy.sh"
FAKE_AWS="$ROOT_DIR/scripts/tests/fake-readiness-aws"
IMAGE=123456789012.dkr.ecr.us-east-1.amazonaws.com/demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
TASK_DEFINITION=arn:aws:ecs:us-east-1:123456789012:task-definition/demo:42
TMP_ROOT="$(mktemp -d)"

cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT
fail() { printf '[TEST ERROR] %s\n' "$*" >&2; exit 1; }

setup_case() {
  local scenario="$1"
  CASE_DIR="$TMP_ROOT/$scenario"
  FAKE_BIN="$CASE_DIR/bin"
  mkdir -p "$FAKE_BIN"
  printf '999' >"$CASE_DIR/time"
  : >"$CASE_DIR/aws-log"
  cat >"$FAKE_BIN/aws" <<EOF
#!/bin/bash
exec /bin/bash --noprofile --norc "$FAKE_AWS" "\$@"
EOF
  cat >"$FAKE_BIN/date" <<'EOF'
#!/bin/bash
if [ "${1:-}" = +%s ]; then
  value="$(<"$CASE_DIR/time")"
  value=$((value + 1))
  printf '%s' "$value" >"$CASE_DIR/time"
  printf '%s\n' "$value"
else
  exec /bin/date "$@"
fi
EOF
  cat >"$FAKE_BIN/sleep" <<'EOF'
#!/bin/bash
exit 0
EOF
  chmod +x "$FAKE_BIN/aws" "$FAKE_BIN/date" "$FAKE_BIN/sleep"
  export CASE_DIR SCENARIO="$scenario" TEST_IMAGE="$IMAGE" TEST_TASK_DEFINITION="$TASK_DEFINITION"
}

run_gate_process() {
  local deadline="${1:-1300}"
  /usr/bin/env -i HOME="${HOME:-/tmp}" PATH="$FAKE_BIN:/usr/bin:/bin" BASH_ENV= ENV= \
    CASE_DIR="$CASE_DIR" SCENARIO="$SCENARIO" TEST_IMAGE="$IMAGE" TEST_TASK_DEFINITION="$TASK_DEFINITION" \
    AWS_ACCESS_KEY_ID= AWS_SECRET_ACCESS_KEY= AWS_SESSION_TOKEN= AWS_PROFILE= AWS_DEFAULT_PROFILE= \
    AWS_WEB_IDENTITY_TOKEN_FILE= AWS_ROLE_ARN= AWS_ROLE_SESSION_NAME= \
    AWS_CONTAINER_CREDENTIALS_RELATIVE_URI= AWS_CONTAINER_CREDENTIALS_FULL_URI= AWS_CONTAINER_AUTHORIZATION_TOKEN= \
    AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true \
    /bin/bash --noprofile --norc "$GATE" \
      --region us-east-1 --cluster cluster --service svc \
      --task-definition-arn "$TASK_DEFINITION" --image-uri "$IMAGE" \
      --app-container app --probe-container app-readiness-probe \
      --target-group-arn tg-candidate --listener-arn listener \
      --candidate-rule-arn rule --active-target-group-arn tg-active \
      --desired-count 2 --attempt-start-epoch 1000 --deadline-epoch "$deadline" \
      --poll-interval 1 --stable-observations 2
}

run_case() {
  local scenario="$1" expected="$2" pattern="${3:-}" deadline="${4:-1300}" output status=0
  setup_case "$scenario"
  set +e
  output="$(run_gate_process "$deadline" 2>&1)"
  status=$?
  set -e
  if [ "$expected" = pass ]; then
    [ "$status" -eq 0 ] || fail "$scenario unexpectedly failed: $output"
  else
    [ "$status" -ne 0 ] || fail "$scenario unexpectedly passed"
    grep -Fq "$pattern" <<<"$output" || fail "$scenario missing diagnostic '$pattern': $output"
  fi
  printf '[PASS] gate scenario: %s\n' "$scenario"
}

run_invalid_timing_case() {
  setup_case invalid_timing
  local output status=0
  set +e
  output="$(run_gate_process 3000 2>&1)"; status=$?
  set -e
  [ "$status" -ne 0 ] || fail 'invalid readiness budget passed'
  grep -Fq 'cannot exceed 1800 seconds' <<<"$output" || fail "missing invalid-budget diagnostic: $output"
  printf '[PASS] invalid readiness timing fails closed\n'
}

run_batching_case() {
  local driver="$TMP_ROOT/batching.sh" calls="$TMP_ROOT/batching-calls"
  cat >"$driver" <<EOF
#!/bin/bash
set -euo pipefail
source "$GATE"
ECS_CLUSTER=cluster
aws_capture() {
  local destination="\$1"; shift
  local seen=false argument result
  local -a tasks=()
  for argument in "\$@"; do
    if [ "\$argument" = --tasks ]; then seen=true; continue; fi
    if [ "\$seen" = true ]; then [[ "\$argument" == --* ]] && break; tasks+=("\$argument"); fi
  done
  printf x >>"$calls"
  result="\$(printf '%s\n' "\${tasks[@]}" | jq -Rsc 'split("\\n") | map(select(length > 0) | {taskArn:.}) | {tasks:.,failures:[]}')"
  printf -v "\$destination" '%s' "\$result"
}
task_arns=()
for number in \$(seq 1 205); do task_arns+=("task/\$number"); done
describe_tasks_batched combined "\${task_arns[@]}"
[ "\$(jq -r '.tasks | length' <<<"\$combined")" = 205 ]
EOF
  /bin/bash --noprofile --norc "$driver"
  [ "$(wc -c <"$calls" | tr -d ' ')" = 3 ] || fail 'DescribeTasks batching did not use 100-item batches'
  printf '[PASS] DescribeTasks batching preserves output assignment and all replicas\n'
}

run_hostile_environment_case() {
  setup_case hostile_environment
  local hook="$CASE_DIR/hostile-hook" sentinel="$CASE_DIR/escape" hostile_bin="$CASE_DIR/hostile-bin" hostile_home="$CASE_DIR/hostile-home"
  mkdir -p "$hostile_bin" "$hostile_home/.aws"
  printf 'printf hook >>"%s"\naws() { printf function >>"%s"; exit 96; }\nexport -f aws\n' "$sentinel" "$sentinel" >"$hook"
  printf '[default]\naws_access_key_id=hostile\naws_secret_access_key=hostile\n' >"$hostile_home/.aws/credentials"
  cat >"$hostile_bin/aws" <<EOF
#!/bin/bash
printf executable >>"$sentinel"
exit 95
EOF
  chmod +x "$hostile_bin/aws"
  HOSTILE_SENTINEL="$sentinel"
  export HOSTILE_SENTINEL
  aws() { printf function >>"$HOSTILE_SENTINEL"; return 96; }
  export -f aws
  HOME="$hostile_home" PATH="$hostile_bin:/usr/bin:/bin" BASH_ENV="$hook" ENV="$hook" \
    AWS_ACCESS_KEY_ID=hostile AWS_SECRET_ACCESS_KEY=hostile AWS_PROFILE=hostile run_gate_process >/dev/null
  unset -f aws
  [ ! -e "$sentinel" ] || fail 'hostile inherited shell environment escaped the hermetic boundary'
  grep -q '^ecs describe-task-definition ' "$CASE_DIR/aws-log" || fail 'pinned fake AWS was not used'
  printf '[PASS] hostile inherited environment cannot escape to external AWS\n'
}

run_promotion_integration() {
  local scenario="$1" expected="$2" active="$3" inactive="$4" driver output status=0 gate_line switch_line
  setup_case "promotion-$scenario-$active-$inactive"
  SCENARIO="$scenario"; export SCENARIO
  driver="$CASE_DIR/driver.sh"
  cat >"$driver" <<EOF
#!/bin/bash
set -euo pipefail
source "$DEPLOY"
ENV_NAME=dev; AWS_REGION_NAME=us-east-1; USE_INSTANCE_ROLE=true; ECS_CLUSTER=cluster
INACTIVE_SERVICE=svc-$inactive; INACTIVE_COLOR=$inactive; ACTIVE_COLOR=$active; ACTIVE_SERVICE=svc-$active
ACTIVE_TG=tg-active; INACTIVE_TG=tg-candidate; ALB_LISTENER_ARN=listener; ALB_CANDIDATE_RULE_ARN=rule
NEW_TASK_DEFINITION_ARN="$TASK_DEFINITION"; IMAGE_URI="$IMAGE"; DESIRED_COUNT=2
TARGET_HEALTH_MAX_WAIT_SECONDS=300; TARGET_HEALTH_POLL_INTERVAL_SECONDS=1; READINESS_STABLE_OBSERVATIONS=2
AWS_ARGS=(--region us-east-1 --cli-connect-timeout 5 --cli-read-timeout 10)
promote_inactive_color
EOF
  set +e
  output="$(/usr/bin/env -i HOME="${HOME:-/tmp}" PATH="$FAKE_BIN:/usr/bin:/bin" BASH_ENV= ENV= \
    CASE_DIR="$CASE_DIR" SCENARIO="$SCENARIO" TEST_IMAGE="$IMAGE" TEST_TASK_DEFINITION="$TASK_DEFINITION" \
    EXPECTED_SERVICE="svc-$inactive" APP_NAME="demo-dev-app-api-$inactive" PROBE_NAME="demo-dev-app-api-$inactive-readiness-probe" \
    AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true \
    /bin/bash --noprofile --norc "$driver" 2>&1)"; status=$?
  set -e
  if [ "$expected" = pass ]; then
    [ "$status" -eq 0 ] || fail "real-gate promotion failed: $output"
    gate_line="$(grep -n '^elbv2 describe-target-health ' "$CASE_DIR/aws-log" | tail -1 | cut -d: -f1)"
    switch_line="$(grep -n '^elbv2 modify-listener ' "$CASE_DIR/aws-log" | cut -d: -f1)"
    [ "$gate_line" -lt "$switch_line" ] || fail 'listener mutation did not follow real gate completion'
  else
    [ "$status" -ne 0 ] || fail 'unready real-gate promotion passed'
    ! grep -q '^elbv2 modify-listener ' "$CASE_DIR/aws-log" || fail 'listener mutated after real gate failure'
  fi
  printf '[PASS] real gate to promotion: %s\n' "$scenario"
}

command -v jq >/dev/null || fail 'jq is required'
run_case ready pass
run_case normal_startup pass
run_case transient pass
run_case unready fail 'without an explicit zero exit code'
run_case missing_exit fail 'without an explicit zero exit code'
run_case swapped_describe fail 'did not exactly match the requested cohort'
run_case missing_describe fail 'did not exactly match the requested cohort'
run_case duplicate_describe fail 'did not exactly match the requested cohort'
run_case partial_replacement fail 'previously observed candidate task disappeared'
run_case identity_contradiction fail 'contradicted an earlier startup observation'
run_case version_regression fail 'version regressed'
run_case replacement fail 'previously observed candidate task disappeared'
run_case container_change fail 'contradicted an earlier startup observation'
run_case extra_target fail 'deadline expired' 1060
run_case missing_target fail 'deadline expired' 1060
run_case stale fail 'outside the bounded deployment attempt'
run_case wrong_revision fail 'task, container, image, network'
run_case api_failure fail 'embedded failures'
run_case ambiguous fail 'ambiguous'
run_case mapping_change fail 'mapping changed'
run_case count_change fail 'desired count'
run_case hung_call fail 'AWS observation failed' 1004
run_batching_case
run_invalid_timing_case
run_hostile_environment_case
run_promotion_integration ready pass blue green
run_promotion_integration ready pass green blue
run_promotion_integration unready fail blue green
printf 'All readiness gate tests passed.\n'
