#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
SYSTEM_PATH="/usr/bin:/bin"

for test_file in \
  "$ROOT_DIR/scripts/tests/test-render-demo-api-taskdef.sh" \
  "$ROOT_DIR/scripts/tests/test-ecs-readiness-gate.sh"; do
  /usr/bin/env -i \
    HOME="${HOME:-/tmp}" \
    PATH="$SYSTEM_PATH" \
    BASH_ENV= \
    ENV= \
    AWS_ACCESS_KEY_ID= \
    AWS_SECRET_ACCESS_KEY= \
    AWS_SESSION_TOKEN= \
    AWS_PROFILE= \
    AWS_DEFAULT_PROFILE= \
    AWS_WEB_IDENTITY_TOKEN_FILE= \
    AWS_ROLE_ARN= \
    AWS_ROLE_SESSION_NAME= \
    AWS_CONTAINER_CREDENTIALS_RELATIVE_URI= \
    AWS_CONTAINER_CREDENTIALS_FULL_URI= \
    AWS_CONTAINER_AUTHORIZATION_TOKEN= \
    AWS_CREDENTIAL_EXPIRATION= \
    AWS_CONFIG_FILE=/dev/null \
    AWS_SHARED_CREDENTIALS_FILE=/dev/null \
    AWS_EC2_METADATA_DISABLED=true \
    /bin/bash --noprofile --norc "$test_file"
done
