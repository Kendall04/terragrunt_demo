#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GATE="$ROOT_DIR/scripts/ecs-readiness-gate.sh"
DEPLOY="$ROOT_DIR/scripts/ecs-blue-green-deploy.sh"
IMAGE="123456789012.dkr.ecr.us-east-1.amazonaws.com/demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TASK_DEFINITION="arn:aws:ecs:us-east-1:123456789012:task-definition/demo:42"
TMP_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

fail() {
  printf '[TEST ERROR] %s\n' "$*" >&2
  exit 1
}

increment_counter() {
  local name="$1"
  local file="$CASE_DIR/$name"
  local value=0
  if [ -f "$file" ]; then
    value="$(<"$file")"
  fi
  value=$((value + 1))
  printf '%s' "$value" >"$file"
  printf '%s' "$value"
}

fake_task_definition() {
  jq -n --arg td "$TASK_DEFINITION" --arg image "$IMAGE" '{
    taskDefinition:{
      taskDefinitionArn:$td,
      networkMode:"awsvpc",
      requiresCompatibilities:["FARGATE"],
      containerDefinitions:[
        {name:"app",image:$image,essential:true,portMappings:[{containerPort:8080,protocol:"tcp"}],environment:[{name:"APP_ENV",value:"dev"}],secrets:[{name:"DB_CONN_STRING",valueFrom:"secret"}]},
        {name:"app-readiness-probe",image:$image,essential:false,command:["readiness-probe"],logConfiguration:{logDriver:"awslogs",options:{}}}
      ]
    }
  }'
}

fake_service() {
  local call desired=2 running=2 pending=0
  call="$(increment_counter service)"
  if [ "$SCENARIO" = "count_change" ] && [ "$call" -ge 5 ]; then
    desired=1
    running=1
  fi
  jq -n --arg td "$TASK_DEFINITION" --argjson desired "$desired" --argjson running "$running" --argjson pending "$pending" '{
    failures:[],services:[{
      serviceArn:"arn:aws:ecs:us-east-1:123456789012:service/cluster/svc",
      serviceName:"svc",status:"ACTIVE",taskDefinition:$td,
      desiredCount:$desired,runningCount:$running,pendingCount:$pending,
      loadBalancers:[{targetGroupArn:"tg-candidate",containerName:"app",containerPort:8080}],
      deployments:[{id:"ecs-svc/1",status:"PRIMARY",taskDefinition:$td,desiredCount:$desired,runningCount:$running,pendingCount:$pending}]
    }]
  }'
}

fake_list_tasks() {
  local call
  call="$(increment_counter list)"
  if [ "$SCENARIO" = "replacement" ] && [ "$call" -ge 3 ]; then
    jq -n '{taskArns:["task/one","task/three"]}'
  else
    jq -n '{taskArns:["task/one","task/two"]}'
  fi
}

fake_task() {
  local arn="$1"
  local call="$2"
  local suffix ip runtime probe_status exit_json created task_definition
  suffix="${arn##*/}"
  case "$suffix" in
    one) ip="10.0.0.1" ;;
    two) ip="10.0.0.2" ;;
    three) ip="10.0.0.3" ;;
    *) fail "Unknown synthetic task $arn" ;;
  esac
  runtime="runtime-$suffix"
  probe_status="STOPPED"
  exit_json=0
  created="1970-01-01T00:16:40Z"
  task_definition="$TASK_DEFINITION"

  case "$SCENARIO" in
    unready) exit_json=23 ;;
    missing_exit) exit_json=null ;;
    stale) created="1970-01-01T00:00:01Z" ;;
    wrong_revision) task_definition="arn:aws:ecs:us-east-1:123456789012:task-definition/demo:41" ;;
    container_change)
      if [ "$call" -ge 3 ] && [ "$suffix" = "two" ]; then runtime="runtime-two-replaced"; fi
      ;;
  esac

  jq -n \
    --arg arn "$arn" --arg td "$task_definition" --arg image "$IMAGE" \
    --arg digest "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    --arg ip "$ip" --arg runtime "$runtime" --arg probe_status "$probe_status" \
    --arg created "$created" --argjson exit_code "$exit_json" '
    {
      taskArn:$arn,taskDefinitionArn:$td,group:"service:svc",startedBy:"ecs-svc/1",
      desiredStatus:"RUNNING",lastStatus:"RUNNING",connectivity:"CONNECTED",version:1,createdAt:$created,
      attachments:[{type:"ElasticNetworkInterface",status:"ATTACHED",details:[{name:"privateIPv4Address",value:$ip}]}],
      containers:[
        {name:"app",containerArn:($arn+"/app"),runtimeId:$runtime,image:$image,imageDigest:$digest,lastStatus:"RUNNING",networkInterfaces:[{privateIpv4Address:$ip}]},
        ({name:"app-readiness-probe",containerArn:($arn+"/probe"),runtimeId:($runtime+"-probe"),image:$image,imageDigest:$digest,lastStatus:$probe_status}
          + if $exit_code == null then {} else {exitCode:$exit_code} end)
      ]
    }'
}

