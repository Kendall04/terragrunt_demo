# Cohost wiring review - local proposal, not installation authority

The owner selected local SQL-host producer/observer with external Sentinel. This
increment wires that choice into the actual DEV TARGET and existing Sentinel inputs.
It creates no cloud resource, state, permission, host credential or email subscription.
SSM AccessDenied is preserved; no SSH, alternate document or principal is introduced.

## Actual code path and phased activation

`terraform/modules/target/dev/data/ordinary-main.tf` now appends the fixed
`terraform/infra/data/cohost-bootstrap.sh.tftpl` only when typed `sql_backup_cohost`
is supplied. Null keeps the exact original SQL bootstrap expression/metadata and no
extra bootstrap actions. Original `user_data.sh`, secrets retrieval and SQL installation
recipe are unchanged. The new metadata contains an exact package version/SHA, public
backup/observer settings and two independent activation flags, defaultfalse; no connection
string, password, arbitrary command or secret value belongs in Terraform/user-data.

The authored bootstrap verifies the expected SQL STS role, retrieves only the versioned
package through the instance role, checks returned SSE-KMS/key/non-bucket-key metadata
and SHA256, rejects unsafe archive entries and stages the existing package installer.
It runs no SSM command. Extraction/config writes are confined to a root-private package
directory, identical files are reused and drift/partial uncertainty refuses blind replay.
Provider/SQL diagnostics and credential environment are not printed or copied.

Initial target boot stages verified files; both activation flags default false.
After fresh approval and native external readiness, observer opt-in can start periodic
checks/UNKNOWN heartbeats autonomously without reading SQL credentials. Its target
owns only the observation timer. Producer opt-in is separate, implies observer opt-in,
and verifies the complete admitted credential handoff before starting its own target.
The producer service repeats that private handoff gate at each start. Missing or failed
producer credentials do not block observation. Both targets retain package integrity,
finite-window and root acknowledgement controls; no recovery/fencing gate is relaxed.
The earlier coupled artifact remains historical and cannot silently adopt split semantics:
the new manifest/install receipt require COHOST_OBSERVER_PRODUCER_SPLIT_V1.
The SQL credential helper, cold restore and its unresolved authorized remote transport
remain distinct from this autonomous observer bootstrap. No rejected SSM operation
is retried or substituted by this local correction.
The SQL Ubuntu recipe installs AWS CLIv1; publisher now omits the CLIv2-only
`--no-cli-pager` flag and retains scrubbed `AWS_PAGER`/single-attempt settings. This
fix is port-contract tested, not an assertion that CLIv1 reached SQS natively.
Opt-in metadata is capped at4096 base64 bytes so the authored5216-byte base and
4892-byte cohost template retain headroom under EC2 user-data size; final rendered
bytes with actual values still require admission verification.
No native boot, timer tick or pipeline/provider execution was performed in this increment.

## External watcher is the original deployed path

`cohost.integration` projects only to existing root inputs. Staged inputs select
`enable_observer=false`, create the existing dispatch schedule addresses but keep its
state and ingress disabled. Activation inputs enable ingress and that same schedule.
Both bind mode/role/run/subject/times/deadline/expected-UP exactly to the SQL configuration.
Mismatches, a dedicated observer, premature data-retirement flag, artifact scope drift,
null version and bucket-key context are rejected.

The real declared chain is EventBridge rule -> target -> dispatch Lambda
`Ecs.Backup.Managed.DispatchFunction::Reconcile` -> `BackupObserverWatchdog.Evaluate`.
The real Lambda environment receives `SENTINEL_WATCHDOG_SECONDS` and
`SENTINEL_OBSERVER_EXPECTED_UP`. No new watchdog Lambda, schedule or database is needed.
It measures arrival of committed observations. Lost telemetry is UNKNOWN, not an independent
S3 inspection, failed SQL backup, restoration proof or monitoring of Sentinel itself.
Existing 119 managed-component tests remain the prior SDK-double qualification; they were
not rerun just for these Terraform/bootstrap changes. b1 inbox evidence remains synthetic;
b2/d1 sent no observer events. Full outbox drain and unsupported probes are not asserted.

## Exact proposed access delta

The helper emits review documents, **not** installed policies or effective-IAM proof:

- Role `arn:aws:iam::341936017254:role/demo-dev-data-sql-ec2-role`:
  only `sqs:SendMessage` on
  `arn:aws:sqs:us-east-1:341936017254:ecs-sentinel-r20261025i1-ingestion`,
  with explicit start/expiry and requested-region conditions. No receive/delete/purge,
  SNS direct publish, SQS KMS key, other queues or wildcard is added. Existing queue
  policy already exempts the configured sender ARN from its Deny; same-account IAM
  grant supplies Allow. This affects all sessions of the shared SQL role, not only
  the Unix observer user. No new observer role/profile/boundary is required.
