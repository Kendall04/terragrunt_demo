#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/aws-response-boundary.sh
source "$SCRIPT_DIR/aws-response-boundary.sh"

AWS_REGION_NAME=""
AWS_PROFILE_NAME=""
USE_INSTANCE_ROLE="false"
ECS_CLUSTER=""
ECS_SERVICE=""
TASK_DEFINITION_ARN=""
IMAGE_URI=""
APP_CONTAINER=""
PROBE_CONTAINER=""
TARGET_GROUP_ARN=""
LISTENER_ARN=""
CANDIDATE_RULE_ARN=""
ACTIVE_TARGET_GROUP_ARN=""
DESIRED_COUNT=""
ATTEMPT_START_EPOCH=""
DEADLINE_EPOCH=""
POLL_INTERVAL_SECONDS="5"
STABLE_OBSERVATIONS="2"

AWS_ARGS=()
FROZEN_COHORT=""
OBSERVED_TASKS=""
OBSERVED_TASK_IDENTITIES='{}'
OBSERVED_TASK_VERSIONS='{}'
OBSERVED_LIFECYCLES='{}'
OBSERVED_SERVICE_IDENTITY=''
PROBE_SUCCEEDED_TASKS=""
TARGET_SET_ESTABLISHED="false"
MAX_SERVICE_RUNNING_COUNT=0
MAX_DEPLOYMENT_RUNNING_COUNT=0
OBSERVATION_STATUS=""
OBSERVATION_FINGERPRINT=""

usage() {
  cat <<'EOF'
Usage: scripts/ecs-readiness-gate.sh --region REGION --cluster CLUSTER --service SERVICE \
  --task-definition-arn ARN --image-uri ECR_URI@sha256:... \
  --app-container NAME --probe-container NAME --target-group-arn ARN \
  --listener-arn ARN --candidate-rule-arn ARN --active-target-group-arn ARN \
  --desired-count N --attempt-start-epoch EPOCH --deadline-epoch EPOCH [options]

Validates one deployment attempt's complete task-local readiness evidence and
returns success only after repeated complete observations plus an immediate final
revalidation. It never mutates AWS resources.
EOF
}

log() {
  printf '[READINESS] %s\n' "$*"
}

die() {
  printf '[READINESS ERROR] %s\n' "$*" >&2
  exit 1
}

redact_text() {
  printf '%s\n' "$*" | sed -E \
    -e 's/[0-9]{12}/<aws-account-id>/g' \
    -e 's#arn:aws:[^[:space:]"'"'"']+#<aws-arn>#g' \
    -e 's#[0-9]{12}\.dkr\.ecr\.([A-Za-z0-9-]+)\.amazonaws\.com#<aws-account-id>.dkr.ecr.\1.amazonaws.com#g'
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --region) AWS_REGION_NAME="${2:-}"; shift 2 ;;
      --profile) AWS_PROFILE_NAME="${2:-}"; USE_INSTANCE_ROLE="false"; shift 2 ;;
      --use-instance-role) AWS_PROFILE_NAME=""; USE_INSTANCE_ROLE="true"; shift ;;
      --cluster) ECS_CLUSTER="${2:-}"; shift 2 ;;
      --service) ECS_SERVICE="${2:-}"; shift 2 ;;
      --task-definition-arn) TASK_DEFINITION_ARN="${2:-}"; shift 2 ;;
      --image-uri) IMAGE_URI="${2:-}"; shift 2 ;;
      --app-container) APP_CONTAINER="${2:-}"; shift 2 ;;
      --probe-container) PROBE_CONTAINER="${2:-}"; shift 2 ;;
      --target-group-arn) TARGET_GROUP_ARN="${2:-}"; shift 2 ;;
      --listener-arn) LISTENER_ARN="${2:-}"; shift 2 ;;
      --candidate-rule-arn) CANDIDATE_RULE_ARN="${2:-}"; shift 2 ;;
      --active-target-group-arn) ACTIVE_TARGET_GROUP_ARN="${2:-}"; shift 2 ;;
      --desired-count) DESIRED_COUNT="${2:-}"; shift 2 ;;
      --attempt-start-epoch) ATTEMPT_START_EPOCH="${2:-}"; shift 2 ;;
      --deadline-epoch) DEADLINE_EPOCH="${2:-}"; shift 2 ;;
      --poll-interval) POLL_INTERVAL_SECONDS="${2:-}"; shift 2 ;;
      --stable-observations) STABLE_OBSERVATIONS="${2:-}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1" ;;
    esac
  done
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "$1 is required but was not found in PATH."
}

