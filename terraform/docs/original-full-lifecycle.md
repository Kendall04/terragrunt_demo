# Retired lifecycle command: stop and inspect

`scripts/original_dev.py` still points here on an ambiguous/failed request.
The E16 orchestrator is retired. Do not retry it, recreate its sessions, replay
an old approval or force-unlock E2. Preserve the original operation UUID, state
versions and evidence; inspect the owning native Terraform state before any
separately authorized operation.

Use the [native lifecycle](native-dev-lifecycle.md) and its current application
handover applicability. Automatic application delivery uses
[the maintained delivery procedure](../../docs/DEV-DELIVERY-DESIGN.md), not this
retired lifecycle. The old procedure is recoverable from Git at
`5b13b448c328241e02ee1432fba221e675e85810`.
