#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKDEF_FILE="$(mktemp)"
SENTINEL_FILE="$(mktemp)"
FAKE_BIN="$(mktemp -d)"
CONFIG_DIR="$(mktemp -d)"
SECRET='arn:aws:secretsmanager:us-east-1:123456789012:secret:demo/dev/app/db-connection-string-AbCdEf:::00000000-0000-4000-8000-000000000001'
KMS='arn:aws:kms:us-east-1:123456789012:key/00000000-0000-4000-8000-000000000002'
IMAGE="123456789012.dkr.ecr.us-east-1.amazonaws.com/demo-dev-shared-demo-ms@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

cleanup() {
  rm -f "$TASKDEF_FILE" "$SENTINEL_FILE"
  rm -rf "$FAKE_BIN"
  rm -rf "$CONFIG_DIR"
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

# Disposable public CA for rendering tests; never a real environment identity.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=Renderer-test \
  -addext basicConstraints=critical,CA:TRUE -keyout "$CONFIG_DIR/key" -out "$CONFIG_DIR/ca" 2>/dev/null
openssl x509 -in "$CONFIG_DIR/ca" -outform DER -out "$CONFIG_DIR/ca.der"
for env in dev prod; do
  jq -n --arg env "$env" '{schema:"SQL_RUNTIME_IDENTITY_V1",environment:$env,profile:"validated-v2",endpoint:"tcp:sql.example.test,1433",database:"demodb",runtime_user:"app_runtime",certificate_hostname:"sql.example.test"}' > "$CONFIG_DIR/$env.json"
  jq -n --arg env "$env" --arg der "$(base64 -w0 "$CONFIG_DIR/ca.der")" --arg pin "$(sha256sum "$CONFIG_DIR/ca.der" | cut -d" " -f1)" '{schema:"SQL_TLS_TRUST_V1",environment:$env,hostname:"sql.example.test",version:"test-v1",anchors:[{kind:"ca",sha256:$pin,der_base64:$der}]}' > "$CONFIG_DIR/$env-trust.json"
done
render() {
  "$ROOT_DIR/scripts/render-demo-api-taskdef.sh" \
  --env "$1" \
  --region us-east-1 \
  --account-id 123456789012 \
  --color blue \
  --image-uri "$IMAGE" \
  --db-secret-id "$SECRET" --kms-key-id "$KMS" \
  --output "$TASKDEF_FILE" "${@:2}"
}
for env in dev prod; do
  render "$env" --database-config "$CONFIG_DIR/$env.json" --sql-trust-manifest "$CONFIG_DIR/$env-trust.json"
  jq -e --arg env "$env" --arg image "$IMAGE" '
    (.containerDefinitions | length == 2) and
    ([.containerDefinitions[].image] | all(. == $image)) and
    ([.containerDefinitions[0].environment[] | select(.name == "Database__SecurityProfile") | .value] == ["validated-v2"]) and
    ([.containerDefinitions[0].environment[] | select(.name == "APP_ENV") | .value] == [$env]) and
    ([.containerDefinitions[0].environment[] | select(.name == "Database__RunMigrationsOnStartup") | .value] == ["false"]) and
    ([.containerDefinitions[0].environment[] | select(.name == "SQL_TRUST_MANIFEST_SHA256")] | length == 1) and
    (.containerDefinitions | all((.dependsOn // []) == [])) and
    (.containerDefinitions[1].environment // [] | length == 0) and
    (.containerDefinitions[1].secrets // [] | length == 0)' "$TASKDEF_FILE" >/dev/null
done
! render dev 2>/dev/null || exit 1
jq '.profile="legacy-v1"' "$CONFIG_DIR/dev.json" > "$CONFIG_DIR/invalid.json"
! render dev --database-config "$CONFIG_DIR/invalid.json" --sql-trust-manifest "$CONFIG_DIR/dev-trust.json" 2>/dev/null || exit 1
jq 'del(.profile)' "$CONFIG_DIR/dev.json" > "$CONFIG_DIR/invalid.json"
! render dev --database-config "$CONFIG_DIR/invalid.json" --sql-trust-manifest "$CONFIG_DIR/dev-trust.json" 2>/dev/null || exit 1
! render prod --database-config "$CONFIG_DIR/prod.json" --sql-trust-manifest "$CONFIG_DIR/dev-trust.json" 2>/dev/null || exit 1
render dev --database-config "$CONFIG_DIR/dev.json" --sql-trust-manifest "$CONFIG_DIR/dev-trust.json"

jq -e --arg image "$IMAGE" '
  .family == "demo-dev-app-api-blue"
  and .executionRoleArn == "arn:aws:iam::123456789012:role/demo-dev-app-api-blue-exec-role"
  and .taskRoleArn == "arn:aws:iam::123456789012:role/demo-dev-app-api-blue-task-role"
  and (.containerDefinitions | length == 2)
  and (.containerDefinitions[0]
    | .name == "demo-dev-app-api-blue"
      and .image == $image
      and .essential == true
      and .secrets[0].valueFrom == "arn:aws:secretsmanager:us-east-1:123456789012:secret:demo/dev/app/db-connection-string-AbCdEf:::00000000-0000-4000-8000-000000000001"
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

# Exercise the production registered-definition consumer with the real rendered
# payload. Only the ARN normally assigned at registration is synthesized.
(
  # shellcheck source=scripts/ecs-readiness-gate.sh
  source "$ROOT_DIR/scripts/ecs-readiness-gate.sh"
  TASK_DEFINITION_ARN=arn:aws:ecs:us-east-1:123456789012:task-definition/demo:42
  IMAGE_URI="$IMAGE"
  APP_CONTAINER=demo-dev-app-api-blue
  PROBE_CONTAINER=demo-dev-app-api-blue-readiness-probe
  registered_payload="$(jq --arg arn "$TASK_DEFINITION_ARN" '{taskDefinition:(. + {taskDefinitionArn:$arn})}' "$TASKDEF_FILE")"
  # shellcheck disable=SC2317 # Called by the sourced production validator.
  aws_capture() {
    [ "$2 $3" = 'ecs describe-task-definition' ] || exit 98
    validate_aws_response describe-task-definition <<<"$registered_payload" || exit 99
    printf -v "$1" '%s' "$registered_payload"
  }
  validate_registered_definition
)

[ ! -s "$SENTINEL_FILE" ] || { printf 'Renderer test escaped to AWS.\n' >&2; exit 1; }

printf 'Task definition readiness-probe contract passed.\n'