validate_args() {
  local required=(
    AWS_REGION_NAME ECS_CLUSTER ECS_SERVICE TASK_DEFINITION_ARN IMAGE_URI
    APP_CONTAINER PROBE_CONTAINER TARGET_GROUP_ARN LISTENER_ARN
    CANDIDATE_RULE_ARN ACTIVE_TARGET_GROUP_ARN DESIRED_COUNT
    ATTEMPT_START_EPOCH DEADLINE_EPOCH
  )
  local name
  for name in "${required[@]}"; do
    [ -n "${!name:-}" ] || die "Required value $name is empty."
  done

  [[ "$IMAGE_URI" =~ @sha256:[a-f0-9]{64}$ ]] || die "Expected image must be digest-qualified."
  [[ "$DESIRED_COUNT" =~ ^[1-9][0-9]*$ ]] || die "--desired-count must be a positive integer."
  [[ "$ATTEMPT_START_EPOCH" =~ ^[0-9]+$ ]] || die "--attempt-start-epoch must be an epoch integer."
  [[ "$DEADLINE_EPOCH" =~ ^[0-9]+$ ]] || die "--deadline-epoch must be an epoch integer."
  [[ "$POLL_INTERVAL_SECONDS" =~ ^[1-9][0-9]*$ ]] || die "--poll-interval must be a positive integer."
  if ! [[ "$STABLE_OBSERVATIONS" =~ ^[0-9]+$ ]] ||
    [ "$STABLE_OBSERVATIONS" -lt 2 ] || [ "$STABLE_OBSERVATIONS" -gt 10 ]; then
    die "--stable-observations must be between 2 and 10."
  fi
  [ "$DEADLINE_EPOCH" -gt "$ATTEMPT_START_EPOCH" ] || die "Readiness deadline must follow attempt start."
  [ $((DEADLINE_EPOCH - ATTEMPT_START_EPOCH)) -le 1800 ] || die "Readiness budget cannot exceed 1800 seconds."
  [ "$POLL_INTERVAL_SECONDS" -lt $((DEADLINE_EPOCH - ATTEMPT_START_EPOCH)) ] ||
    die "Readiness poll interval must be shorter than the total budget."

  AWS_ARGS=(--region "$AWS_REGION_NAME" --cli-connect-timeout 5 --cli-read-timeout 10)
  if [ "$USE_INSTANCE_ROLE" != "true" ] && [ -n "$AWS_PROFILE_NAME" ]; then
    AWS_ARGS+=(--profile "$AWS_PROFILE_NAME")
  fi
}

now_epoch() {
  date +%s
}

check_deadline() {
  local now
  now="$(now_epoch)"
  [ "$now" -lt "$DEADLINE_EPOCH" ] || die "Readiness evidence deadline expired before traffic switching."
}

remaining_seconds() {
  local now remaining
  now="$(now_epoch)"
  remaining=$((DEADLINE_EPOCH - now))
  [ "$remaining" -gt 0 ] || die "Readiness evidence deadline expired before traffic switching."
  printf '%s\n' "$remaining"
}

sleep_until_next_poll() {
  local now remaining duration
  now="$(now_epoch)"
  remaining=$((DEADLINE_EPOCH - now))
  [ "$remaining" -gt 0 ] || die "Readiness evidence deadline expired before traffic switching."
  duration="$POLL_INTERVAL_SECONDS"
  if [ "$duration" -gt "$remaining" ]; then
    duration="$remaining"
  fi
  sleep "$duration"
}

aws_capture() {
  local destination="$1"
  shift
  local output remaining
  check_deadline
  remaining="$(remaining_seconds)"
  if ! output="$(python3 "$SCRIPT_DIR/bounded-process.py" "$remaining" \
    env AWS_MAX_ATTEMPTS=3 AWS_RETRY_MODE=standard AWS_PAGER='' \
    aws "$@" "${AWS_ARGS[@]}" 2>&1)"; then
    die "AWS observation failed for '$1': $(redact_text "$output")"
  fi
  check_deadline
  if [ "$2" != describe-tasks ]; then
    validate_aws_response "$2" <<<"$output" || die "$2 response envelope is malformed."
  fi
  printf -v "$destination" '%s' "$output"
}

