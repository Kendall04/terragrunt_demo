#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' 'E1_LEGACY_PATH_RETIRED: use the protected E1 workflow request; security/bootstrap requires the separately authenticated administrator.' >&2
exit 1