fake_describe_tasks() {
  local call arg collect=false
  local -a arns=() rendered=()
  call="$(increment_counter tasks)"
  shift 2
  for arg in "$@"; do
    if [ "$arg" = "--tasks" ]; then collect=true; continue; fi
    if [ "$collect" = "true" ]; then
      [[ "$arg" == --* ]] && break
      arns+=("$arg")
    fi
  done
  for arg in "${arns[@]}"; do
    rendered+=("$(fake_task "$arg" "$call")")
  done
  if [ "$SCENARIO" = "api_failure" ]; then
    printf '%s\n' "${rendered[@]}" | jq -s '{tasks:.,failures:[{arn:"task/two",reason:"ACCESS_DENIED"}]}'
  else
    printf '%s\n' "${rendered[@]}" | jq -s '{tasks:.,failures:[]}'
  fi
}

fake_route() {
  local kind="$1" target call
  call="$(increment_counter "$kind")"
  if [ "$kind" = "listener" ]; then target="tg-active"; else target="tg-candidate"; fi
  if [ "$SCENARIO" = "mapping_change" ] && [ "$kind" = "listener" ] && [ "$call" -ge 5 ]; then
    target="tg-candidate"
  fi
  if [ "$SCENARIO" = "ambiguous" ] && [ "$kind" = "listener" ]; then
    jq -n '{Listeners:[{DefaultActions:[{Type:"forward",ForwardConfig:{TargetGroups:[{TargetGroupArn:"tg-active",Weight:1},{TargetGroupArn:"tg-other",Weight:1}]}}]}]}'
  elif [ "$kind" = "listener" ]; then
    jq -n --arg target "$target" '{Listeners:[{DefaultActions:[{Type:"forward",TargetGroupArn:$target}]}]}'
  else
    jq -n --arg target "$target" '{Rules:[{Actions:[{Type:"forward",TargetGroupArn:$target}]}]}'
  fi
}

fake_targets() {
  local call
  call="$(increment_counter targets)"
  if [ "$SCENARIO" = "extra_target" ]; then
    jq -n '{TargetHealthDescriptions:[
      {Target:{Id:"10.0.0.1",Port:8080},TargetHealth:{State:"healthy"}},
      {Target:{Id:"10.0.0.2",Port:8080},TargetHealth:{State:"healthy"}},
      {Target:{Id:"10.0.0.99",Port:8080},TargetHealth:{State:"healthy"}}]}'
  elif [ "$SCENARIO" = "missing_target" ]; then
    jq -n '{TargetHealthDescriptions:[{Target:{Id:"10.0.0.1",Port:8080},TargetHealth:{State:"healthy"}}]}'
  elif [ "$SCENARIO" = "replacement" ] && [ "$(<"$CASE_DIR/list")" -ge 3 ]; then
    jq -n '{TargetHealthDescriptions:[
      {Target:{Id:"10.0.0.1",Port:8080},TargetHealth:{State:"healthy"}},
      {Target:{Id:"10.0.0.3",Port:8080},TargetHealth:{State:"healthy"}}]}'
  else
    jq -n '{TargetHealthDescriptions:[
      {Target:{Id:"10.0.0.1",Port:8080},TargetHealth:{State:"healthy"}},
      {Target:{Id:"10.0.0.2",Port:8080},TargetHealth:{State:"healthy"}}]}'
  fi
  : "$call"
}

aws() {
  local argument connect_timeout=false read_timeout=false
  for argument in "$@"; do
    [ "$argument" != "--no-paginate" ] || fail "ListTasks pagination was disabled"
    [ "$argument" != "--cli-connect-timeout" ] || connect_timeout=true
    [ "$argument" != "--cli-read-timeout" ] || read_timeout=true
  done
  [ "$connect_timeout" = "true" ] && [ "$read_timeout" = "true" ] || fail "AWS call omitted socket bounds: $*"
  case "$1 $2" in
    "ecs describe-task-definition") fake_task_definition ;;
    "ecs describe-services") fake_service ;;
    "ecs list-tasks") fake_list_tasks ;;
    "ecs describe-tasks") fake_describe_tasks "$@" ;;
    "elbv2 describe-listeners") fake_route listener ;;
    "elbv2 describe-rules") fake_route rule ;;
    "elbv2 describe-target-health") fake_targets ;;
    *) fail "Unexpected AWS call: $*" ;;
  esac
}

