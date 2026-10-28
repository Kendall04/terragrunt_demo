# Portable Sentinel: proposed native trial, not deployment authority

Historical proposal: current security/retirement contracts and the **69-resource
mock** inventory supersede the 62-resource checkpoint below; see [README](README.md).
The immediate next gate is [E16 PLAN-ONLY](PLAN-ONLY-E16.md), without deploying
Sentinel or installing all CI/CD controllers. Earlier amounts remain unapproved.

The executable package is qualified locally from ECS `25f037e04b0e059e868c66b0c8282d410452bfd9`
and upstream `b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828`. It is a managed,
framework-dependent `dotnet10` Lambda ZIP, not the Python controller or SQL-host tar.
`trial/lambda-package.json` identifies the immutable bytes and config. Its hash grants
no permission. The old artifacts, upstream checkout, legacy integration and approvals
remain intact. No cloud operation, subscription or email was performed for this cut.

## Cohost local completion addendum

The portable SQL-host package/bootstrap/publisher wiring is now qualified locally;
see [the paired artifact and real limits](PORTABLE-COHOST-QUALIFICATION.md).
The Lambda ZIP remains unchanged. References below to an unassembled/unselected
cohost publisher describe the prior checkpoint; native installation/transport and
whole-ECS admission remain pending. The USD2 serverless proposal excludes SQL.

## What is implemented and tested

The real original portable Lambda, reducer, ingestion, DynamoDB/S3 adapters, durable
journal, worker, watchdog and cleanup remain upstream code. Three source extensions:
optional SNS rendering, factory forwarding of that renderer, and `MaxAttempts=3`
in this consumer's operational profile (critical retries beyond limit remain false).
The structured notice remains schema2. Human SNS text shows PRUEBA SINTÃ‰TICA, state,
actual reasons, revision/evaluation time and operational IDs, and distinguishes provider
acceptance from inbox receipt. Webhook JSON/default upstream rendering are unchanged.

The wrapper admits exactly one backup Artifact/FULL_COPY_ONLY_CHECKSUM expectation
and one Reported host-telemetry expectation, both Freshness, from `sql-observer`.
A fresh heartbeat does not refresh backup dataAt or prove host/SQL health. Backup
failure/unconfirmed coverage remains UNKNOWN; no invented successful restore.
There are no NAT permissions or NAT execution adapter for these monitors.

Package checks: 116 integrity/extraction checks plus20 in a separate process loading
the extracted ZIP. They construct its real default factory, verify formatter injection,
load the declared Lambda serializer and roundtrip requests for all four handlers,
check three-attempt dispatch and critical limit, reject altered config, then clean
their own temporary files. No handler needing AWS is invoked.22 checks rerun the
actual original Notifications with its exact pinned SDK and a network-rejecting double.
This proves Windows CLR/dependency closure, not Linux/Lambda execution. Three real
Terraform mock-provider plan runs test disabled install, separate activation and ZIP
drift rejection. Provider6.28.0 schema validation has0 errors/warnings. Original source
expansion is115 files with exactly three declared extensions, unchanged package locks.
Upstream's749 declared checks were not rerun and are not our result.

The durable EventBridge publisher is a separately tested local API:20 attempted entries
globally, not20 batches; three per pending entry, stable IDs, partial results, persistent
uncertainty, reservation before transport and fail-closed denied/binding changes.
Prior evidence:19 Windows /18 Linux scenarios and36 real core checks with memory storage.
It is NOT inside this Lambda ZIP or connected to the old installed/proposed SQS timers.
The SQL-host executable/installer portable switch and native producer remain gates.

## Exact proposed scope

Candidate account 341936017254 / us-east-1 / `ecs-portable-r20261026p1`.
Mock plan:62 creations, no updates/deletes. No native IDs, inventory or saved AWS plan
is claimed. `trial/mock-plan-inventory.json` contains every address and type.

| Group | Addresses |
| --- | ---: |
| DynamoDB table (on demand, TTL, indexes, PITR, deletion protection) | 1 |
| Private versioned S3 archive + encryption/public block/versioning/policy | 5 |
| Four roles + four mirrored boundaries + four inline policies | 12 |
| Four Lambdas + four live aliases + three async configs + three invoke grants + mapping | 15 |
| Three queues (reports + two DLQs) and two queue policies | 5 |
| Event bus + four rules + four targets | 9 |
| Four log groups + metric filter + seven alarms | 12 |
| SNS topic/policy/email subscription | 3 |
| **Total** | **62** |

