# ECS upstream integrations — local consumer qualification

The sources are private, independently versioned repositories. No framework source
is copied into ECS, no upstream scripts run, and no package is published. Verified
Git references qualify Sentinel locally; the paused PKI experiment consumes local
packages. Neither is a deployed integration or hosted CI result.

## Provenance

`upstream-sources.json` pins the exact origin and revision. The bounded read/clone
completed after owner-operated official GCM authentication on 2026-10-23:

| Source | Origin | Commit |
| --- | --- | --- |
| Sentinel | https://github.com/Kendall04/reliability-sentinel.git | 0e8fc55333ddde3b9816885915310a7e69f3de45 |
| PKI | https://github.com/Kendall04/service-identity-pki.git | 29a3dfc70a0b1646388c0229212898b4be164afe |

Qualification used separate checkouts under `task-3/integrations/` on the laptop.
`verify_sources.py --sentinel-root ABSOLUTE_PATH --pki-root ABSOLUTE_PATH` refuses a
wrong origin/revision or modified tracked source. It does not fetch, authenticate,
read credentials or execute upstream validation scripts. Supply the source root
explicitly to MSBuild; no machine-specific checkout path is committed.

## Backup observer to Sentinel

`Ecs.Backup.Sentinel` implements the actual public `ISourceNormalizer` interface.
It consumes the existing strict observer JSON directly, bound to one configured
subject and Sentinel correlation key. It never labels events `sentinel.synthetic`
or `aws.*`; the upstream EventBridge normalizer supports synthetic fixtures only.
The caller must authenticate the producer and establish tenant/environment/subject
binding in a future transport. Plain JSON and configured allowlists are not proof
of producer identity. Use a distinct subject/key for a different backup config.

FAILED/MISSING/STALE map to Failure; UNKNOWN maps to TelemetryLost. An emitted
HEALTHY/RECOVERED observation maps to backup-scoped Readiness evidence and safe
metadata. Unchanged/baseline/maintenance observations normally bypass ingestion.
One fresh unchanged HEALTHY check can confirm an AUTO_RECOVERED episode, as
required by the actual reducer; it is not a fabricated second observation. Content-derived IDs remain stable across redelivery; received time is set
by the receiver. Extra/duplicate fields, impossible status/code/severity pairs,
future evidence and false delivery/remediation claims are refused without echoing
payloads. An incoming JSON candidate still truthfully says Delivery=NONE.

The focused executable exercises **real IngestionProcessor, SignalProcessor,
IncidentReducer, receipts, audits and outbox** against upstream
TransactionalMemoryStore. No reducer/outbox is copied. The memory store survives
reconstruction of the processor in this test, not OS/process termination. It is
explicitly an upstream fake, not DynamoDB or durable filesystem storage.

**54 checks passed** with actual ingress/reducer/receipt/audit/outbox components:
opening and persistent incidents, one escalation intent per episode, reminders,
redelivery after processor reconstruction, UNKNOWN, recovery, recurrence, old
recovery replay after a new epoch, second-observation confirmation, late/tied/
expired health refusal and input sanitation. Thirteen fixtures come from the
actual ECS observer transition with synthetic observations. Release build: zero
warnings/errors, no external packages/download in this dependency slice.

### Backup-observer incident policy

No equivalent backup evaluator exists in pinned upstream; its implemented
IRecoveryEvaluator is NatRecoveryEvaluator. The consumer-owned BackupIncidentPolicy
implements that **existing public interface**; original reducer, transaction/
receipt logic and outbox stay untouched. It replaces the old 988063f unqualified
guard. No upstream source was modified.

- FAILED/MISSING/STALE produce a failed backup-health assessment and escalation
  **intent**, retaining one incident/epoch while the condition persists. Reminders
  add evidence without another escalation intent for that episode.
- UNKNOWN remains telemetry uncertainty, never missing/healthy. It cannot close
  an incident; after the explicit incident budget it can escalate as overdue.
