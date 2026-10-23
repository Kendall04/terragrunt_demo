# ECS backup signal pipeline: local implementation and one-cycle review

**LOCAL QUALIFICATION ONLY. A narrow retirement-policy amendment is ready for grouped consent, not installed.
The AWS cycle is NOT APPROVED and has not run.**

[Part4 amendment, diff, hashes, tests and rollback](trial-review/part4-amendment/AMENDMENT.md)
excepts only this trial bucket from DeleteBucket Deny. Current AWS Part4 remains unchanged.
Its five-version limit also requires explicit consent to preserve/replace nondefault v1;
effective v5 rollback is exact, historical VersionId/CreateDate rollback is impossible.
This document supersedes the initial preparation at commit1ba82c2; its historical
scope/receipt remains in Git. PKI is outside ECS scope. API, original recovery
artifacts/states/backups, EKS, production and original backup2+2-day retention
remain outside this trial.

## Implemented and checked

`Ecs.Backup.Managed` composes the actual Sentinel IngestionProcessor, reducer,
transactional DynamoStore, outbox/fences, DeferredCheckAdapter and immutable
S3ArchiveAdapter. The original SQS Function retains source/queue validation,
batch5, unique IDs, partial ACK and cancellation. A single explicit consumer hook
permits validated suppression ACKs; it is applied only to a verified staging copy
of pinned Sentinel0e8fc55333ddde3b9816885915310a7e69f3de45. The original checkout
stays unchanged. No reducer/outbox or backend is replaced.

The receiver binds account, region, function ARN, queue, subject, key, table,
namespace, archive prefix and topic explicitly. Actual AWS_REGION must equal the
configured region; no CLI profile, alternate endpoint or implicit Ohio fallback.
Only LOCAL_RECEIPT_REPLAY is accepted by this trial host. Normalizer reads and
commit operations use the same invocation cancellation/store retention. Cancellation
also respects trial expiry. A genuine later unchanged HEALTHY observation can
reach the original reducer for confirmation; normal suppression remains a no-op.

The SNS adapter calls the real SDK Publish contract with a fixed topic and
sanitized fields. HTTP200 plus a bounded MessageId confirms **SNS acceptance only**,
not delivery to an inbox. Unknown client/service/timeout outcomes remain unknown;
403 is permanent and causes no alternate access attempt. SDK publish retries are
zero; the original durable dispatcher permits at most3 attempts per effect,
including critical effects. Lost completion persistence after SNS acceptance can
cause duplicates. Tests demonstrate that case, and that a fourth attempt stops.

No NAT provider/RecoveryCheckWorker/WorkActivation is connected. Namespace/key/
policy gates precede external effects, runtime boundaries contain no EC2/ASG/IAM/
secret/KMS permissions, and an unimplemented functional probe stays visibly pending.
The original libraries contain NAT implementations; their presence is not a wired
runtime path. Logical due checks reuse DeferredCheckAdapter and do not run a remote
backup checker. Archive ACK requires original immutable PUT/checksum/readback.

Qualification: managed-host/real-adapter tests use **upstream offline SDK doubles**,
not DynamoDB/S3 services. Existing61 observer/policy memory-fake checks are separate.
Exact NuGet dependencies are locked, restored from nuget.org into the shared cache:
Core4.0.102.10, DynamoDB4.0.107.1, S3 4.0.104.2, SNS4.0.100.17,
Lambda.Core3.3.0, SQSEvents3.0.1, Serialization.SystemTextJson3.0.1.
No framework SDK, container or other toolchain was installed. Initial NuGet path
failures were resolved with required Windows path variables and single non-reused
MSBuild processing; no processes were killed.

## Exact proposed inventory

Account **341936017254**, region **us-east-1**, run **ecs-sentinel-r20261023b1**.
Main stack name equals run. These are19 proposed AWS resources across two stacks;
the two stack objects themselves are additional control-plane objects.