Upstream's55 already contain the durable worker/watchdog/cleanup/alarms; consumer adds
four permission boundaries and three owned SNS resources. Legacy 29 is a different
architecture, not an in-place29â†’62 migration. No CloudFormation, second backend,
EC2 observer, SQL, NAT, VPC, ECR, secrets, CA or new business service. Do not add this
count to historical102 or reuse its USD 6. Implicit Lambda versions, S3 object versions,
log streams, DynamoDB records/PITR storage and subscription generation are lifecycle
obligations even though not separate addresses; real IDs are collected on admission.

Roles: `ecs-portable-r20261026p1-{ingestion,worker,watchdog,cleanup}`;
boundaries: same names plus `-boundary`; inline names are provider-generated on only
those roles and must be recorded. All four boundaries equal their own inline policy.
Functions/aliases use those four component suffixes / `live`; logs `/aws/lambda/` plus
function name. Table `ecs-portable-r20261026p1-state`, archive bucket
`ecs-portable-r20261026p1-341936017254-us-east-1`, bus candidate name, topic candidate
plus `-notices`; queues candidate plus `-reports`, `-reports-dlq`, `-operations-dlq`.
All functions are512MiB,60s. Worker/watchdog/cleanup rules are one minute but disabled
at installation; mapping disabled too. Alarm actions stay independently off by default
even after runtime activation, to avoid seven extra notification paths during the pilot.
Email is a required input, never inferred from `.invalid` in mock tests.

## Access and lifecycle proposal

Existing `cnp-cert-admin` prepares/reverses only an admitted temporary inline for
`TerragruntDemoDevOperator` and exact backend exception. Operator owns all62 resources
via this isolated Terraform/Terragrunt unit. No CloudFormation service role/bootstrap
roles. Four workload roles/boundaries are included in62. Ability to write those policies
can change their contents: names alone are not a limit on policy power; disclose and
review their full JSON before applying. No approval, IAM install or current-policy claim
is implied by the following scope. Preserve global5.100, legacy6.27 and upstream6.70
locks; only the new root pins signed AWS6.28.0.

Workload permissions from the source map are only own DynamoDB reads/writes/transactions
and indexes, own queue Receive/Delete/GetAttributes (ingestion), own operations-DLQ send,
own logs, worker own archive prefix `sentinel/v3/*` Get/Put, worker exact notices Publish;
watchdog reads own state. No workload EC2/SSM/IAM/secrets/KMS/RDS/Backup/original BAK.
The final SQL producer would need only PutEvents to the exact bus with
`events:source=sentinel.report.sql-observer` and detail-type `Sentinel Observation v1`,
plus admitted expiry. This pilot does not grant or install that SQL-role change.

Operator lifecycle scope includes Create/Describe/Update/Delete table, indexes/TTL/PITR/
protection/tags; own bucket creation, policy/encryption/public-block/versioning/lifecycle/
replication/acceleration/tags read callbacks and emptying own objects/versions; own queue
create/read attributes/tags/policy/delete; bus/rule/target put/read/tag/remove/delete;
four IAM roles/boundaries/inline policies and Lambda PassRole; four function code/config/
versions/aliases/async config/invoke permissions/mapping create/read/update/delete;
log-group/stream/filter/retention/export read/deletion; seven alarms; own SNS topic
attributes/policy/subscription/read/publish/delete. Required Get/List/Describe inventories
may expose regional metadata. Known Lambda Get/DeleteEventSourceMapping callback
Resource* exposure must be explicitly disclosed in the final expiring policy rather
than pretending its UUID is an IAM isolation boundary. Do not call any previously
denied action or assume another principal to prove this local proposal.

Proposed existing backend bucket (historical snapshot, not current proof):
`e1-lifecycle-dev-341936017254-us-east-1`, isolated key
`e1/lifecycle/dev/sentinel-portable/ecs-portable-r20261026p1/terraform.tfstate`
and exact `.tflock`, no default workspace writes. Final preflight must read identity,
current policies, actual bucket encryption and concurrency, reconcile manual deletions,
quota/names and compare a real saved plan before consent/apply. If its KMS or Part4/7
denies need a delta, review/hash/reversal and any policy-version loss must be bundled;
the old snapshots are insufficient to generate a truthful installable current IAM delta.
No existing historical version is deleted or permission exception assumed now.

Trial retentions as configured: audit7d/effects7d, queue14d/log30d, versioned archive
without expiry and table PITR. Those are native TTL/retention settings, not permission
to leave data after trial. Proposal requests exporting local evidence then deleting
ALL new synthetic data, versions, records, logs and resources at closure; no new backup
retention. Preserve originals, historical states/receipts/backups2+2d. Keep only terminal
backend state/local evidence, with residual storage reserved for first month.