run_invalid_timing_case() {
  local output status=0
  if output="$({
    source "$GATE"
    main \
      --region us-east-1 --cluster cluster --service svc \
      --task-definition-arn "$TASK_DEFINITION" --image-uri "$IMAGE" \
      --app-container app --probe-container app-readiness-probe \
      --target-group-arn tg-candidate --listener-arn listener \
      --candidate-rule-arn rule --active-target-group-arn tg-active \
      --desired-count 2 --attempt-start-epoch 1000 --deadline-epoch 3000
  } 2>&1)"; then
    status=0
  else
    status=$?
  fi
  [ "$status" -ne 0 ] || fail "invalid readiness budget unexpectedly passed"
  grep -Fq "cannot exceed 1800 seconds" <<<"$output" || fail "invalid budget diagnostic was missing: $output"
  printf '[PASS] invalid readiness timing fails closed\n'
}

run_batching_case() {
  local batch_dir="$TMP_ROOT/batching"
  mkdir -p "$batch_dir"
  local output
  output="$({
    source "$GATE"
    ECS_CLUSTER=cluster
    aws_capture() {
      local destination="$1"
      shift
      local seen_tasks=false argument
      local -a tasks=()
      for argument in "$@"; do
        if [ "$argument" = "--tasks" ]; then seen_tasks=true; continue; fi
        if [ "$seen_tasks" = "true" ]; then
          [[ "$argument" == --* ]] && break
          tasks+=("$argument")
        fi
      done
      printf x >>"$batch_dir/calls"
      local json
      json="$(printf '%s\n' "${tasks[@]}" | jq -Rsc 'split("\n") | map(select(length > 0) | {taskArn:.}) | {tasks:.,failures:[]}')"
      printf -v "$destination" '%s' "$json"
    }
    local -a task_arns=()
    local combined number
    for number in $(seq 1 205); do task_arns+=("task/$number"); done
    describe_tasks_batched combined "${task_arns[@]}"
    jq -er '.tasks | length' <<<"$combined"
  })"
  [ "$output" = "205" ] || fail "DescribeTasks batching lost replicas: $output"
  [ "$(wc -c <"$batch_dir/calls" | tr -d ' ')" = "3" ] || fail "DescribeTasks did not use 100-item batches"
  printf '[PASS] DescribeTasks batching covers 205 replicas\n'
}

run_gate_case() {
  local scenario="$1" expected="$2" pattern="$3"
  CASE_DIR="$TMP_ROOT/$scenario"
  mkdir -p "$CASE_DIR"
  SCENARIO="$scenario"
  export CASE_DIR SCENARIO
  printf '999' >"$CASE_DIR/time"

  local output status=0 deadline=1300
  if [ "$scenario" = "missing_target" ] || [ "$scenario" = "extra_target" ]; then deadline=1060; fi
  if output="$({
    source "$GATE"
    now_epoch() {
      local value
      value="$(<"$CASE_DIR/time")"
      value=$((value + 1))
      printf '%s' "$value" >"$CASE_DIR/time"
      printf '%s\n' "$value"
    }
    sleep() { :; }
    main \
      --region us-east-1 --cluster cluster --service svc \
      --task-definition-arn "$TASK_DEFINITION" --image-uri "$IMAGE" \
      --app-container app --probe-container app-readiness-probe \
      --target-group-arn tg-candidate --listener-arn listener \
      --candidate-rule-arn rule --active-target-group-arn tg-active \
      --desired-count 2 --attempt-start-epoch 1000 --deadline-epoch "$deadline" \
      --poll-interval 1 --stable-observations 2
  } 2>&1)"; then
    status=0
  else
    status=$?
  fi

  if [ "$expected" = "pass" ]; then
    [ "$status" -eq 0 ] || fail "$scenario unexpectedly failed: $output"
  else
    [ "$status" -ne 0 ] || fail "$scenario unexpectedly passed"
    grep -Fq "$pattern" <<<"$output" || fail "$scenario did not report '$pattern': $output"
  fi
  printf '[PASS] gate scenario: %s\n' "$scenario"
}