| Main logical ID | AWS type / physical identity |
| --- | --- |
| Sentinel | DynamoDB table `ecs-sentinel-r20261023b1`, original PK/SK and Due/Active/Cleanup indexes; on-demand |
| Archive | Private versioned SSE-S3 bucket `ecs-sentinel-r20261023b1-341936017254` |
| ArchivePolicy | TLS/identity-scoped bucket policy on that bucket |
| Queue | SQS Standard `ecs-sentinel-r20261023b1-ingestion`, managed SSE |
| Dlq | SQS Standard `ecs-sentinel-r20261023b1-dlq`, exclusive source redrive |
| QueuePolicy | Own queue/DLQ policy; direct input sender restricted to admitted operator |
| IngestLogs | `/aws/lambda/ecs-sentinel-r20261023b1-ingest` |
| DispatchLogs | `/aws/lambda/ecs-sentinel-r20261023b1-dispatch` |
| IngestRole | IAM `ecs-sentinel-r20261023b1-ingest-role`, bounded inline runtime policy |
| DispatchRole | IAM `ecs-sentinel-r20261023b1-dispatch-role`, bounded inline runtime policy |
| IngestFunction | Lambda `ecs-sentinel-r20261023b1-ingest`, .NET10/x86,512MB,15s, concurrency2 |
| DispatchFunction | Lambda `ecs-sentinel-r20261023b1-dispatch`, .NET10/x86,512MB,15s, concurrency1; manual bounded calls |
| Mapping | SQS→ingest mapping, AWS-assigned UUID, batch5, partial ACK, maximum concurrency2; initially disabled |
| Topic | SNS Standard `ecs-sentinel-r20261023b1-notices` |
| TopicPolicy | TLS/publisher policy permitting only dispatch role to publish |
| Subscription | Email subscription on that topic, owner address/confirmation pending |

Bootstrap stack `ecs-sentinel-r20261023b1-bootstrap` contains exactly:

1. `IngestBoundary`: managed policy `ecs-sentinel-r20261023b1-ingest-boundary`.
2. `DispatchBoundary`: managed policy `ecs-sentinel-r20261023b1-dispatch-boundary`.
3. `ExecutionRole`: `ecs-sentinel-r20261023b1-cfn`, trusted only by CloudFormation.

The previous15-resource proposal lacked a topic publisher-isolation policy. The
16th main resource closes that gap. Boundaries limit the two new runtime roles even
if an inline policy is changed. CF execution cannot alter those boundaries or its
own policy, remove runtime boundaries, or pass any other role. No existing role
with proven matching trust/boundaries is available in the local evidence; reusing
the broad operator as CF execution would widen service trust. Retain these3 rather
than weaken security to reduce a confirmation. No network/SQL/ECS business service,
CA, Scheduler/timer, EventBridge bus, custom KMS key or historical resource is added.

## Principals, permissions and installation stages

Future Windows profile `cnp-cert-dev` must first prove actual account/principal.
Normal execution is **TerragruntDemoDevOperator** in341936017254. Existing
`cnp-cert-admin` is required only for the explicitly reviewed bootstrap and named
operator temporary-policy installation/reversal. Neither is assumed or used now.
A denial is reported; no unplanned principal or permission expansion is a fallback.

The renderer produces exact JSON templates and separate operator/bootstrap scope
policies. Main CF execution rights include creation, inspection and deletion of
only the named table, bucket, queues, logs, functions, topic/subscription and two
runtime roles. IAM role creation requires its exact boundary; PassRole permits
only those two roles to lambda.amazonaws.com. The operator may pass only the
new CF role to cloudformation.amazonaws.com. No managed administrator attachment.

Runtime grants are minimal: ingress consumes its queue, performs namespace-bound
Dynamo item transactions and writes its own logs. Dispatch performs namespace-bound
Dynamo transactions, immutable Get/Put on its archive prefix, SNS Publish on its
single topic and its logs. The manual dispatcher needs no Dynamo Scan/Query or
NAT rights. The operator can send the finite input set, invoke dispatch, inspect
own logs/queue/topic, read/query the namespace, upload/read the package, export and
delete only the two trial S3 prefixes and their versions, and delete the retained
trial table/bucket after preservation. Namespace LeadingKeys includes a non-null
guard. Transaction APIs authorize constituent item actions, not fictional IAM
TransactWriteItems actions.

Service-driven wildcard exceptions are explicit: creating a mapping requires
Resource=* with exact lambda:FunctionArn/region; assigned mapping UUID actions stay
function-bound. CF also has regional DescribeLogGroups metadata listing because
that provider read has no resource-level scope; no foreign log-content permission.
Mapping tagging is limited to this run's requested tags and known
CloudFormation tag keys; it grants no foreign mapping update/delete. SNS subscription
read/delete IAM is scoped to the **topic ARN**, not a guessed subscription ARN.

Future admitted stages, one approved cycle:

1. Record account/principal, expiry, existing named inline-policy bytes/hash and
   effective authority/inline-size capacity. Confirm neither stack/resource names
   exist and that the complete create/delete scope is effective. Keep originals.