Retire: stop producer/admitted synthetic publication and disable schedules/mapping/alarms;
export and classify active/due/future/unknown work, DLQ, audits, receipts and archive.
Do not call outbox drained merely because future health checks remain or unsupported
work was ignored. Remove only own table deletion protection with a reviewed saved plan,
purge own archive objects+versions/delete markers, then exact saved destroy; explicitly
reconcile versions/aliases/mapping/targets/queues/subscription/logs/roles/boundaries.
Verify native absence and preserved originals, reverse only own IAM/backend deltas
against current hashes. Retain terminal state and failed/uncertain evidence. No SSH,
SSM retry, force process cleanup or resource substitution.

## Smallest useful native test and cost proposal

Recommend a NEW serverless-only pilot, separate from full SQL/Fargate recovery. It can
test EventBridgeâ†’SQSâ†’authenticated ingressâ†’durable state/audit/outboxâ†’readable SNS,
replays/duplicates and scheduled watchdog without any RunCommand operation. Explicitly
authorize operator synthetic PutEvents only to this bus/source if selected; it does not
execute the denied SSM command or prove SQL-host IAM/timers/backup. The observer's full
cohost path and full ECS LIVE 30min window remain separate future acceptance.

Install disabled, confirm NEW SNS subscription natively before activation. Use at most
20 attempted entries (usually two paired observations/four entries): stale backup plus
fresh telemetry opens one attention episode; fresh valid synthetic backup plus fresh
telemetry resolves the SAME incident. Delays/UNKNOWN/duplicates must not create false
health; cap three durable notice attempts, provider duplicates possible. Validate
original delivery/audit IDs and accepted SNS MessageId separately from user inbox
evidence. Keep telemetry fresh within20min until stop; do not create a second host-loss
episode merely by waiting. Review native backend for30min if user is available; never
keep infrastructure awaiting inbox confirmation. Alarm actions remain off in this
bounded pilot. Real alarm delivery and SQL host-loss recovery remain explicit probes.

Proposed new budget **USD 2**, no previous budget carried/reset. Target 2h, stop active
diagnosis/triggers by 4h, reserve 90min retirement, absolute 24h INCLUDING cleanup.
24h is a cleanup ceiling, not permission for 24h of active schedules. Without free tier,
conservative compute envelope: three schedules/minute Ã—330min Ã—60s Ã—0.5GiB =29,700GB-s;
plus100 ingestion invocations at full timeout =3,000GB-s; total32,700 Ã—
USD0.0000166667 â‰ˆUSD0.545, requests <USD0.001. Budget allowances (not claimed unit
tariffs): DynamoDB/PITR0.40, logs/seven alarms0.15, SQS/EventBridge/SNS0.10,
S3/backend first-month residual0.10, contingency0.704 =>USD 2.00. Assumes at most20
entries, â‰¤100MiB logs/archive and bounded payloads, no provisioned capacity/pollers,
no cross-account/network/service extras. Review rates in the actual region at admission;
stop early on unexpected traffic, retries/storage growth or projected reserve erosion.
This estimate is not an automatic invoice cap or measured charge.

Official pricing references checked2026-10-26: [Lambda](https://aws.amazon.com/lambda/pricing/)
(GB-s/request formula), [EventBridge](https://aws.amazon.com/eventbridge/pricing/)
(custom ingestion USD1/M; same-account service delivery free),
[SQS](https://aws.amazon.com/sqs/pricing/) (request/chunk accounting; no unrelated MCP
blog), [DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/), [SNS](https://aws.amazon.com/sns/pricing/),
[S3](https://aws.amazon.com/s3/pricing/). Non-Lambda categories above are reserved
allowances rather than a falsely precise quote from dynamically rendered tables.

## Remaining real gates

1. Current read-only identity/IAM/backend/names/manual-deletion reconciliation and real
   saved plan, expiring access JSON/reversal plus fresh grouped spending/data/email consent.
2. Native managed-dotnet10 Lambda handler execution, DynamoDB/S3 atomicity, retries,
   ACK/redelivery, durable watchdog and readable SNS/inbox. Local mocks prove none of those.
3. Native acceptance of the now locally qualified SQL-host package/boot/timer wiring
   and producer role, authenticated
   EventBridge publication without persistent laptop credentials; loss/regain of telemetry.
   No need to recreate a dedicated observer just to test the serverless consumer.
4. SQL fencing/restoreâ†’Fargate/public service recovery is still a distinct gate. SSM's
   historical AccessDenied remains unresolved; no alternate transport/principal used.
   No native clean deployment, actual RPO/full RTO or full ECS completion is asserted.