validate_registered_definition() {
  local definition_json
  local expected_digest="${IMAGE_URI##*@}"
  aws_capture definition_json ecs describe-task-definition --task-definition "$TASK_DEFINITION_ARN" --output json

  if ! jq -e \
    --arg task_definition "$TASK_DEFINITION_ARN" \
    --arg image "$IMAGE_URI" \
    --arg app "$APP_CONTAINER" \
    --arg probe "$PROBE_CONTAINER" '
      .taskDefinition as $td
      | ($td.taskDefinitionArn == $task_definition)
        and ($td.networkMode == "awsvpc")
        and ($td.requiresCompatibilities | index("FARGATE") != null)
        and ($td.containerDefinitions | length == 2)
        and ([ $td.containerDefinitions[] | select(.name == $app) ] | length == 1)
        and ([ $td.containerDefinitions[] | select(.name == $probe) ] | length == 1)
        and ($td.containerDefinitions[] | select(.name == $app)
          | .image == $image
            and .essential == true
            and ([.portMappings[]? | select(.containerPort == 8080 and .protocol == "tcp")] | length == 1))
        and ($td.containerDefinitions[] | select(.name == $probe)
          | .image == $image
            and .essential == false
            and .command == ["readiness-probe"]
            and ((.restartPolicy? // null) == null or .restartPolicy.enabled == false)
            and ((.secrets? // []) | length == 0)
            and ((.environment? // []) | length == 0)
            and ((.portMappings? // []) | length == 0))
    ' <<<"$definition_json" >/dev/null; then
    die "Registered task definition does not match the required app/probe contract."
  fi

  [ "$expected_digest" != "$IMAGE_URI" ] || die "Could not derive expected image digest."
}

extract_route_target() {
  local json="$1"
  local root="$2"
  jq -er --arg root "$root" -f "$SCRIPT_DIR/alb-route-target.jq" <<<"$json"
}

observe_routing() {
  local listener_json rule_json listener_target rule_target
  aws_capture listener_json elbv2 describe-listeners --listener-arns "$LISTENER_ARN" --output json
  aws_capture rule_json elbv2 describe-rules --rule-arns "$CANDIDATE_RULE_ARN" --output json

  listener_target="$(extract_route_target "$listener_json" listener)" || die "Listener forwarding configuration is ambiguous."
  rule_target="$(extract_route_target "$rule_json" rule)" || die "Candidate-rule forwarding configuration is ambiguous."
  [ "$listener_target" = "$ACTIVE_TARGET_GROUP_ARN" ] || die "Active listener mapping changed during readiness evaluation."
  [ "$rule_target" = "$TARGET_GROUP_ARN" ] || die "Candidate rule no longer maps exactly to the candidate target group."
  printf '%s|%s' "$listener_target" "$rule_target"
}

describe_tasks_batched() {
  local destination="$1"
  shift
  local task_arns=("$@")
  local chunks=()
  local offset batch_json

  for ((offset = 0; offset < ${#task_arns[@]}; offset += 100)); do
    aws_capture batch_json ecs describe-tasks \
      --cluster "$ECS_CLUSTER" \
      --tasks "${task_arns[@]:offset:100}" \
      --output json
    # Slurp this AWS call only: -e alone checks the last result in a JSON
    # stream. Reject zero/multiple documents before inspecting the envelope.
    if ! jq -se '
      length == 1 and (.[0] |
        type == "object"
        and (.tasks | type == "array")
        and (.failures | type == "array")
        and all(.tasks[]; type == "object")
        and all(.failures[]; type == "object"))
    ' <<<"$batch_json" >/dev/null; then
      die "DescribeTasks batch response envelope is malformed."
    fi
    chunks+=("$batch_json")
  done

  local aggregate_json
  aggregate_json="$(printf '%s\n' "${chunks[@]}" | jq -s '{tasks:[.[].tasks[]],failures:[.[].failures[]]}')"
  printf -v "$destination" '%s' "$aggregate_json"
}

retain_task_observations() {
  local tasks_json="$1"
  local current_identities current_versions

  current_identities="$(jq -cS --arg app "$APP_CONTAINER" --arg probe "$PROBE_CONTAINER" '
    def populated:
      if type == "object" then with_entries(.value |= populated | select(.value != null and .value != [] and .value != {}))
      else . end;
    [.tasks[] | {key:.taskArn, value:({
      taskDefinitionArn,group,startedBy,createdAt,
      eniAttached:(if any(.attachments[]?; .type == "ElasticNetworkInterface" and .status == "ATTACHED") then true else null end),
      eniAddresses:[.attachments[]? | select(.type == "ElasticNetworkInterface")
        | .details[]? | select(.name == "privateIPv4Address") | .value],
      app:([.containers[]? | select(.name == $app) | {containerArn,runtimeId,image,imageDigest,networkInterfaces}][0]),
      probe:([.containers[]? | select(.name == $probe) | {containerArn,runtimeId,image,imageDigest}][0])
    } | populated)}] | from_entries
  ' <<<"$tasks_json")"
  current_versions="$(jq -cS '[.tasks[] | {key:.taskArn, value:.version}] | from_entries' <<<"$tasks_json")"

  if ! jq -en --argjson previous "$OBSERVED_TASK_IDENTITIES" --argjson current "$current_identities" '
    all($previous | paths(scalars); . as $path | ($previous | getpath($path)) == ($current | getpath($path)))
  ' >/dev/null; then
    die "Candidate task or container identity contradicted an earlier startup observation."
  fi

  if ! jq -en --argjson previous "$OBSERVED_TASK_VERSIONS" --argjson current "$current_versions" '
    all($current | keys[]; $previous[.] == null or $current[.] >= $previous[.])
  ' >/dev/null; then
    die "Candidate task version regressed from a newer startup observation."
  fi

  local lifecycles
  lifecycles="$(jq -c --arg app "$APP_CONTAINER" --arg probe "$PROBE_CONTAINER" '
    def rank: {PROVISIONING:0,PENDING:1,ACTIVATING:2,RUNNING:3,STOPPED:4}[.];
    [.tasks[] | {key:.taskArn,value:{task:(.lastStatus | rank),
      connectivity:(if .connectivity == null then null else {DISCONNECTED:0,CONNECTED:1}[.connectivity] end),
      app:([.containers[]? | select(.name == $app) | .lastStatus | rank][0]),
      probe:([.containers[]? | select(.name == $probe) | .lastStatus | rank][0])}}] | from_entries
  ' <<<"$tasks_json")"
  jq -en --argjson previous "$OBSERVED_LIFECYCLES" --argjson current "$lifecycles" '
    all($previous | paths(numbers); . as $path | ($current | getpath($path)) >= ($previous | getpath($path)))
  ' >/dev/null || die "Candidate task/container lifecycle regressed during startup."
  OBSERVED_LIFECYCLES="$lifecycles"

  OBSERVED_TASK_IDENTITIES="$(jq -cn --argjson previous "$OBSERVED_TASK_IDENTITIES" --argjson current "$current_identities" '$previous * $current')"
  OBSERVED_TASK_VERSIONS="$(jq -cn --argjson previous "$OBSERVED_TASK_VERSIONS" --argjson current "$current_versions" '$previous * $current')"
}

validate_service_observation() {
  if ! jq -e \
    --arg service "$ECS_SERVICE" \
    --arg task_definition "$TASK_DEFINITION_ARN" \
    --arg target_group "$TARGET_GROUP_ARN" \
    --arg app "$APP_CONTAINER" \
    --argjson desired "$DESIRED_COUNT" '
      (.failures | type == "array" and length == 0)
      and (.services | type == "array" and length == 1)
      and .services[0].serviceName == $service
      and (.services[0].serviceArn | type == "string" and length > 0)
      and .services[0].status == "ACTIVE"
      and ([.services[0].runningCount, .services[0].pendingCount,
            .services[0].deployments[0].runningCount, .services[0].deployments[0].pendingCount]
        | all(.[]; type == "number" and . == floor and . >= 0 and . <= $desired))
      and .services[0].taskDefinition == $task_definition
      and .services[0].desiredCount == $desired
      and (.services[0].loadBalancers | length) == 1
      and .services[0].loadBalancers[0].targetGroupArn == $target_group
      and .services[0].loadBalancers[0].containerName == $app
      and .services[0].loadBalancers[0].containerPort == 8080
      and (.services[0].deployments | length) == 1
      and .services[0].deployments[0].status == "PRIMARY"
      and .services[0].deployments[0].taskDefinition == $task_definition
      and .services[0].deployments[0].desiredCount == $desired
      and (.services[0].deployments[0].id | type == "string" and length > 0)
    ' <<<"$1" >/dev/null; then
    die "Candidate service revision, desired count, deployment set, or status changed."
  fi
  local identity
  identity="$(jq -cS '.services[0] | {serviceArn,serviceName,taskDefinition,desiredCount,loadBalancers,deploymentId:.deployments[0].id}' <<<"$1")"
  [ -z "$OBSERVED_SERVICE_IDENTITY" ] || [ "$identity" = "$OBSERVED_SERVICE_IDENTITY" ] ||
    die "Candidate service/deployment identity contradicted an earlier observation."
  OBSERVED_SERVICE_IDENTITY="$identity"
}

observe_once() {
  local service_before service_after service_fingerprint_before service_fingerprint_after
  local routing_before routing_after list_json tasks_json target_json
  local deployment_id task_count cohort expected_digest now service_complete
  local probe_pending invalid_probe target_invalid target_pending
  local task_fingerprint target_fingerprint
  local task_arns=()

  OBSERVATION_STATUS="pending"
  OBSERVATION_FINGERPRINT=""
  now="$(now_epoch)"
  expected_digest="${IMAGE_URI##*@}"

  aws_capture service_before ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" --output json
  validate_service_observation "$service_before"
  deployment_id="$(jq -er '.services[0].deployments[0].id' <<<"$service_before")"
  service_fingerprint_before="$(jq -cS '.services[0] | {serviceArn,serviceName,status,taskDefinition,desiredCount,runningCount,pendingCount,loadBalancers,deployments}' <<<"$service_before")"

  local service_running deployment_running
  service_running="$(jq -er '.services[0].runningCount' <<<"$service_before")"
  deployment_running="$(jq -er '.services[0].deployments[0].runningCount' <<<"$service_before")"
  [ "$service_running" -ge "$MAX_SERVICE_RUNNING_COUNT" ] || die "Candidate service running count regressed during startup."
  [ "$deployment_running" -ge "$MAX_DEPLOYMENT_RUNNING_COUNT" ] || die "Candidate deployment running count regressed during startup."
  MAX_SERVICE_RUNNING_COUNT="$service_running"
  MAX_DEPLOYMENT_RUNNING_COUNT="$deployment_running"

  routing_before="$(observe_routing)"

  service_complete="false"
  if jq -e --argjson desired "$DESIRED_COUNT" '
    .services[0].runningCount == $desired
    and .services[0].pendingCount == 0
    and .services[0].deployments[0].runningCount == $desired
    and .services[0].deployments[0].pendingCount == 0
  ' <<<"$service_before" >/dev/null; then
    service_complete="true"
  elif [ -n "$FROZEN_COHORT" ]; then
    die "Candidate service stability regressed after cohort discovery."
  fi

  aws_capture list_json ecs list-tasks \
    --cluster "$ECS_CLUSTER" \
    --service-name "$ECS_SERVICE" \
    --desired-status RUNNING \
    --output json
  jq -e '.taskArns | type == "array"' <<<"$list_json" >/dev/null ||
    die "ListTasks response did not contain a task ARN array."
  jq -e '
    all(.taskArns[]; type == "string" and length > 0)
    and ((.taskArns | length) == (.taskArns | unique | length))
  ' <<<"$list_json" >/dev/null || die "ListTasks returned empty or duplicate task ARNs."
  mapfile -t task_arns < <(jq -r '.taskArns | sort | .[]' <<<"$list_json")
  task_count="${#task_arns[@]}"
  if [ "$task_count" -gt "$DESIRED_COUNT" ]; then
    die "Candidate service exposed more RUNNING tasks than the intended replica count."
  fi

  cohort="$(printf '%s\n' "${task_arns[@]}")"
  if [ -n "$OBSERVED_TASKS" ]; then
    while IFS= read -r observed_task; do
      [ -z "$observed_task" ] || grep -Fxq "$observed_task" <<<"$cohort" ||
        die "A previously observed candidate task disappeared during readiness evaluation."
    done <<<"$OBSERVED_TASKS"
  fi
  OBSERVED_TASKS="$(printf '%s\n%s\n' "$OBSERVED_TASKS" "$cohort" | sed '/^$/d' | sort -u)"

  if [ "$task_count" -gt 0 ]; then
    local requested_task_arns
    requested_task_arns="$(printf '%s\n' "${task_arns[@]}" | jq -Rsc 'split("\n") | map(select(length > 0)) | sort')"
    describe_tasks_batched tasks_json "${task_arns[@]}"
    if ! jq -e '(.failures | length) == 0' <<<"$tasks_json" >/dev/null; then
      die "DescribeTasks returned one or more embedded failures."
    fi
    if ! jq -e --argjson requested "$requested_task_arns" '
      ([.tasks[].taskArn] | all(.[]; type == "string" and length > 0))
      and (([.tasks[].taskArn] | length) == ([.tasks[].taskArn] | unique | length))
      and (([.tasks[].taskArn] | sort) == $requested)
    ' <<<"$tasks_json" >/dev/null; then
      die "DescribeTasks task ARN set did not exactly match the requested cohort."
    fi
  else
    tasks_json='{"tasks":[],"failures":[]}'
  fi

  # Startup permits absent metadata, never conflicting populated values. Once
  # the probe stops, complete runtime/network identity is mandatory.
  if ! jq -e --arg td "$TASK_DEFINITION_ARN" --arg group "service:$ECS_SERVICE" \
    --arg deployment "$deployment_id" --arg app "$APP_CONTAINER" --arg probe "$PROBE_CONTAINER" \
    --arg image "$IMAGE_URI" --arg digest "$expected_digest" '
      def nonempty: type == "string" and length > 0;
      def startup: . == "PROVISIONING" or . == "PENDING" or . == "ACTIVATING" or . == "RUNNING";
      all(.tasks[];
        .taskDefinitionArn == $td and .group == $group and .startedBy == $deployment
        and .desiredStatus == "RUNNING" and (.lastStatus | startup)
        and (.version | type == "number" and . == floor and . >= 0)
        and (.createdAt | nonempty)
        and ((.connectivity // "CONNECTED") == "CONNECTED" or
             (.lastStatus != "RUNNING" and .connectivity == "DISCONNECTED"))
        and ([.attachments[]? | select(.type == "ElasticNetworkInterface")
          | .details[]? | select(.name == "privateIPv4Address") | .value] as $eni
          | ($eni | length <= 1) and all($eni[]; nonempty)
          and all(.containers[]? | select(.name == $app) | .networkInterfaces[]?;
            ($eni | length == 0) or .privateIpv4Address == $eni[0]))
        and ((.containers // []) | type == "array")
        and ([.containers[]?.name] | length == (unique | length))
        and all(.containers[]?;
          (.name == $app or .name == $probe)
          and (.image == $image)
          and ((.imageDigest // $digest) == $digest)
          and (if .name == $app then (.lastStatus | startup)
               else (.lastStatus | startup or . == "STOPPED") end)
          and (if has("containerArn") then (.containerArn | nonempty) else true end)
          and (if has("runtimeId") then (.runtimeId | nonempty) else true end)
          and (if has("networkInterfaces") then
            (.networkInterfaces | type == "array" and length <= 1)
            and all(.networkInterfaces[]; .privateIpv4Address | nonempty)
            else true end))
      )
    ' <<<"$tasks_json" >/dev/null; then
    die "Candidate task, container, image, network, or startup identity is invalid."
  fi

  local incomplete_tasks
  incomplete_tasks="$(jq -c \
    --arg task_definition "$TASK_DEFINITION_ARN" \
    --arg group "service:$ECS_SERVICE" \
    --arg deployment "$deployment_id" \
    --arg app "$APP_CONTAINER" \
    --arg probe "$PROBE_CONTAINER" \
    --arg image "$IMAGE_URI" \
    --arg digest "$expected_digest" '
      [.tasks[] | select((
        .taskDefinitionArn == $task_definition
        and .group == $group
        and .startedBy == $deployment
        and .desiredStatus == "RUNNING"
        and .lastStatus == "RUNNING"
        and .connectivity == "CONNECTED"
        and (.version | type == "number")
        and (.createdAt | type == "string" and length > 0)
        and ([.containers[]? | select(.name == $app)] | length == 1)
        and ([.containers[]? | select(.name == $probe)] | length == 1)
        and ([.containers[]? | select(.name == $app)][0]
          | .image == $image
            and .imageDigest == $digest
            and .lastStatus == "RUNNING"
            and (.containerArn | type == "string" and length > 0)
            and (.runtimeId | type == "string" and length > 0)
            and (.networkInterfaces | length == 1)
            and (.networkInterfaces[0].privateIpv4Address | type == "string" and length > 0))
        and ([.containers[]? | select(.name == $probe)][0]
          | .image == $image
            and .imageDigest == $digest
            and (.containerArn | type == "string" and length > 0)
            and (.runtimeId | type == "string" and length > 0)
            and (.lastStatus == "RUNNING" or .lastStatus == "STOPPED"))
        and ([.attachments[]?
          | select(.type == "ElasticNetworkInterface" and .status == "ATTACHED")
          | [.details[]? | select(.name == "privateIPv4Address") | .value][0]
        ] | length == 1)
        and ([.attachments[]?
          | select(.type == "ElasticNetworkInterface" and .status == "ATTACHED")
          | [.details[]? | select(.name == "privateIPv4Address") | .value][0]
        ][0] == ([.containers[]? | select(.name == $app)][0].networkInterfaces[0].privateIpv4Address))
      ) | not)]
    ' <<<"$tasks_json")"

  local created_at created_epoch
  while IFS= read -r created_at; do
    if ! created_epoch="$(date -d "$created_at" +%s 2>/dev/null)"; then
      die "Candidate task creation time is malformed."
    fi
    if [ "$created_epoch" -lt $((ATTEMPT_START_EPOCH - 60)) ] || [ "$created_epoch" -gt $((now + 60)) ]; then
      die "Candidate task creation time falls outside the bounded deployment attempt."
    fi
  done < <(jq -r '.tasks[].createdAt' <<<"$tasks_json")

  retain_task_observations "$tasks_json"

  invalid_probe="$(jq -r --arg probe "$PROBE_CONTAINER" '
    .tasks[] | .taskArn as $task | .containers[]? | select(.name == $probe)
    | select(.lastStatus == "STOPPED" and ((.exitCode | type) != "number" or .exitCode != 0))
    | "replica=\($task | split("/")[-1]) exit=\(.exitCode // "missing")"
  ' <<<"$tasks_json")"
  [ -z "$invalid_probe" ] || die "A candidate readiness probe stopped without an explicit zero exit code: $invalid_probe"

  probe_pending="$(jq -r --arg probe "$PROBE_CONTAINER" '[.tasks[] | .containers[]? | select(.name == $probe and .lastStatus != "STOPPED")] | length' <<<"$tasks_json")"
  local current_probe_successes
  current_probe_successes="$(jq -r --arg probe "$PROBE_CONTAINER" '.tasks[] | select(any(.containers[]?; .name == $probe and .lastStatus == "STOPPED" and .exitCode == 0)) | .taskArn' <<<"$tasks_json" | sort)"
  if [ -n "$PROBE_SUCCEEDED_TASKS" ]; then
    while IFS= read -r succeeded_task; do
      [ -z "$succeeded_task" ] || grep -Fxq "$succeeded_task" <<<"$current_probe_successes" ||
        die "Previously successful readiness evidence regressed or changed."
    done <<<"$PROBE_SUCCEEDED_TASKS"
  fi
  PROBE_SUCCEEDED_TASKS="$(printf '%s\n%s\n' "$PROBE_SUCCEEDED_TASKS" "$current_probe_successes" | sed '/^$/d' | sort -u)"

  if [ "$incomplete_tasks" != "[]" ]; then
    jq -e --arg probe "$PROBE_CONTAINER" '
      any(.[]; any(.containers[]?; .name == $probe and .lastStatus == "STOPPED"))
    ' <<<"$incomplete_tasks" >/dev/null &&
      die "Completed probe lacks required task, container, image, network identity."
    [ -z "$FROZEN_COHORT" ] || die "Complete candidate runtime metadata regressed."
    return 0
  fi

  if [ "$task_count" -lt "$DESIRED_COUNT" ] || [ "$service_complete" != "true" ]; then
    [ -z "$FROZEN_COHORT" ] || die "A frozen candidate task disappeared during readiness evaluation."
    return 0
  fi

  if [ -z "$FROZEN_COHORT" ]; then
    FROZEN_COHORT="$cohort"
    log "Candidate cohort frozen with $task_count replica(s)."
  elif [ "$cohort" != "$FROZEN_COHORT" ]; then
    die "Candidate task replacement or identity change invalidated prior evidence."
  fi

  aws_capture target_json elbv2 describe-target-health --target-group-arn "$TARGET_GROUP_ARN" --output json
  target_invalid="$(jq -r \
    '[ .TargetHealthDescriptions[]? | (.Target.Id + ":" + (.Target.Port | tostring)) ] as $actual
      | (($actual | length) - ($actual | unique | length))
    ' <<<"$target_json")"
  [ "$target_invalid" = "0" ] || die "Candidate target group contains duplicate target identities."
  target_pending="$(jq -r \
    --argjson tasks "$tasks_json" --arg app "$APP_CONTAINER" '
      ([ $tasks.tasks[] | (.containers[] | select(.name == $app) | .networkInterfaces[0].privateIpv4Address) + ":8080" ] | sort) as $expected
      | ([ .TargetHealthDescriptions[]? | (.Target.Id + ":" + (.Target.Port | tostring)) ] | sort) as $actual
      | if $actual != $expected then 1
        elif any(.TargetHealthDescriptions[]; .TargetHealth.State != "healthy") then 1
        else 0 end
    ' <<<"$target_json")"

  if [ "$TARGET_SET_ESTABLISHED" = "true" ] && [ "$target_pending" != "0" ]; then
    die "Established candidate target coverage or liveness regressed."
  fi
  if [ "$target_pending" = "0" ]; then
    TARGET_SET_ESTABLISHED="true"
  fi
  if [ "$probe_pending" != "0" ] || [ "$target_pending" != "0" ]; then
    return 0
  fi

  routing_after="$(observe_routing)"
  [ "$routing_after" = "$routing_before" ] || die "Routing mapping changed within an evidence observation."
  aws_capture service_after ecs describe-services --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" --output json
  validate_service_observation "$service_after"
  service_fingerprint_after="$(jq -cS '.services[0] | {serviceArn,serviceName,status,taskDefinition,desiredCount,runningCount,pendingCount,loadBalancers,deployments}' <<<"$service_after")"
  [ "$service_fingerprint_after" = "$service_fingerprint_before" ] || die "Candidate service changed within an evidence observation."

  task_fingerprint="$(jq -cS --arg app "$APP_CONTAINER" --arg probe "$PROBE_CONTAINER" '[.tasks[] | {taskArn,taskDefinitionArn,group,startedBy,desiredStatus,lastStatus,connectivity,version,createdAt,containers:[.containers[] | select(.name == $app or .name == $probe) | {name,containerArn,runtimeId,image,imageDigest,lastStatus,exitCode,networkInterfaces}]}] | sort_by(.taskArn)' <<<"$tasks_json")"
  target_fingerprint="$(jq -cS '[.TargetHealthDescriptions[] | {Target,TargetHealth}] | sort_by(.Target.Id,.Target.Port)' <<<"$target_json")"
  OBSERVATION_FINGERPRINT="$(printf '%s\n%s\n%s\n%s\n' "$service_fingerprint_after" "$task_fingerprint" "$target_fingerprint" "$routing_after" | sha256sum | awk '{print $1}')"
  OBSERVATION_STATUS="complete"
}

run_gate() {
  local stable_count=0
  local last_fingerprint=""

  validate_registered_definition
  log "Evaluating exact per-replica readiness evidence for service=$ECS_SERVICE replicas=$DESIRED_COUNT."
  while true; do
    check_deadline
    observe_once
    if [ "$OBSERVATION_STATUS" != "complete" ]; then
      sleep_until_next_poll
      continue
    fi

    if [ -n "$last_fingerprint" ] && [ "$OBSERVATION_FINGERPRINT" = "$last_fingerprint" ]; then
      stable_count=$((stable_count + 1))
    else
      [ -z "$last_fingerprint" ] || die "Complete readiness evidence changed between observations."
      last_fingerprint="$OBSERVATION_FINGERPRINT"
      stable_count=1
    fi

    if [ "$stable_count" -lt "$STABLE_OBSERVATIONS" ]; then
      sleep_until_next_poll
      continue
    fi

    log "Stable readiness evidence established; performing immediate final revalidation."
    observe_once
    [ "$OBSERVATION_STATUS" = "complete" ] || die "Final readiness revalidation became incomplete."
    [ "$OBSERVATION_FINGERPRINT" = "$last_fingerprint" ] || die "Final readiness identity changed before traffic switching."
    check_deadline
    log "Final readiness revalidation succeeded for all $DESIRED_COUNT candidate replica(s)."
    return 0
  done
}

main() {
  parse_args "$@"
  require_command aws
  require_command jq
  require_command sha256sum
  require_command date
  require_command python3
  require_command env
  validate_args
  run_gate
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
