# Sentinel/backups: minimum operational trial proposal

Status: **local preparation only; NOT DEPLOYABLE or authorized to execute**.
Review date: 2026-10-23. ECS base `ae6807630284ac37d83f7fdbf40a4fab7cffa7a2`.
No AWS calls, credentials, services/timers, publication or email were used here.
The [scope/permission matrix](OPERATIONAL-SCOPE-PROPOSAL.json) has concrete proposed
names and deliberately unresolved decisions. It is not a CloudFormation template
or an installable IAM policy. Existing closed recovery cycles stay closed.

## One bounded source trace

Pinned source: `Kendall04/reliability-sentinel`, commit
`0e8fc55333ddde3b9816885915310a7e69f3de45`, local checkout
`task-3/integrations/reliability-sentinel`. [Source pin](upstream-sources.json)
and `verify_sources.py` verify origin, HEAD and tracked cleanliness without fetch.
All upstream paths below are relative to that commit. PKI is outside ECS scope.

| Stage | Existing original implementation | Actual ECS gap |
| --- | --- | --- |
| Observation | ECS `operations/sql-backup/observer.py`, producer/check CLI, private dedupe state and inert units | Real independent host/role/receipt failure ingestion/expected-UP/cadence remain uninstalled. `replay` is synthetic. Actual `run` requires EC2-role/IMDS and a real check command; it cannot be relabeled a Lambda-native remote check. |
| Authenticated ingress | `src/Sentinel.Worker.Lambda/Function.cs`: exact SQS ARN/source, unique IDs, batch limit 5, partial ACK, deadline token; AWS role credentials | JSON producer/account labels are not authentication. A dedicated IAM-only sender + exclusive SQS queue must bind the configured subject/key. Host accepts only IngestionProcessor; ECS BackupIngress suppression-aware facade is not connected. |
| Normalize/evaluate | ECS ObserverNormalizer/BackupIngress/BackupIncidentPolicy; original IngestionProcessor/SignalProcessor/IncidentReducer | Original RuntimeComposition hardcodes NatRecoveryEvaluator and EventBridge/native NAT normalizers. No-catalog route accepts synthetic EventBridge envelopes, not raw observer JSON. Passing Emit=false directly gives poison/retry instead of valid suppression; dropping every Emit=false loses the required second genuine HEALTHY confirmation. |
| Durable state/receipt/audit/outbox | `src/Sentinel.Persistence.DynamoDb/{DynamoStore,PhysicalLayout,DynamoQueries,CommitValidation}.cs` | Original store is reusable, not NAT-specific. Replace the current **memory fake**, keep original transactional CAS/receipt reconciliation. Pass identical explicit StorageLimits to DynamoStore **and** SignalProcessor: existing managed composition omits the store argument and otherwise retains defaults. |
| Dispatch/archive | Original `OutboxDispatcher`, `EffectRouter`, `DeferredCheckAdapter`, `S3ArchiveAdapter` | Original lease/fence/known-result completion and immutable conditional S3 PUT + checksum/readback are reusable. Backup-only scope/epoch validation and host wiring remain. DeferredCheckAdapter performs logical evaluation only; it does not run an observer/checker. Functional-probe work has no backup worker; preserve/report it pending, never ACK it as executed or send it to NAT. |
| Notice | OperationalWorker routes EscalateIncident to **SimulatedNotification**, other incident effects to AuditAcknowledgement | There is **no real email provider** in pinned source. Resolve ACK is an audit ACK, not a recovery email. A small real provider adapter and explicit escalation/recovery notification choice are still required; provider acceptance is not inbox receipt or exactly-once delivery. |

Schema/host boundaries found in this single review:

- Observer JSON schema1, source `SqlBackup.Observer`, Delivery=NONE remains truthful
  even when its receiver later delivers an alert. Never impersonate `aws.*` or
  `sentinel.synthetic`. Adapter metadata is generic and fits original persistence.
