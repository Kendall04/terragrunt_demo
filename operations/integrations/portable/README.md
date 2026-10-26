# Portable Sentinel integration - first local contract increment

This is a tested adapter, not an installed/published runtime. Legacy upstream-sources.json,
cohost source131e87b and qualified archives stay unchanged. New upstream pin is explicit
in portable/upstream.json; do not pass its checkout through the old source verifier.

## Implemented

bridge.py maps the existing strict observer candidate to two real upstream Report
entries: backup freshness and host telemetry. Backup LastSuccessUtc becomes dataAt;
receiving an old backup today does not make it fresh. Data identity/runId remains
stable across fresh polls; report IDs remain stable across retry and JSON property
reordering. Both configured resource/generation bindings are validated again by the
real upstream ReportNormalizer. Unchanged healthy checks still produce heartbeats.

Explicit full COPY_ONLY checksum policy is required. The new upstream SQL PowerShell
reporter excludes COPY_ONLY by default and is not installed or used. Current SQL
producer and credential-free observer remain the source. Without producer coverage,
healthy-looking metadata becomes Unknown, not confirmed success. The current producer
receipt FAILED_OR_UNCONFIRMED cannot establish an explicit failure: the adapter conservatively
maps it to Unknown while still opening an actionable incident. It never invents business
impact, RestoreTested, restore success or .bak verification.

Telemetry reports assert only arrival of the observer, not SQL/backup health. Loss of
arrival opens an external insufficient-evidence incident; return alone does not heal
backup health. Portable worker-health watchdog is distinct from this host expectation.
Maintenance emits no report; the external expectation must also be disabled in a future
reviewed plan. This increment does not implement a new maintenance API or silently cancel
monitoring. The example uses the upstream default one qualified pass for freshness;
that is proposed monitor policy, not authority to change installed policy/recovery gates.

The example deployment/consumer are local-only, notifications=false. Account metadata
does not grant access. No arbitrary command/endpoint, credential or secret is accepted.
The adapter only returns entries; it cannot call PutEvents, SQS, SQL or SNS.

## Executed qualification

14 Python projection cases and33 checks through original b3d0b3b ReportNormalizer,
IngestionProcessor, SignalProcessor, MonitorReducer, transactions/receipts/outbox,
MonitorBootstrap and TransactionalMemoryStore pass. Includes pending-work protection,
terminal-chain reconciliation, loss/return, stale/failure/unknown, foreign identity,
replay/deduplication, future data, cancellation and no NAT probes. Explicit timer-input
evaluation exercises the real reducer, not a running cloud worker. The first test draft
incorrectly expected bootstrap to execute pending work; it was corrected to preserve
the actual upstream contract, and a regression now asserts that protection.

Memory store and synthetic receipts are not DynamoDB persistence, native SQL, AWS
permissions, scheduling or inbox proof. The upstream749 tests were not rerun.

prepare_source.py extracts52 exact tracked files from the reviewed Git commit, seven
package-free CLR projects, no upstream scripts. It preserves their original bytes.
The consumer uses the already-installed ECS SDK10.0.402; original upstream global.json
10.0.301 is deliberately excluded from this isolated compatibility slice, recorded in
its receipt. Neither upstream nor machine/global pins are edited. Offline NuGet config
clears sources: no dependencies/SDKs were downloaded. Release compile:0 warnings/errors.
This proves the core slice on Windows, not the complete portable AWS/Lambda/Linux bundle.

Repeat with the reviewed repo scripts, explicit source/output dirs and installed tools:

```text
python -I -B operations/integrations/portable/prepare_source.py --source <clean-pinned-checkout> --output <new-temp-source>
python -I -B operations/integrations/portable/generate_fixtures.py --output <new-temp-fixtures>
python -I -B -m unittest discover -s operations/integrations/portable -p test_bridge.py -v
dotnet restore operations/integrations/Ecs.Backup.Portable.Tests/Ecs.Backup.Portable.Tests.csproj --configfile <own-source-cleared-config> --artifacts-path <temp-artifacts> -p:PortableSentinelSourceRoot=<temp-source>
dotnet build operations/integrations/Ecs.Backup.Portable.Tests/Ecs.Backup.Portable.Tests.csproj --no-restore -c Release --artifacts-path <temp-artifacts> -p:PortableSentinelSourceRoot=<temp-source> --disable-build-servers -m:1
dotnet <temp-artifacts>/bin/Ecs.Backup.Portable.Tests/release/Ecs.Backup.Portable.Tests.dll <temp-fixtures>
```

## Next local wiring and real external gates

This first cut does not switch the cohost installer/timers/publisher from SQS. Next:
bind manifest/bridge to the runtime opt-in; implement durable EventBridge publication,
counting each attempted entry toward20 (not just HTTP requests), FailedEntryCount and
unknown/partial outcomes, persistent IDs and pending data. Preserve root producer gate
and observer independence. Do not enable both legacy and portable transports.

Then wire the real upstream portable Lambda/store/journal/watchdog, and an explicit
readable SNS rendering extension that preserves schema2 revision/evaluatedAt/deliveryId
and immutable evidence. Do not fork a second reducer/outbox or pretend raw JSON is the
readable mail requested. No notices sent by this increment.

Portable Terraform source requires AWS>=6.28 and pins6.70.0; existing ECS roots/locks
remain unchanged. It is not schema-qualified with the older project provider. Review
an isolated compatible provider/tool before preparing the TG unit, without a global
5-to-6 migration. Runtime SDK dependencies, permissions boundaries, new four-role
footprint, SNS ownership, retentions and complete create/read/delete IAM require a
new scoped proposal. Do not copy55 addresses blindly or reuse102/USD6 authority.

No AWS/IAM/backend/state, publishing, Actions, push or SSM/SSH occurred. SSM remains
unresolved; observing backups cannot establish fencing/SQL restore/public ECS recovery.
New cloud trial needs separate actual plan, budget, permissions, LIVE review and retirement.