- Only current-epoch, backup-scoped, producer-bound readiness observations count.
  Latest observation wins; tied negative/unknown evidence prevents recovery.
  Expired positives have no older-positive fallback. Healthy must be strictly
  newer than failure. This assesses observer-reported backup health, not restored
  database/API availability or NAT functional recovery.
- A fresh later healthy check recovers an escalated episode. For uncertainty-only
  incidents the original reducer first records AUTO_RECOVERED; a second genuine
  fresh HEALTHY observation closes it. Baseline healthy opens no incident.
- Closed episodes recur with a new epoch. Redelivery reloads the original signal
  from the real receipt/audit, preserving its original evidence/epoch/fingerprint
  after a later episode. Missing audit evidence is retryable, never a fake ACK.

The existing RecoveryPolicy schema still requires NatRecoverySettings. This
consumer supplies explicitly unused compatibility values and backup scope labels,
never AWS NAT/EIP/route bindings or successful NAT facts. It never invokes
NatRecoveryEvaluator. Generic ScheduleRecoveryCheck/RequestFunctionalProbe intents
are scoped to the backup observer; no worker/provider/dispatcher executes them.
Do **not** attach these to NAT workers. Future installation needs the backup
read-check worker mapping; no infrastructure repair actions exist here.

Observation max age, incident budget, check interval, confirmation hold and logical
owner are required parameters; their hash versions the policy. Test values are
synthetic, not installed cadence/SLO decisions. Producer one-hour schedule,
two-hour freshness and 2+2-day retention remain unchanged. Existing failure-coverage
labels retain their limits: an unseen producer failure is not disproved by an
independent healthy remote check. Candidate IDs use a v2 namespace for the changed
evidence contract; old persistent stores/policies are not automatically migrated.

### Remaining installation and delivery boundary

Memory persistence is the **upstream fake**, not durable filesystem/DynamoDB.
All outbox work stays pending, EffectsExecuted=0; no email, probe, repair, AWS,
service/timer install or workflow ran. The local observer policy is qualified
against synthetic local inputs only; no new remote backup observation/database
recovery is claimed. Before AWS/install: review the external observer host/failure
domain, actual role/config/producer receipt path, authenticated producer/tenant
binding, cadence/expected-UP/owner, backup-check worker, durable store/dispatch/ACK,
native alarms/logs, supported region and real email provider. Sentinel Notify is
still fake and managed hosts document Ohio; us-east-1 qualification remains open.
Deployment needs its exact plan, retirement access and budget; old USD2 is not reset.

### Reproduce with installed .NET 10 and Python

From this directory, set `SENTINEL_SOURCE_ROOT` to the pinned checkout and `OUT` to
a new disposable directory outside the source repository. Use an empty local
folder `EMPTY_FEED`; no network restore or dependency installation is needed.

```sh
python -I -B verify_sources.py --sentinel-root "$SENTINEL_SOURCE_ROOT"
python -I -B generate_fixtures.py --observer-root ../sql-backup --output "$OUT/fixtures"
dotnet build Ecs.Backup.Sentinel.Tests/Ecs.Backup.Sentinel.Tests.csproj -c Release --artifacts-path "$OUT/artifacts" -p:SentinelSourceRoot="$SENTINEL_SOURCE_ROOT" --source "$EMPTY_FEED" -p:NuGetAudit=false -m:1
dotnet "$OUT/artifacts/bin/Ecs.Backup.Sentinel.Tests/release/Ecs.Backup.Sentinel.Tests.dll" "$OUT/fixtures"
```

Use the same SDK/environment for build and execution; set
DOTNET_CLI_TELEMETRY_OPTOUT=1 and DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1. Nothing runs a
normal ECS API startup, database migration, KMS request or host service.

PKI runtime integration is **paused** after the owner clarified that ECS has one
application and no business HTTP peer. The preserved [compatibility experiment](PKI-EXPERIMENT.md)
is NOT ACCEPTED and is not an existing/deployed microservice. It installs no CA
and changes no existing API, database/KMS or runtime/IaC contract.