- Physical DynamoDB schema3 vs logical stored snapshot schema2 is an intentional
  adapter distinction. Keep the original serializer/revision/receipt identity.
  New candidate business IDs use v2; no implicit migration of old stores.
- ServiceCatalog is **nat-asg only**, permits NAT resource ARN kinds and requires
  positive ProbeSpacing. Backup policy uses zero unused probe spacing and one
  unused required pass; RuntimeConfiguration requires at least two. Do not fake
  a NAT service or weaken the original catalog to insert backups.
- Operational CloudConfiguration explicitly requires **us-east-2**. Its sandbox
  configuration window also maxes at 60 minutes. ECS uses **us-east-1**. The thin
  backup composition needs explicit region/binding qualification; these validators
  must not be bypassed or an old NAT deployment reused unchanged. The 24-hour user
  ceiling is not a reason to silently change a runtime schema/time contract.
- Original defaults: receipt/signal age 7 days, audit 90 days, effects 30 days;
  queues 4/14 days, logs 7 days, retained table/bucket. They are not owner decisions
  for this new trial. Physical `Expires` uses **UTC ticks**, not epoch seconds:
  **do not enable DynamoDB TTL on it**. Original Cleanup index/store controls remain.
  Deleting a stack with Retain does not mean storage is gone.

Local correction in this increment: BackupIngress forwards the invocation token,
checks cancellation before and after suppression reads and retries a cancelled
message, including normally suppressed HEALTHY. **61 real-component in-process
checks PASS**, zero build warnings/errors, installed toolchain/cache only.
Persistence is still upstream memory fake; no SDK persistence test is implied.
The SDK proxy must independently bind the invocation token for every actual I/O.
Normalizer receipt/head reads need the same per-invocation store budget; do not
share an expired token through a warm static normalizer. The local facade still
uses runId=ecs-backup-local; the future managed bridge must supply actual receiver
invocation correlation, not mistake that local label for authenticated identity.

## First useful cycle: durable signal pipeline, no EC2 recreation

Proposed run `ecs-sentinel-r20261023b1`, account341936017254/us-east-1.
Feed at most 20 synthetic observer receipts from the actual replay/transition
implementation through SigV4 SQS, original reducer/DynamoDB receipts/outbox,
original S3 archive and a real notice adapter **after** its decisions/tests are
complete. Distinct subject/key and fresh namespace in the JSON matrix; no original
ECS/EKS table, state, backup prefix, bucket, queue or role is reused.

The original phase5 IaC supplies table/index/bucket/queue/role/mapping patterns;
`tools/continuous_iac.py` is a 42-resource NAT shadow blueprint, not an ECS ready
installer. Extract only the reviewed slice. Proposed inventory: **15 template
resources**, including two optional SNS resources, plus a dedicated CF execution
role and stack object. Table with Due/Active/Cleanup indexes; private versioned
SSE-S3 archive bucket/policy; Standard managed-SSE queue/DLQ/policy; two .NET10
512MB/15s Lambdas, two log groups and two roles; one initially disabled SQS mapping;
conditional SNS topic/email subscription. Inline policies are embedded, not extra
managed-policy resources. Code package lives under the trial bucket's `packages/`
prefix. No NAT/VPC/EC2/SQL, custom KMS key, Scheduler/timer, public HTTP endpoint,
new business service or unrelated account resources. Operator manually invokes a
bounded dispatcher; no continuous scheduling claim.

This qualifies **transport and durable incident pipeline only**. It does not
qualify real remote backup checks, timer independence, missed producer detection,
SQL recovery/RPO/RTO or the full ECS deployment. Unrouted backup read-check work
must stay visible pending; no false all-outbox-drained claim. A later real
observer trial needs its separately reviewed host/permissions/cadence.

## Access delta, including deletion

Nothing below is installed or currently effective. Existing cnp-cert-dev identity
and intended TerragruntDemoDevOperator must be revalidated only in a future
admitted execution. A denial is reported, not bypassed by another principal.
The JSON matrix spells **exact proposed runtime ARNs and action lists**, plus
resource names; unknown mapping/subscription identities stay null:

