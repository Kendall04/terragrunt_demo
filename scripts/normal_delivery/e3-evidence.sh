#!/usr/bin/env bash
set -euo pipefail
# Protected wrapper only. E3 owns all readiness decisions and final revalidation.
context_sha256="${1:?context required}"
[[ "$context_sha256" =~ ^[0-9a-f]{64}$ ]] || exit 1
shift
wrapper_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/ecs-readiness-gate.sh
source "$wrapper_dir/../ecs-readiness-gate.sh"
main "$@"
jq -cn --arg context "$context_sha256" --arg cohort "$FROZEN_COHORT" \
  --arg fingerprint "$OBSERVATION_FINGERPRINT" \
  '{schema:"E1_E3_OBSERVATION_V1",context_sha256:$context,
    cohort:($cohort | split("\n") | map(select(length > 0)) | sort),fingerprint:$fingerprint}'
