#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKDEF_FILE="$(mktemp)"
SENTINEL_FILE="$(mktemp)"
FAKE_BIN="$(mktemp -d)"
IMAGE="123456789012.dkr.ecr.us-east-1.amazonaws.com/demo-dev-shared-demo-ms@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

cleanup() {
  rm -f "$TASKDEF_FILE" "$SENTINEL_FILE"
  rm -rf "$FAKE_BIN"
}
trap cleanup EXIT

cat >"$FAKE_BIN/aws" <<'EOF'
#!/bin/bash
printf 'external aws was invoked\n' >>"$OFFLINE_AWS_SENTINEL"
exit 97
EOF
chmod +x "$FAKE_BIN/aws"
export OFFLINE_AWS_SENTINEL="$SENTINEL_FILE"
PATH="$FAKE_BIN:/usr/bin:/bin"
export PATH

"$ROOT_DIR/scripts/render-demo-api-taskdef.sh" \
  --env dev \
  --region us-east-1 \
  --account-id 123456789012 \
  --color blue \
  --image-uri "$IMAGE" \
  --db-secret-id arn:aws:secretsmanager:us-east-1:123456789012:secret:demo/dev/app/db-connection-string-AbCdEf \
  --output "$TASKDEF_FILE"

jq -e --arg image "$IMAGE" '
  .family == "demo-dev-app-api-blue"
  and .executionRoleArn == "arn:aws:iam::123456789012:role/demo-dev-app-api-blue-exec-role"
  and .taskRoleArn == "arn:aws:iam::123456789012:role/demo-dev-app-api-blue-task-role"
  and (.containerDefinitions | length == 2)
  and (.containerDefinitions[0]
    | .name == "demo-dev-app-api-blue"
      and .image == $image
      and .essential == true
      and .secrets[0].valueFrom == "arn:aws:secretsmanager:us-east-1:123456789012:secret:demo/dev/app/db-connection-string-AbCdEf"
      and ([.portMappings[] | select(.containerPort == 8080)] | length == 1)
      and ((.healthCheck? // null) == null)
      and ((.restartPolicy? // null) == null))
  and (.containerDefinitions[1]
    | .name == "demo-dev-app-api-blue-readiness-probe"
      and .image == $image
      and .essential == false
      and .command == ["readiness-probe"]
      and ((.environment? // []) | length == 0)
      and ((.secrets? // []) | length == 0)
      and ((.portMappings? // []) | length == 0)
      and ((.healthCheck? // null) == null)
      and ((.restartPolicy? // null) == null))
' "$TASKDEF_FILE" >/dev/null

[ ! -s "$SENTINEL_FILE" ] || { printf 'Renderer test escaped to AWS.\n' >&2; exit 1; }

printf 'Task definition readiness-probe contract passed.\n'