- Sender: only sqs:SendMessage to the trial queue. No InvokeFunction permission
  for ingress, AWS profile fallback or credentials on the observer host.
- Ingress: own queue ReceiveMessage/DeleteMessage/GetQueueAttributes; namespace-
  bound table GetItem/PutItem/UpdateItem/DeleteItem/ConditionCheckItem; own log
  streams/events. No Scan, other namespaces or outbound notice privileges.
- Dispatch: same table item operations plus Query of its table/three indexes;
  GetObject/PutObject only its immutable archive prefix; own logs; conditional
  sns:Publish to its exact topic. No S3 original backup access or KMS permissions.
- Both new Lambda trusts are only lambda.amazonaws.com. No EC2/ASG/NAT, Secrets
  Manager, SES or IAM runtime grant. Exclusive sender/consumer queue policy and
  TLS-only bucket/queue policies supplement identity grants.

[DynamoDB transactional IAM](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html)
authorizes the constituent item actions; do not invent IAM actions named
TransactWriteItems/TransactGetItems. Use ForAllValues:StringEquals LeadingKeys
plus a non-null guard on item/query access. Preserve original namespace partition
keys, including GSI queries; test positive and foreign-namespace refusal.

Provisioning/retirement scope to compile from the **final** template, not grant
wildcard administrator rights:

| Target | Temporary create/read path | Retirement/reversal path |
| --- | --- | --- |
| Exact named stack + trial change sets | cloudformation CreateStack/CreateChangeSet/DescribeChangeSet/ExecuteChangeSet/DescribeStacks/DescribeStackEvents/DescribeStackResource/ListStackResources/GetTemplate | DeleteChangeSet/DeleteStack, then terminal describe; PassRole only dedicated CF role with PassedToService=cloudformation.amazonaws.com |
| Dedicated CF role; two exact runtime roles | iam CreateRole/GetRole/TagRole/PutRolePolicy/GetRolePolicy, ListRolePolicies/ListAttachedRolePolicies; CF PassRole only those two roles to lambda.amazonaws.com | DeleteRolePolicy/DeleteRole; restore any changed existing inline policy from original hash and read back; no managed attachment or new principal fallback |
| Exact table/indexes | dynamodb CreateTable/DescribeTable/TagResource/ListTagsOfResource; runtime item/query rights above; UpdateTable only if final settings require it | DeleteTable and describe disappearance; export via namespace Query before deletion; no original table alteration |
| Exact bucket and own objects | S3 bucket create/configure/tag/version/encryption/public-access/ownership/TLS policy; package Put/Get only packages/; archive permissions above | ListBucket/ListBucketVersions, GetObject/GetObjectVersion for evidence, DeleteObject/DeleteObjectVersion for **all own versions/delete markers**, delete own bucket policy/bucket; original buckets excluded |
| Exact queue/DLQ | sqs CreateQueue/GetQueueAttributes/SetQueueAttributes/TagQueue/ListQueueTags plus own inspection Receive/Delete permissions | DeleteQueue/GetQueueAttributes; preserve poison/DLQ receipts before deletion; no blanket PurgeQueue |
| Two exact functions/mapping | lambda CreateFunction/GetFunction/GetFunctionConfiguration/TagResource/GetFunctionConcurrency/PutFunctionConcurrency plus Create/Get/UpdateEventSourceMapping; InvokeFunction only dispatch for admitted operator | Disable mapping, DeleteEventSourceMapping/DeleteFunction/DeleteFunctionConcurrency; verify no mapping/function remains; no AddPermission/public URL/VPC role |
| Two exact log groups | logs CreateLogGroup/PutRetentionPolicy/TagResource/DescribeLogStreams/GetLogEvents; runtime own stream writes | DeleteLogGroup after bounded local export/hash; do not claim retention auto-deletes it |
| Conditional exact topic/subscription | sns CreateTopic/GetTopicAttributes/SetTopicAttributes/TagResource/Subscribe/ListSubscriptionsByTopic/GetSubscriptionAttributes | Unsubscribe/DeleteTopic/read back absence. Owner confirms subscription; no unilateral ConfirmSubscription or address inference. |