- Package read: `s3:GetObjectVersion` only on
  `arn:aws:s3:::terragrunt-demo-sql-backup-341936017254-fa48a32dc9/terragrunt-demo/dev/sql-backup-artifacts/ecs-sentinel-r20261025i1/<SHA256>/SqlBackup.tar`,
  with exact `s3:VersionId` and the same time window. No ListBucket/GetObject/write/delete
  or additional .bak access. `<SHA256>` and actual VersionId are mandatory admission
  values, not wildcards to install. Bootstrap's STS GetCallerIdentity retains the existing
  SQL role; it does not assume another principal.
- Artifact CMK decrypt: only existing
  `arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced`,
  `kms:Decrypt` through `s3.us-east-1.amazonaws.com` with encryption-context ARN equal
  to that one artifact. The matching key-policy statement, if missing, uses that exact
  SQL principal/context and expiry; no BucketKey-wide fallback or GenerateDataKey for
  the reader. Current bucket/key policies must be read back before admission. Publication
  separately uses the previously proposed publisher rights and conditional encrypted PUT.
- Existing source/restore producer/backup permissions remain under the original review:
  source `.../r20261025i1s/runs/*` and target `.../r20261025i1t/runs/*`, original backup CMK
  and text CMK `50d3fe36-8128-4d09-ac13-8f5536a230a7`. The **SQL role already needs .bak
  reads for native recovery**; sharing that role does not create an IAM-isolated metadata
  reader. Observer code downloads manifests only. No extra .bak prefix, secret read or
  retention change is introduced by this delta. No secret is fetched by the new bootstrap.
- Reverse only these exact run statements after closing, with original hash/concurrency
  checks. Export own pending/budget/evidence first; never delete/relabel old backups or
  states. Do not rewrite approvals to reflect the changed protected source automatically.

The object version/hash is unknown until a new complete runtime archive is qualified and
published under approval. The source review ZIP is not that archive. Existing component
binaries/source receipts stay immutable; an old tar lacks this wiring. This preparation
has not created an upload, VersionId, native identity or owner approval on their behalf.

## Scope, proposed budget and grouped decision text (do not send yet)

Forecast remains **102 Terraform addresses**, including **29 Sentinel addresses** and
zero dedicated observer host addresses. TARGET adds variables/template/locals only; no
new resource declaration. The29 already include rule/target/exact Lambda invocation
permission. An immutable SQL package object/version is an additional out-of-band artifact
in the retained backup bucket, not a new bucket/Terraform address or a free object. Record
its version, storage and encryption in the next packet. Recommend exporting its local hash/receipt then deleting only that new artifact version at closure with the already designated publisher/administrator, explicitly included in the grouped irreversible-retirement consent. Do not change bucket lifecycle or the data backups2+2-day retention. If existing publisher DeleteObjectVersion is absent, disclose the exact object capability as a new delta before installing anything. No such permission or deletion is executed here.
Native saved plans/reuse checks may still change the conditional102 forecast.

Suggested grouped decision after remaining gates: authorize the existing CROSS_AZ integrated
recovery proposal in341936017254/us-east-1, maximum **USD6 NEW**, including creation/test,
30min owner LIVE review, evidence export and full own-resource retirement. All previous
budgets remain closed. Target2-4h, budget estimate allows7.5h including90min cleanup;
absolute ceiling24h is not permission to spend the full24h or an automatic bill cap.
No numerical price was changed/reverified by this local task; refresh official quotes
and committed-cost headroom before admission. No extra EC2 observer charge is included.

Disclose existing Part4/history/backend/operator/Sentinel/factory/network/secret-version
residual deltas from the integrated proposal **plus** this exact SQS/artifact/CMK delta
and the opt-in user-data bootstrap's root execution capability. New protected module/helper
bytes require renewed source/package admission before publication or deployment; old pins
and empty approvals remain unchanged. Do not add automatic authority because local tests pass.
New SNS subscription to the previously selected destination needs native user confirmation
before activation; this document sends nothing. One episode/attention+recovery, <=3 attempts
per notice; producer has <=20 total SQS attempts across restarts (including uncertainty),
<=3 per pending payload. Exhaustion keeps pending evidence and becomes externally UNKNOWN.
At300s cadence20 attempts is roughly100min without retries; allocate LIVE review and
loss/return checks inside that finite budget rather than extending/resetting it.

No request should claim installable/live readiness until current resource reconciliation,
SSM native admission, full immutable SQL+Sentinel artifact qualification and protected
source/runtime publication approvals are satisfied. Stage the bootstrap on the target;
finish approved post-restore credentials, verify external runtime/SNS, then activate through
the approved owner. Do not replace EC2 just to change the activation flag: the staged fixed
entry can be invoked after the native handoff under the original approved execution path.

## Local verification boundary

Linux:83 cases (cohost15, lifecycle12, observer15, publisher16, EC2 provisioning25), no skips.
Three source-backed wiring tests check actual TARGET/Sentinel declarations,29 resources,
real rule->Lambda->watchdog method/environment and compiled inline Python. These are not
mock AWS success. Terraform1.13.4 fmt/parser and Bash syntax/unit-parser checks are offline.
Credential provisioning uses synthetic SQL/cloud ports in disposable root; no host service,
SQL process, secret value, AWS call, IAM simulator, remote workflow or email is involved.