2. Bootstrap only the3 own IAM resources and add the exact named temporary operator
   policy. Read back hashes. The operator policy affects every session of that role
   until reversed. No existing backend/lock/KMS policy changes are needed.
3. Create the main base with DeployRuntime=false. This creates the bucket before
   package publication. Upload exactly the locally pinned ZIP under
   `packages/<ZIP_SHA256>.zip`; record version and compare returned SHA/bytes.
4. Review/execute the main UPDATE change set with DeployRuntime=true and actual
   PackageVersion. A rule forbids the base-only placeholder; final rendering fixes
   PackageKey to the one qualified digest. Mapping remains disabled.
5. Owner confirms the subscription. Confirm its own topic/address/status by the
   exact configured principal, then enable only the known own mapping. No short
   like-dependent admission cutoff. Start the finite fresh receipt sequence.

This is not a saved AWS change set or an effective-permission certification. Those
are future admission checks inside the new reviewed cycle, not performed locally.
CloudFormation/native deletion behavior still needs the actual trial. If a service
needs an unlisted permission, stop that action and report it; preserve boundaries.

## Recommended synthetic defaults and bounded notice plan

These are **recommendations for one grouped decision**, not installed defaults or
changes to producer contracts. Templates require explicit values for them.

| Parameter | Recommended trial value |
| --- | --- |
| NotificationEmail | Owner supplies address and consent; never inferred/stored in Git |
| SenderLabel | `ECS Backup Trial`; this labels subject/body, not a custom From address |
| NotificationMode | EscalationAndRecovery |
| Owner | Kendall04 as logical incident owner |
| EvidenceSeconds / BudgetSeconds / CheckSeconds / HoldSeconds | 300 /600 /60 /0, synthetic policy only; no periodic task installed |
| DedupSeconds / SignalAgeSeconds | 86400 /3600 |
| AuditSeconds / EffectSeconds | 86400 /86400 |
| QueueRetentionSeconds / DlqRetentionSeconds | 3600 /86400 |
| LogRetentionDays | 1 |
| StartsAt / ExpiresAt | Actual admitted start, at most24h later; aim finish within2h and preserve cleanup reserve |
| PackageKey / PackageVersion | Qualified digest key / actual new S3 version, internal publication receipts |

SNS owns the email From address. If a custom sender identity is required, that is
outside this SNS trial; no SES/domain identity/credential is configured here.
Logical24h retention is a ceiling for expiry eligibility if storage remains, not
an AWS TTL guarantee. Normal proposal: export/hash synthetic evidence locally and
explicitly authorize deletion of these new cloud records at trial end, without
changing original SQL backup2+2-day preservation. If owner chooses cloud retention
instead, identify exact residuals/deletion date/cost and do not report CLOSED CLEAN.

Generate receipts using the existing actual observer transition with explicit
`--subject sql-backup-trial --anchor-utc <first-send-UTC>`; historical test defaults
stay unchanged. Do not submit a future ObservedUtc before its time. Send only the
first episode: failed, duplicate failed, unchanged/reminder, missing, stale,
unknown, recovered, baseline healthy and recovered redelivery; optional sanitized
poison negative. At most20 messages. FAILED/MISSING/STALE share one incident;
UNKNOWN cannot heal it. Expect **one escalation and one recovery notice**, plus
one subscription confirmation. Do not send recurrence fixtures in this mail trial.
At most3 Publish attempts per each of the2 notice effects (6 planned attempts);
SNS transport/internal retries can still duplicate delivery. Inspect the original
outbox/message IDs; do not deliberately inject ambiguous real mail outcomes.

Reconstruct runtime between duplicate deliveries to test durable receipts. Check
state/receipt/audit identity, original archive byte readback and SNS MessageId;
operator-received email is separate human evidence. Unsupported functional probes
remain pending; never label them executed or an entire outbox drained. This proves
synthetic durable signal plumbing, not remote backup checks, independent host/timer
operation, producer failure coverage, SQL restore/RPO/RTO or whole ECS availability.

## Retirement and original preservation

Stop sender and disable mapping first. Wait for in-flight processing and leases;
record unresolved/uncertain work instead of clearing rows. Export/read-back/hash
namespace head/evidence/receipts/audit/outbox, exact archive/package versions,
logs and DLQ evidence to local storage. No secret values are present by design.

Delete the main stack and wait through terminal state. Original definitions retain
Sentinel table and Archive bucket deliberately: after verified local preservation
and the bundled destructive consent, **the operator has exact native DeleteTable,
DeleteObject/DeleteObjectVersion and DeleteBucket rights for them**. Reconcile own
versions/delete markers, then targeted absence. No PurgeQueue, ForceDelete, state
surgery, boundary removal or unrelated cleanup. Preserve unexpected keys and report
rather than broadening deletion. All original ECS/EKS resources remain excluded.