**Not yet an exact installable provisioner policy:** AWS assigns mapping and
subscription ARNs at creation, and some list/create operations lack resource ARN
scoping. Their narrow service-supported conditions/necessary Resource=* exceptions,
S3 configuration IAM action mapping, full final CF resource requirements and the
named operator policy before/after hashes must be compiled/reviewed with the final
change set. Do not install broad grants to discover them. No existing backend,
state lock or KMS policy exceptions are proposed. No need to reinstall az6 policies.

## Admission, assertions and retirement

Before asking for execution approval, close these **specific** gates:

1. Build the exact pinned managed AWS slice. Required cache gaps are
   AWSSDK.DynamoDBv2 4.0.107.1 / Core4.0.102.10 and Lambda.Core3.3.0,
   SQSEvents3.0.1, Serialization.SystemTextJson3.0.1. Reviewed caches lack them
   (only older Lambda packages/S3 exist). No download/version substitution ran.
   SNS provider is also absent. A controlled dependency restore is a separate
   next local step; never execute unknown remote scripts.
2. Small upstream-host bridge/consumer composition must preserve exact SQS
   authorization/batch/deadline and suppression ACK semantics, reuse the original
   DynamoStore with explicit StorageLimits, BackupIncidentPolicy and fenced
   dispatcher. Add tests for region/config binding, foreign source/queue/key,
   partial batch, deadline/uncertain commit and unsupported work. No NAT worker
   or native-NAT catalog attached. Runtime absence of EC2/ASG permissions provides
   a second boundary; test the source path too.
3. Choose real email provider/recipient and confirm ownership/consent, notice
   policy for escalation **and recovery**, and retry/dedup limits. Proposed SNS
   Standard is an option, not an existing integration. Store provider MessageId
   in the original dispatch receipt where supported; unknown acceptance retries
   can duplicate email. Never mark Confirmed after timeout or claim inbox receipt.
4. Owner decides trial evidence retention/export and deletion, policy parameters
   and logical owner. Existing 1h producer/2h freshness/2+2-day backup retention
   stay unchanged. Observer timer frequency/expected-UP/host are future install
   decisions, not silently selected by this replay trial.
5. Generate exact small template, deterministic package manifest and plan/changeset,
   temporary create **and delete** policies, current authority, resource ownership
   and cost checkpoint. Review new access/spend/destructive consent as one bundle.

After admission, record start/paid-resource times immediately. Target finish in
2 hours, allow up to4 hours including a substantial cleanup reserve; overall
ceiling **24h**. No minute-level approval cutoff; late human confirmation simply
means re-check current plan/authority before starting. There is no automatic
spend cutoff. Stop input and retire early on unresolvable security/authority
failure or projected envelope overrun; ordinary recoverable bugs can be diagnosed
live within the admitted reserve, without expanding scope.

Single finite assertion set: FAILED/MISSING/STALE opens incident; unchanged/reminder
retains epoch and one escalation; exact duplicate after a fresh runtime retains
receipt/audit/revision; UNKNOWN cannot heal; fresh recovery and required second
healthy observation close the proper epoch; recurrence opens new epoch; old/tied/
expired positive cannot heal it. Check malformed/foreign queue/key/NAT poison has
no unauthorized writes; original archive byte/digest readback; dispatcher known
ACK vs unknown result; inspect pending unsupported work; human independently
confirms the designated notice arrived. Counterfactual AWS denials are modeled
locally first, not repeatedly attempted against unrelated resources.

