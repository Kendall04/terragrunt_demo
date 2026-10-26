# Split observer/producer activation - local qualification

Source commit `f7a96c2479af88fae2a2b2772db18468a399b7a4` corrects the coupled activation. Both flags default
false. Observer activation requires separately admitted external readiness, with no SQL
credential reads. Producer activation additionally requires complete admitted root-side
credential handoff. Separate targets own their separate timers; producer refusal cannot
disable the observer. The service integrity gate remains unprivileged: private handoff
checks occur during root activation, and systemd loads producer credentials. No new
root service or privileged startup command is introduced.

ActivationContract is `COHOST_OBSERVER_PRODUCER_SPLIT_V1`; old packages cannot silently
adopt the new interpretation. No protected approval, caller, CURRENT pin or AWS access
is refreshed by its hash. This change adds zero AWS resource addresses.

## Artifact and evidence

- `SqlBackup-cohost-f7a96c2.tar`, 133672960 bytes,250 payload files.
- SHA256 `e341f4687de937365ed7ee7f618f0679f3c8fbbaff93847f1e600b1d46888dc8`.
- Small source/evidence review ZIP `cohost-split-review-f7a96c2.zip`, 80930 bytes,
  SHA256 `3f8e8a0829dba117b897f37c4ea7fcf9102797349ca30e416b3cff6406ef4cbc`. Binary tar is referenced, not duplicated inside it.
- Receipt folder on the laptop: `task-3/cohost-split-qualification`.
- Previous qualified archive0cabbbb remains byte-identical, SHA256
  `feda7d1495637db751a92d818f4150bc305b7bb72f05431142446a72c16d5984`. Its historical receipts are unchanged.

45 checks execute the actual tar's Linux ELF, install/reinstall in a disposable root,
inspect component identity/dependencies, compare deterministic archive bytes, and run
installed helper paths. The observer starts through a service double without credentials;
a producer attempt refuses before service requests. A healthy synthetic manifest without
a producer receipt stays UNKNOWN, producer failure remains visible, and valid subsequent
evidence permits recovery. Redelivery preserves the exact pending event and refuses
attempt21 across restarts. Tamper/integrity and wrong confirmation cases refuse.

90 Python fixture tests,3 actual declaration/bootstrap wiring tests and119 original
Sentinel/managed component checks with SDK doubles pass. The latter include external
telemetry loss/return, old-replay rejection, persistence/ACK/outbox and no NAT dispatch.
The real systemd255 parser accepts both target/timer graphs. No host timers run.
Terraform fmt check and Bash/embedded Python syntax checks pass locally.

The Linux CLR component is reused unchanged from
`b2bf8d82938e690561a85e45b3ab9e2a383413cf` with pinned original manifest and all31 Linux dependency
versions/hashes matched. Its C# and project source are unchanged. This is not a fresh
compile or resolution of the separately recorded cross-RID restore/cache failures.
Ubuntu24.04 WSL execution is not Ubuntu22.04/SQL-host or AL2023 acceptance. SQL, SQS,
service control and health receipts are explicitly local doubles/replay, not AWS proof.

## Real external gates

The proposed102-address/USD6 cycle remains unapproved. It still requires a fresh complete
scope/permission/retirement packet, identity/policy/backend concurrency reconciliation,
immutable artifact publication with actual S3 VersionId, native Sentinel/SNS/watchdog
readback, bounded owner LIVE review, target Ubuntu boot/timers, real backup/restore,
public Fargate checks and cleanup evidence. No forecast is an actual Terraform plan.

Observer autonomy no longer depends on SQL handoff or SSM. Cold SQL seeding, backup,
fencing, restore/CHECKDB and credential handoff still require a separately admitted
working transport. The b2/d1 RunCommand AccessDenied cause remains unknown; no retry,
SSH, alternate document/principal or new cloud trial was used here. Recovery gates
are unchanged and missing evidence remains UNKNOWN. No claim of full outbox drain.

## Sentinel version boundary before any update

`operations/integrations/upstream-sources.json` still pins the original Sentinel origin
`https://github.com/Kendall04/reliability-sentinel.git` at
`0e8fc55333ddde3b9816885915310a7e69f3de45`.
The original Core/Application/Ingestion, DynamoDb/S3 adapters, outbox and Lambda batch
handler are consumed by project reference from verified prepared source. The sole
explicit upstream-source extension is
`src/Sentinel.Worker.Lambda/Function.cs`, declared in `managed-source-extension.json`:
it preserves batch/deadline handling while exposing the consumer callback for suppression
ACK/cancellation. Its original SHA256 is
`2c45b9cbe6b46b5f299763b58f9641fe37a0a801cc71c60473e3d9a8f73f172e`.
`prepare_managed_source.py` records original/patched hashes in its receipt.

ECS owns `Ecs.Backup.Sentinel/ObserverNormalizer.cs` and `BackupIncidentPolicy.cs`;
`Ecs.Backup.Managed` owns backup composition/settings/functions, cursor/heartbeat/watchdog,
backup-only effect gate/dispatch and readable SNS adapter/text. ECS also owns the cohost
Python producer/observer helpers and final Terraform/Terragrunt deployment under
`terraform/infra/sentinel-backup`. These are adaptations, not upstream features claimed
unchanged. CloudFormation is historical pilot only. No NAT recovery worker is wired.

Before updating, compare the owner's exact new branch/commit with the current pin:
normalizer/evaluator interfaces, event validation/keys/epochs, reducer transitions,
schema3 Dynamo transactions/retention/receipts, discovery cursor and outbox leases,
effect/idempotency/ACK semantics, Lambda batch/cancellation extension, archive contract,
watchdog/replay assumptions and build/runtime/SDK locks. Preserve historic b1 receipts
and verify backup-only/no-NAT routes. The new target is not yet known or imported;
no fetch, pull, merge, source substitution or update acceptance is implied here.
