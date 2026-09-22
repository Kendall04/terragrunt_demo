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
  local replicas=2
  [ "$SCENARIO" != later_describe_stream ] || replicas=101
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
      --desired-count "$replicas" --attempt-start-epoch 1000 --deadline-epoch "$deadline" \
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
  if [ "$scenario" = later_describe_stream ]; then
    [ "$(<"$CASE_DIR/tasks")" = 2 ] || fail "$scenario did not reject the second DescribeTasks batch"
    ! grep -q '^elbv2 describe-target-health ' "$CASE_DIR/aws-log" || fail "$scenario aggregated malformed batch evidence"
  elif [ "$scenario" = final_describe_failures_scalar ] || [ "$scenario" = final_describe_stream ]; then
    [ "$(<"$CASE_DIR/tasks")" = 3 ] || fail "$scenario did not reach the final DescribeTasks observation"
    [ "$(<"$CASE_DIR/service")" = 5 ] || fail "$scenario continued after the malformed final DescribeTasks response"
  elif [[ "$scenario" == nested_final_* ]]; then
    [ "$(<"$CASE_DIR/tasks")" = 3 ] || fail "$scenario did not reach final task revalidation"
    [ "$(<"$CASE_DIR/service")" = 5 ] || fail "$scenario continued after malformed final evidence"
  elif [[ "$scenario" == final_* ]]; then
    [ "$(<"$CASE_DIR/service")" = 6 ] || fail "$scenario did not reach the final service revalidation"
  elif [[ "$scenario" == boundary_*_final_* ]]; then
    local counter="${scenario#boundary_}"
    counter="${counter%%_*}"
    [ "$(<"$CASE_DIR/$counter")" = 6 ] || fail "$scenario did not reach the last final routing/service read"
    if [ "$counter" != service ]; then
      [ "$(<"$CASE_DIR/service")" = 5 ] || fail "$scenario continued after malformed final routing"
    fi
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
  # shellcheck disable=SC2317 # Deliberately exported for attempted indirect invocation by the child Bash process.
  aws() { printf function >>"$HOSTILE_SENTINEL"; return 96; }
  export -f aws
  HOME="$hostile_home" PATH="$hostile_bin:/usr/bin:/bin" BASH_ENV="$hook" ENV="$hook" \
    AWS_ACCESS_KEY_ID=hostile AWS_SECRET_ACCESS_KEY=hostile AWS_PROFILE=hostile run_gate_process >/dev/null
  unset -f aws
  [ ! -e "$sentinel" ] || fail 'hostile inherited shell environment escaped the hermetic boundary'
  grep -q '^ecs describe-task-definition ' "$CASE_DIR/aws-log" || fail 'pinned fake AWS was not used'
  printf '[PASS] hostile inherited environment cannot escape to external AWS\n'
}

run_routing_detection() {
  local scenario="$1" expected="$2" driver output status=0
  setup_case "$scenario"
  driver="$CASE_DIR/detect.sh"
  cat >"$driver" <<EOF
#!/bin/bash
set -euo pipefail
source "$DEPLOY"
ALB_LISTENER_ARN=listener; ALB_CANDIDATE_RULE_ARN=rule
TG_BLUE_ARN=tg-active; TG_GREEN_ARN=tg-candidate
ECS_SERVICE_BLUE=svc-blue; ECS_SERVICE_GREEN=svc-green
AWS_ARGS=(--cli-connect-timeout 5 --cli-read-timeout 10)
detect_blue_green_state
[ "\$ACTIVE_COLOR" = blue ] && [ "\$INACTIVE_COLOR" = green ]
EOF
  output="$(/usr/bin/env -i HOME="${HOME:-/tmp}" PATH="$FAKE_BIN:/usr/bin:/bin" BASH_ENV= ENV= \
    CASE_DIR="$CASE_DIR" SCENARIO="$SCENARIO" TEST_IMAGE="$IMAGE" TEST_TASK_DEFINITION="$TASK_DEFINITION" \
    /bin/bash --noprofile --norc "$driver" 2>&1)" || status=$?
  if [ "$expected" = pass ]; then
    [ "$status" -eq 0 ] || fail "routing detection $scenario failed: $output"
  else
    [ "$status" -ne 0 ] || fail "routing detection $scenario accepted ambiguity"
    grep -Fq ambiguous <<<"$output" || fail "routing diagnostic missing: $output"
  fi
  printf '[PASS] deploy routing detection: %s\n' "$scenario"
}