After runtime roles are gone, delete bootstrap stack: CF role and its two boundary
policies. Reverse the named operator policy to its exact prior bytes (or remove
only the policy this cycle introduced), read back hash, verify no session retains
new effective access after propagation. Targeted residual checks cover stack
objects, functions/mapping/roles/boundaries, queues/DLQ, topic/subscription, logs,
table and every S3 version. A retained or uncertain resource is a residual, not a
clean close. Record actual creation/retirement/reversal times and final inventory.

## Cost and authority boundary

Propose **USD1 NEW**, not yet approved. Previous trial allocations are closed;
actual historical spend/credits remain unknown and no billing call ran. The old
az5/az6 USD2 aggregate is not reopened or reset.

Without free tier/credits, conservative small-use model: Lambda200 invocations
including30s billed-duration allowance at512MB ≈USD0.050041; Dynamo20000 WRU plus
10000 RRU ≈0.01375 and20MB full-month storage0.005; SQS100000 requests0.04;
SNS100 Publish/email-delivery allowance0.00205; logs10MB ingest/full-month storage
0.0053; explicit S3 request/storage reserve0.02 and export/rounding reserve0.01.
**Modeled total ≈USD0.147**, with margin inside proposed USD1. The100-notification
pricing reserve is not permission to send100 messages. No EC2/NAT/PITR/custom
metrics/alarms or provisioned concurrency. Exact retained size/taxes can vary.

Sources reviewed2026-10-23: [Lambda](https://aws.amazon.com/lambda/pricing/)
(0.0000166667/GB-s,0.20/million requests),
[DynamoDB](https://aws.amazon.com/dynamodb/pricing/)
(0.625/million WRU,0.125/million RRU,0.25/GB-month),
[SQS Pricing](https://aws.amazon.com/sqs/pricing/) and
[official us-east-1 Price List](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSQueueService/current/us-east-1/index.json)
(SKU8RN6B8U4MERHRXP3, version20260911124607: USD0.0000004000/request;
100000 x0.0000004 =USD0.04; no free tier, no MessageGroupId/fair-queue surcharge),
[SNS FAQ](https://aws.amazon.com/sns/faqs/)
(0.50/million Publish,2/100000 email deliveries),
[CloudWatch](https://aws.amazon.com/cloudwatch/pricing/) and
[S3](https://aws.amazon.com/s3/pricing/).
[Publish contract](https://docs.aws.amazon.com/sns/latest/api/API_Publish.html),
[transaction IAM](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis-iam.html),
[Lambda mapping authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_lambda.html),
[SNS topic/subscription IAM](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sns.html).

Input/invocation limits and a manual cleanup reserve are operating controls, not
an automatic AWS billing cap. Account/region, exact access, code digest, email
consent, deletion/preservation, recommended parameters and USD1 must be reviewed
as one future bundle. Nothing in local readiness authorizes that execution.


## Read-only admission finding - 2026-10-23

[Exact preflight receipt](readonly-preflight.json): cnp-cert-dev resolved to
arn:aws:iam::341936017254:user/cnp-cert-admin. Both templates passed actual
CloudFormation ValidateTemplate (CAPABILITY_NAMED_IAM); all consulted names were
absent/free. IAM has capacity for3 roles/2 policies and the4572-character temporary
operator inline policy fits10240 without replacing existing policies. Operator
sessions max3600s; future renewal must use the same admitted role, not expand it.

**NOT READY for execution consent using the current retirement packet:** IAM
simulation with the exact proposed temporary policy returned explicitDeny for
s3:DeleteBucket on arn:aws:s3:::ecs-sentinel-r20261023b1-341936017254, from existing
TerragruntDemoDevOperatorPart4. CreateStack/DeleteStack simulations being allowed
do not cure the native retained-bucket deletion path. No actual DeleteBucket,
role assumption, permission change or alternate-principal attempt occurred.
This needs a corrected, reviewed retirement plan before approval; this preflight
has not changed the templates, principals or policies to bypass the deny.

Official runtime documentation supports dotnet10/AL2023. The existing Python
SDK's Runtime enum lacks dotnet10; the planned CloudFormation-body route does not
use that enum. No SDK upgrade or native runtime qualification is inferred.
The direct SQS tariff leaves the USD0.147 model/USD1 proposal unchanged.