run_promotion_order_case() {
  local active="$1" inactive="$2" gate_result="$3"
  local case_name="order-${active}-${gate_result}"
  local log_file="$TMP_ROOT/$case_name.log"
  local env_file="$TMP_ROOT/$case_name.env"
  local output status=0

  if output="$({
    source "$DEPLOY"
    ENV_NAME=dev
    AWS_REGION_NAME=us-east-1
    USE_INSTANCE_ROLE=true
    ECS_CLUSTER=cluster
    INACTIVE_SERVICE="svc-$inactive"
    INACTIVE_COLOR="$inactive"
    ACTIVE_COLOR="$active"
    ACTIVE_SERVICE="svc-$active"
    ACTIVE_TG="tg-$active"
    INACTIVE_TG="tg-$inactive"
    ALB_LISTENER_ARN=listener
    ALB_CANDIDATE_RULE_ARN=rule
    NEW_TASK_DEFINITION_ARN="$TASK_DEFINITION"
    IMAGE_URI="$IMAGE"
    DESIRED_COUNT=2
    TARGET_HEALTH_MAX_WAIT_SECONDS=300
    TARGET_HEALTH_POLL_INTERVAL_SECONDS=1
    READINESS_STABLE_OBSERVATIONS=2
    DRAIN_DELAY_MINUTES=5
    SCALE_DOWN_RULE_NAME=scale-down
    SCALE_DOWN_LAMBDA_ARN=lambda
    OUTPUT_ENV_FILE="$env_file"
    AWS_ARGS=()
    aws() { printf 'aws %s\n' "$*" >>"$log_file"; }
    execute_readiness_gate() {
      printf 'readiness %s\n' "$*" >>"$log_file"
      [ "$gate_result" = "pass" ]
    }
    promote_inactive_color
    schedule_old_color_scale_down
    write_outputs
  } 2>&1)"; then
    status=0
  else
    status=$?
  fi

  if [ "$gate_result" = "pass" ]; then
    [ "$status" -eq 0 ] || fail "$case_name unexpectedly failed: $output"
    local update_line gate_line listener_line rule_line schedule_line target_line
    update_line="$(grep -n 'aws ecs update-service' "$log_file" | cut -d: -f1)"
    gate_line="$(grep -n '^readiness ' "$log_file" | cut -d: -f1)"
    listener_line="$(grep -n 'aws elbv2 modify-listener' "$log_file" | cut -d: -f1)"
    rule_line="$(grep -n 'aws elbv2 modify-rule' "$log_file" | cut -d: -f1)"
    schedule_line="$(grep -n 'aws events put-rule' "$log_file" | cut -d: -f1)"
    target_line="$(grep -n 'aws events put-targets' "$log_file" | cut -d: -f1)"
    [ "$update_line" -lt "$gate_line" ] && [ "$gate_line" -lt "$listener_line" ] && [ "$listener_line" -lt "$rule_line" ] && [ "$rule_line" -lt "$schedule_line" ] && [ "$schedule_line" -lt "$target_line" ] ||
      fail "$case_name ordering was wrong"
    grep -Fq -- "--task-definition-arn $TASK_DEFINITION" "$log_file" || fail "$case_name did not bind revision"
    grep -Fq -- "--image-uri $IMAGE" "$log_file" || fail "$case_name did not bind image"
    grep -Fq "ACTIVE_COLOR=$inactive" "$env_file" || fail "$case_name did not write successful outputs"
  else
    [ "$status" -ne 0 ] || fail "$case_name unexpectedly passed"
    ! grep -q 'modify-listener\|modify-rule' "$log_file" || fail "$case_name mutated routing after gate failure"
  fi
  printf '[PASS] promotion ordering: %s\n' "$case_name"
}

command -v jq >/dev/null 2>&1 || fail "jq is required"

run_gate_case ready pass ""
run_gate_case unready fail "without an explicit zero exit code"
run_gate_case missing_exit fail "without an explicit zero exit code"
run_gate_case replacement fail "replacement or identity change"
run_gate_case container_change fail "identity changed"
run_gate_case extra_target fail "deadline expired"
run_gate_case missing_target fail "deadline expired"
run_gate_case stale fail "outside the bounded deployment attempt"
run_gate_case wrong_revision fail "task, container, image, network"
run_gate_case api_failure fail "embedded failures"
run_gate_case ambiguous fail "ambiguous"
run_gate_case mapping_change fail "mapping changed"
run_gate_case count_change fail "desired count"

run_batching_case
run_invalid_timing_case

run_promotion_order_case blue green pass
run_promotion_order_case green blue pass
run_promotion_order_case blue green fail

printf 'All readiness gate tests passed.\n'