run_promotion_integration() {
  local scenario="$1" expected="$2" active="$3" inactive="$4" driver output status=0 gate_line switch_line
  local replicas=2
  [ "$scenario" != later_describe_stream ] || replicas=101
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
NEW_TASK_DEFINITION_ARN="$TASK_DEFINITION"; IMAGE_URI="$IMAGE"; DESIRED_COUNT=$replicas
TARGET_HEALTH_MAX_WAIT_SECONDS=300; TARGET_HEALTH_POLL_INTERVAL_SECONDS=1; READINESS_STABLE_OBSERVATIONS=2
AWS_ARGS=(--region us-east-1 --cli-connect-timeout 5 --cli-read-timeout 10)
# Include initial routing discovery for initial boundary failures; final-stage
# cases start at promotion so the sixth read remains the final routing bracket.
if [[ "\$SCENARIO" == boundary_listener_* || "\$SCENARIO" == boundary_rule_* ]] &&
   [[ "\$SCENARIO" != *_final_* ]]; then
  TG_BLUE_ARN=tg-active; TG_GREEN_ARN=tg-candidate
  ECS_SERVICE_BLUE=svc-blue; ECS_SERVICE_GREEN=svc-green
  detect_blue_green_state
fi
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
    ! grep -q '^elbv2 modify-rule ' "$CASE_DIR/aws-log" || fail 'rule mutated after real gate failure'
    if [[ "$scenario" == nested_final_* ]]; then
      [ "$(<"$CASE_DIR/tasks")" = 3 ] || fail 'promotion fixture did not reach final task revalidation'
      grep -Fq 'nested task evidence is malformed' <<<"$output" || fail 'wrong final-evidence failure'
    elif [[ "$scenario" == definition_* ]]; then
      grep -Fq 'Registered task definition does not match' <<<"$output" || fail 'wrong definition failure'
      ! grep -q '^ecs describe-tasks ' "$CASE_DIR/aws-log" || fail 'invalid definition allowed probe interpretation'
    fi
  fi
  printf '[PASS] real gate to promotion: %s\n' "$scenario"
}

command -v jq >/dev/null || fail 'jq is required'
# Correction regressions run before every previous group, including focused runs.
for shape in attachments_object attachments_null attachments_scalar attachment_null \
  attachment_scalar attachment_type attachment_status details_object details_null \
  details_scalar detail_null detail_scalar detail_name detail_value containers_object \
  containers_null containers_scalar container_null container_name runtime_null \
  digest_false exit_string network_object network_null network_scalar network_entry_null network_ip; do
  for stage in startup complete final; do
    run_case "nested_${stage}_${shape}" fail 'nested task evidence is malformed'
  done
  run_promotion_integration "nested_final_${shape}" fail blue green
done
for shape in entrypoint entrypoint_null command essential image app_entrypoint app_command \
  app_restart probe_restart restart_false restart_null restart_array restart_string \
  restart_missing_enabled restart_enabled_string restart_codes restart_period \
  environment_files environment_files_null mount volumes directory user health dependency app_dependency; do
  run_case "definition_${shape}" fail 'Registered task definition does not match'
  run_promotion_integration "definition_${shape}" fail blue green
done
run_case definition_restart_disabled pass
run_case definition_empty_defaults pass
run_case lifecycle_absent_collections pass
run_case lifecycle_no_containers pass
run_promotion_integration ready pass blue green
if [ "${1:-}" = --validation-fixes-only ]; then
  printf 'All nested evidence and registered execution correction tests passed.\n'
  exit 0
fi
# Exercise captured-response boundaries first, including the actual switch path.
for endpoint in listener rule; do
  for shape in prefix suffix unsupported empty array; do
    scenario="boundary_${endpoint}_${shape}"
    run_case "$scenario" fail 'response envelope is malformed'
    run_routing_detection "$scenario" fail
    run_promotion_integration "$scenario" fail blue green
  done
  for shape in prefix suffix unsupported; do
    scenario="boundary_${endpoint}_final_${shape}"
    run_case "$scenario" fail 'response envelope is malformed'
    run_promotion_integration "$scenario" fail blue green
  done