Retirement order: disable mapping and sender; wait for in-flight processing/leases,
record unresolved work/uncertainties; read/export/hash namespace state, receipts,
audits, outbox and exact S3 archive versions plus logs/DLQ evidence to local storage;
verify archive bytes/receipt lineage before destructive cleanup. Preserve original
recovery evidence/states/backups unchanged. If new retention requires retained
cloud data, report its exact names/cost/deletion date as residuals, not CLOSED CLEAN.
Otherwise delete only admitted synthetic objects/versions/delete markers, table,
queues, mapping/functions/logs, topic/subscription and own policies/roles; delete
stack and dedicated CF role in dependency order. Retain defaults require explicit
owned-resource reconciliation. No force cleanup, state edits, clearing pending
rows to fabricate success, or unrelated prune. Reverse every temporary existing-
role change and verify prior hash. Terminal targeted inventory must verify all
owned resources/permissions absent or explicitly retained; uncertain delete needs
read-only reconciliation before any retry. No NAT deletion is involved in this cycle.

## New budget proposal; prior allocations are not a balance

Earlier USD2+USD1+USD1 caps and the closed az5/az6 USD2 aggregate are **historical
authorizations**, not measured spend or a reusable allowance. No billing lookup
was performed; actual past charges/credits and remaining balances are unknown.
This new pipeline cycle needs **new explicit budget approval**.

Propose **USD1 new**, only after the above gates and actual plan are ready. Model
below assumes us-east-1, no free tier/credits, no EC2/NAT/VPC/custom KMS, at most20
input records, 200 total Lambda invocations (512MB,15s worst case), and bounded
manual dispatch/retries. A future approved notice policy must bound actual sends
(the cost reserve of100 deliveries is not permission to send100 messages). Counts include provisioning/inspection where relevant;
these are operating envelopes, not AWS-enforced billing caps. Count consumed
DynamoDB transaction units and GSI writes, not just API requests.

| Meter/envelope | Reviewed tariff or explicit reserve | USD |
| --- | --- | ---: |
| Lambda200 x15s x0.5GB +200 requests | 0.0000166667/GB-s +0.20/million | 0.025041 |
| DynamoDB20000 WRU incl transaction/GSI +10000 RRU | 0.625/million writes +0.125/million reads | 0.013750 |
| DynamoDB20MB, conservatively full month | 0.25/GB-month (ignore free tier) | 0.005000 |
| SQS100000 requests,64KiB accounting | 0.40/million Standard | 0.040000 |
| SNS100 publishes +100 email deliveries | 0.50/million +2/100000 deliveries | 0.002050 |
| Logs10MB ingest +full-month storage | 0.50/GB +0.03/GB-month | 0.005300 |
| S3 packages/archive/versions/requests | explicit USD0.02 reserve, not quoted tariff | 0.020000 |
| Bounded export/data-transfer rounding | explicit USD0.01 reserve | 0.010000 |
| **Modeled envelope** | conditional on these counts/settings | **0.121141** |

USD1 leaves margin; it is not a guarantee against runaway input, retained data,
changed regional prices or taxes. Recheck S3 request/transfer details and exact
package size in the final budget. Use original capacity accounting and local
counters, input cap, no schedule and concurrency2; disable input before any
projected overrun. Do not repeatedly poll billing (which can lag) as a cost guard.
Any additional scope/budget requires a new decision, not reuse of old trial money.

Official sources consulted 2026-10-23:
[Lambda](https://aws.amazon.com/lambda/pricing/),
[DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[SQS pricing](https://aws.amazon.com/sqs/pricing/) and
[AWS SQS rate example](https://aws.amazon.com/blogs/aws-cloud-financial-management/aws-price-list-gets-a-natural-language-upgrade-introducing-the-aws-pricing-mcp-server/),
[SNS FAQ](https://aws.amazon.com/sns/faqs/),
[S3](https://aws.amazon.com/s3/pricing/),
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/).
The small scope/manifest are reproducible preparation; they are neither a saved
AWS plan nor evidence of effective permissions or a delivered notice.