done
for scenario in boundary_definition_prefix boundary_definition_suffix \
  boundary_service_prefix boundary_service_final_prefix boundary_list_prefix \
  boundary_target_prefix boundary_target_object_entries; do
  run_case "$scenario" fail 'response envelope is malformed'
  run_promotion_integration "$scenario" fail blue green
done
run_case ready pass
run_routing_detection route_default pass
run_promotion_integration ready pass blue green
if [ "${1:-}" = --response-boundaries-only ]; then
  printf 'All authorization response boundary tests passed.\n'
  exit 0
fi
# Keep new boundary counterexamples first, before the existing regression suite.
run_case describe_stream_prefix fail 'batch response envelope is malformed'
run_case describe_stream_object fail 'batch response envelope is malformed'
run_case describe_stream_suffix fail 'batch response envelope is malformed'
run_case describe_stream_scalar fail 'batch response envelope is malformed'
run_case describe_empty fail 'batch response envelope is malformed'
run_case later_describe_stream fail 'batch response envelope is malformed'
run_case final_describe_stream fail 'batch response envelope is malformed'
for stream_scenario in describe_stream_prefix describe_stream_object describe_stream_suffix describe_stream_scalar describe_empty later_describe_stream final_describe_stream; do
  run_promotion_integration "$stream_scenario" fail blue green
done
run_case describe_valid_envelope pass
run_case describe_top_scalar fail 'batch response envelope is malformed'
run_case describe_top_array fail 'batch response envelope is malformed'
run_case describe_failures_scalar fail 'batch response envelope is malformed'
run_case describe_failures_object fail 'batch response envelope is malformed'
run_case describe_failures_null fail 'batch response envelope is malformed'
run_case describe_failures_missing fail 'batch response envelope is malformed'
run_case describe_failure_entry_scalar fail 'batch response envelope is malformed'
run_case describe_tasks_object fail 'batch response envelope is malformed'
run_case describe_tasks_scalar fail 'batch response envelope is malformed'
run_case describe_tasks_null fail 'batch response envelope is malformed'
run_case describe_tasks_missing fail 'batch response envelope is malformed'
run_case describe_task_entry_scalar fail 'batch response envelope is malformed'
run_case describe_embedded_failure fail 'embedded failures'
run_case final_describe_failures_scalar fail 'batch response envelope is malformed'
run_case ready pass
run_case lifecycle_success pass
run_case lifecycle_no_containers pass
run_case lifecycle_mixed pass
run_case lifecycle_identity fail 'contradicted an earlier startup observation'
run_case lifecycle_metadata_regression fail 'contradicted an earlier startup observation'
run_case lifecycle_container_regression fail 'lifecycle regressed'
run_case lifecycle_replacement fail 'previously observed candidate task disappeared'
run_case lifecycle_regression fail 'lifecycle regressed'
run_case missing_completed_metadata fail 'Completed probe lacks required'
run_case network_contradiction fail 'task, container, image, network'
run_case deployment_change fail 'service/deployment identity contradicted'
run_case service_failures fail 'deployment set'
run_case extra_services fail 'deployment set'
run_case final_failures fail 'deployment set'
run_case final_extra fail 'deployment set'
run_case final_malformed fail 'response envelope is malformed'
run_case running_regression fail 'running count regressed'
run_case probe_regression fail 'lifecycle regressed'
run_case route_config pass
run_case route_default pass
run_case route_dual pass
run_case route_conflict fail 'ambiguous'
run_case route_zero fail 'ambiguous'
run_case route_malformed fail 'ambiguous'
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
run_routing_detection ready pass
run_routing_detection route_config pass
run_routing_detection route_dual pass
run_routing_detection route_conflict fail
run_routing_detection ambiguous fail
hard_started=$SECONDS
run_case resistant_call fail 'forced process-group termination' 1004
run_case orphan_call fail 'forced process-group termination' 1004
run_case hung_call fail 'AWS observation failed' 1004
[ $((SECONDS - hard_started)) -le 10 ] || fail 'external calls exceeded the total bounded tolerance'
run_batching_case
run_invalid_timing_case
run_hostile_environment_case
run_promotion_integration ready pass blue green
run_promotion_integration ready pass green blue
run_promotion_integration unready fail blue green
run_promotion_integration describe_failures_scalar fail blue green
run_promotion_integration final_describe_failures_scalar fail blue green
printf 'All readiness gate tests passed.\n'
