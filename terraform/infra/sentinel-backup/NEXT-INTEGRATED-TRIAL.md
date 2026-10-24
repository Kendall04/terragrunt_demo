# Next integrated Sentinel/observer trial — proposal only

Status: LOCAL PREPARATION, NOT ADMITTED. No new AWS, recipient, role, subscription,
backend or timer has been created. The previous USD1 cycle is CLOSED; prior ECS
recovery allowances are also closed. This proposal does not reuse them.

## Recommended scope and host

Use one temporary Linux x86_64 t3.micro observer, CPU-credit mode STANDARD, encrypted
8 GiB gp3 root with delete-on-termination, IMDSv2 required, no SSH key and no inbound
security-group rules. Run the existing .NET CHECK executable, Python observer/publisher
and AWS CLI under a dedicated EC2 role. Do not install SQL or run backup/restore.
An isolated public subnet with an ephemeral public IPv4 provides outbound HTTPS;
no NAT, EIP, endpoints, ALB or application-service deployment is needed. Use SSM for
bounded operator commands, not remote-shell credentials. Pin/review the official AMI
and a hashed, existing-toolchain host bundle before the saved plan; no AMI selected yet.
The host slice below is a proposal, NOT implemented by the current pipeline module.

Why: Program.cs constructs NativeSql only for backup/restore. Protocol.Check reads
versioned KMS-protected manifests and local attempt state, so SQL is unnecessary.
S3Store.Connect(--ec2-role) verifies the exact instance-profile role/account; publisher
also deliberately supports EC2 role delivery only. A laptop replay is not this test.
A Lambda wrapper would require changing these real credential/process contracts, not
just deploying the same checker. Recreating az6's two SQL hosts/NAT would add cost and
mix two acceptance goals. Reuse its immutable backup evidence, not its retired hosts.

Use READ-ONLY the exact original native-produced manifest versions still within their
existing retention (and KMS scope), unchanged. Verify their identity/timestamps first.
For this observation-only trial a declared maximum age up to168h can admit a retained
native manifest; this is a test threshold, NOT a change to the production2h proposal.
Never change StartedUtc, BackupVersion, NativeChecksumVerified or invent a backup.
If retained evidence is absent/expired, stop the HEALTHY/recovery assertion: MISSING/
UNKNOWN and transport can still be tested, but real recovery requires a separate native
backup cycle. Do not manufacture a healthy manifest or silently recreate SQL.
A synthetic local failed-attempt receipt exercises observer failure precedence only;
it is explicitly injected data, not evidence that a real SQL backup attempt failed.

## Inventory and ownership

Current implemented pipeline has26 Terraform addresses:

| Group | Addresses |
| --- | --- |
| State | DynamoDB table1 (Due/Active/Cleanup indexes embedded) |
| Archive/code | S3 bucket, versioning, encryption, public block, ownership, policy, code object7 |
| Queues | SQS2, policies2 |
| Notices | SNS topic, policy, email subscription3 |
| Execution | Logs2, boundaries2, roles2, inline policies2, Lambdas2, mapping1 |

Opt-in dispatch rule + target + exact Lambda permission adds3 =29, recommended for
periodic-cursor/watchdog qualification. This is a legacy EventBridge scheduled rule,
not EventBridge Scheduler. Ingestion and schedule remain OFF in source defaults.
Pilot16 + bootstrap3 used a CloudFormation execution role and combined S3 properties;
TF splits S3 properties, owns code and Lambda roles directly. Counts are IaC addresses,
not an equal count of separately billed services. No CloudFormation role in final path.

The proposed observer slice adds12 addresses: VPC, IGW, subnet, route table, default
internet route, association, SG, IAM boundary, IAM role, role inline policy, instance
profile, EC2 instance. Thus the full recommended isolated trial is41 addresses, NOT29.
Embedded root EBS, ENI/public IP, default VPC-created objects and SSM managed-node entry
are indirect dependencies to inventory/retire too. Reusing an existing suitable host
could remove these12, but none is assumed live or available. Do not touch EKS networks.
Host code distribution must use a reviewed exact-object read grant; current archive
bucket policy excludes that role. Prefer an existing artifact bucket's isolated new
object if its actual policy permits; otherwise prepare a strictly scoped amendment
or a separately counted bucket BEFORE consent. No wildcard bucket-policy bypass.

## Exact runtime permissions and lifecycle review

[Runtime policies](modules/pipeline/main.tf.json) are executable source, not an inferred
permission list. Identity policy and boundary match for each Lambda:

- Both: dynamodb:GetItem/PutItem/UpdateItem/DeleteItem/ConditionCheckItem on exact table,
  required non-null LeadingKeys = exact namespace; logs:CreateLogStream/PutLogEvents on
  own function streams. These item actions authorize the original transactional calls.
- Ingest only: sqs:ReceiveMessage/DeleteMessage/GetQueueAttributes on exact ingress queue.
- Dispatch only: dynamodb:Query on exact table/namespace; s3:GetObject/PutObject on exact
  original archive prefix; sns:Publish on exact topic. No GSI Query used by work directory.
- Scheduled invocation: events.amazonaws.com, exact rule SourceArn and account, only
  own dispatch function. No runtime EC2/NAT/IAM/KMS/secrets or automatic infrastructure repair.

Proposed host boundary/inline policy: sts:GetCallerIdentity; sqs:SendMessage on exactly
R-ingestion; s3:ListBucket limited to exact selected backup runs prefix; s3:GetObject /
GetObjectVersion only selected original manifest keys; kms:Decrypt only selected existing
backup key via s3.us-east-1.amazonaws.com and exact original encryption-context prefix;
s3:GetObjectVersion on exact immutable host-code version. No backup Put/Delete, SQL,
secret read or KMS encryption/generation. SSM channel actions ssmmessages:CreateControlChannel,
CreateDataChannel, OpenControlChannel, OpenDataChannel require Resource '*'; ssm:UpdateInstanceInformation
requires its supported scope. These regional metadata/channel capabilities must be disclosed;
do not claim the UUID/instance condition constrains actions that AWS does not support.
Host has no SNS Publish or Dynamo access. An admin diagnostic channel is a separate
operator action, not host permission to execute NAT/EC2 operations.

Lifecycle identity: existing TerragruntDemoDevOperator is the intended executor, with
existing cnp-cert-admin only for reviewed temporary grants/reversal. The root is
administrator-owned; this is NOT permission to assume/use a different principal after
a denial. Prepare exact policy JSON/hashes and effective-permission simulation before
asking for the grouped consent. Read/create/update/delete action checklist:

- S3 bucket/config/tag/policy/version CRUD; exact code/owned-version Get/Put/Delete and
  ListBucketVersions. Existing explicit DeleteBucket Deny needs an exact NEW bucket
  exception if still applicable, original/version-history preservation and reversal.
- DynamoDB Create/Describe/Update/DeleteTable, tag/list/untag; own table/index scope.
- SQS Create/DeleteQueue, GetQueueUrl/Get/SetQueueAttributes, List/Tag/UntagQueue on own2.
- SNS Create/DeleteTopic, Get/SetTopicAttributes, Subscribe/Get/SetSubscriptionAttributes,
  Unsubscribe, ListSubscriptionsByTopic, List/Tag/UntagResource; own topic/subscription.
- Lambda Create/Get/Update/DeleteFunction, code/config, Get/Put/DeleteFunctionConcurrency,
  tag/list/untag, Get/Create/Update/DeleteEventSourceMapping, Add/RemovePermission/GetPolicy.
  Historical mapping Get/Delete callback evaluation on '*' MUST be anticipated, regional
  time-limited broad capability disclosed, no false exact-UUID condition or IfExists.
- Logs Create/Describe/DeleteLogGroups, Put/DeleteRetentionPolicy, tag/list/untag on own2;
  DescribeLogGroups is regional metadata, not an exact-group guarantee.
- IAM own3 roles/boundaries/inline policies, instance profile, Get/List/Create/Update/Delete,
  policy-version/boundary/attachment inspection and safe reversal; PassRole only own2
  Lambda roles to lambda.amazonaws.com and own observer role to ec2.amazonaws.com.
- EventBridge Put/Describe/DeleteRule, Put/Remove/ListTargets, tag/list/untag exact own rule.
- Observer EC2 Create/Delete VPC/Subnet/InternetGateway/RouteTable/Route/SecurityGroup,
  Attach/DetachInternetGateway, Associate/DisassociateRouteTable, Run/TerminateInstances,
  Create/DeleteTags and necessary regional Describe*; SG egress revoke/authorize only own.
  RunInstances exact reviewed AMI, type, subnet/SG/profile and required ownership tags;
  Terminate only owned instance. No Reboot permission is silently included. No DeleteVolume
  workaround: root delete-on-termination, native wait/reconcile for ENI/IP/volume release.
- SSM bounded SendCommand/GetCommandInvocation on exact host and reviewed document;
  DescribeInstanceInformation and DeregisterManagedInstance if native cleanup leaves own
  stale row. No access to other managed nodes or arbitrary maintenance documents.
- Existing backend: exact new state key + .tflock Get/Put/Delete, required prefix ListBucket,
  existing backend key KMS context only if required. Preserve terminal state; no new backend.

This is a scoped API review checklist, NOT an installed/effective IAM policy or a claim
that every6.27 provider callback has passed AWS. Render final policy and host plan before
consent; names/AMI/source objects/backend/effective Deny must be reconciled then, once.
No implicit grant extension on denial. Existing historical resources are read-only except
reviewed temporary IAM/key-policy amendments, all restored with original hashes.

## Parameters and test sequence

Recommend R=ecs-sentinel-r20261024b2, account341936017254/us-east-1; new state identity
sentinel-backup/R/terraform.tfstate. Availability/names have NOT been checked in AWS.
Recommend the previously owner-specified email only if reconfirmed in the new grouped
consent; create a NEW SNS subscription (old topic was retired), user confirms latest
native subscription. No sender identity/SES grant is needed. A SNS subject is a label,
not a custom From address. Never resend an alert only to improve formatting.

Aim2h, ceiling24h from first paid resource; protect90min cleanup reserve and retire
immediately after sufficient proof. No minute-level like/admission deadline. Recommend
rate(1 minute), observer every60s, watchdog180s expected-UP=true only while observer
is intended running, recovery budget120s, fresh evidence600s, resolution hold60s,
reminders0, max3 transport/notice attempts. Finite expiry/retentions explicit; logs1day,
SQS/DLQ86400s, dedup/audit/effects86400s, max signal age600s; remove all new test data
at retirement, preserve originals2+2days and old states/receipts.

1. Review saved create/destroy scope, immutable ZIP/host hash, effective create AND delete
   rights, original policy snapshots and backend identity. Apply disabled; check code
   version/hash/runtime roles. Verify SNS confirmed natively before enabling notices.
2. Real EC2-role CHECK against selected historical manifests -> observer-check admission,
   SQS -> persisted receipt/audit/head/outbox -> immutable S3 readback. Healthy is only
   manifest recency/readability under declared threshold, NOT SQL restore/file verification.
3. Keep the dispatcher schedule OFF initially. Stop observer temporarily, manually
   reconcile to observe the first UNKNOWN watchdog evidence; restart against a controlled
   empty prefix (MISSING), not a healthy source. Keep one continuous non-healthy episode.
   Old native manifests/declared stale threshold and an injected local failed-attempt
   receipt exercise STALE/failure precedence. Do not heal between these conditions.
   UNKNOWN tests observer silence; injected failure is not a real failed SQL backup.
4. Enable the periodic dispatcher for that same active epoch, verify ONE readable
   attention notice with max3 attempts. No invented notification-disable switch exists.
   If an earlier manual reconciliation already sent the notice, count that acceptance;
   do not send another. Repeat one exact event for receipt dedupe. Native cursor progresses
   over>20 work entries if achievable within<=20 external observations; otherwise leave
   multipage native acceptance pending instead of spending meaningless dummy events.
5. Remove synthetic attempt state and return to the same unmodified historical manifest
   selection. Genuine later checker confirmations resolve the episode; verify ONE readable
   recovery notice. SNS acceptance and user inbox receipts are distinct. Stop the HEALTHY
   assertion if original native evidence no longer exists; never fabricate it to close work.
6. Verify heartbeat now reflects actual checks, not synthetic replay; inspect durable
   cursor/lease and reconcile all known due pages. Do not create another watchdog episode
   or a second pair of messages for aesthetics. <=20 external observations total; if a
   second epoch is accidentally opened, pause schedule and report rather than send extras.
7. Active RequestFunctionalProbe has NO supported provider: count/report UNSUPPORTED_ACTIVE
   without claim/attempt. After genuine episode resolution, original CAS cancels obsolete
   intents; classify Pending/Confirmed/Cancelled/Unknown by identity. If an incident stays
   active, export its unsupported Pending work and call this an acceptance gap, not drain.
   Historical trial's10 Pending entries are NEVER retroactively changed by these tests.

## Retirement and evidence

Stop producer and disable rule/mapping; settle/reconcile known inflight work; save exact
queue counts, receipt/audit/incident/outbox/cursor/heartbeat + archive/version hashes and
SNS Publish/inbox distinction. Export UNKNOWN/active work too. Review saved destroy against
same state lineage and ONLY owned resources. Set allow_data_retirement only with approved
irreversible deletion. Export/delete only synthetic owned versions; force_destroy=false.
Remove observer/its SSM row/embedded volume/ENI/IP, mapping/Lambdas/rule/queues/topic/logs,
table/bucket/code and host network in dependency order. No NAT disassociation workaround.
Remove all trial roles/boundaries/profile and temporary lifecycle/backend/KMS grants;
restore originals/default policy documents, preserve replaced version contents and disclose
unrecoverable historical version IDs/dates before consent. Verify native absence separately
from Terraform state/destroy receipt; retain terminal state and evidence. No remote push.

## New cost envelope — estimate, not invoice or automatic cap

Recommend ONE new USD2 total allowance including observer+pipeline and cleanup; previous
USD1/USD2 trials are excluded/closed. No free-tier or credit assumption. Target2h;24h
is maximum authority, not permission to ignore observed usage/cost or cleanup reserve.
Conservative24h modeled envelope (bounds must be checked during execution):

- t3.micro STANDARD24h * USD0.0104 =0.2496; IPv4 24h *0.005 =0.12.
-8GiB gp3, modeled upper rate0.10/GB-month =0.0267/day (confirm regional PriceList before
  admission; official page's0.08 example is not a regional quote). No surplus CPU fee.
- <=1,440 dispatcher ticks plus<=20 ingest invocations,512MiB,15s each:
  <=10,950 GB-s *0.0000166667 + request fees <0.184; no provisioned concurrency.
- Provision USD0.75 combined reserve for transactional DDB/index/storage, SQS long polls/
  retries, S3 requests/storage, two SNS emails/possible duplicates, KMS reads, logs and
  small transfer. It is a planning reserve, not a fabricated service tariff. Bound20
  observations,6 publication attempts,<=1MiB receipts/exports and<=50MiB logs; monitor
  observed capacity/queue growth, do not assume outbox scan pages cost zero.

Modeled sum <=1.331, rounded USD2 gives0.669 contingency. Taxes and unbounded failures
are not silently declared covered by this estimate; actual bill remains unknown until
billing. Retire earlier if projected spend threatens the allowance. A true new SQL
backup/restore, new KMS key, endpoints/NAT or larger host needs a revised model/scope.
Official tariff references checked2026-10-24:
[EC2 T3](https://aws.amazon.com/ec2/instance-types/t3/),
[IPv4](https://aws.amazon.com/vpc/pricing/), [EBS](https://aws.amazon.com/ebs/pricing/),
[Lambda](https://aws.amazon.com/lambda/pricing/), [DynamoDB](https://aws.amazon.com/dynamodb/pricing/),
[SQS](https://aws.amazon.com/sqs/pricing/), [SNS](https://aws.amazon.com/sns/pricing/),
[S3](https://aws.amazon.com/s3/pricing/), [Logs](https://aws.amazon.com/cloudwatch/pricing/).
The current rule is NOT priced using EventBridge Scheduler's free tier.

## Readable notice example and remaining gate

    OBSERVACION DE BACKUP
    ECS Backup Check Trial - Atencion de backup
    Estado: AUSENTE (MISSING)
    Servicio: sql-backup
    Alcance: observer-trial
    Motivo registrado: El observador informo que no hay un commit remoto de backup.
    Codigo del recibo: NO_REMOTE_COMMIT
    Observado (UTC): <actual observation>

    El estado procede del observador de backups. No acredita una restauracion SQL.
    No se ha ejecutado reparacion automatica de infraestructura.
    DATOS TECNICOS: incidente/episodio/efecto/tipo/origen
    Entrega: la aceptacion de SNS no acredita recepcion en el buzon.

Remaining implementation gate: observer host slice and bounded artifact-distribution
policy, exact retained-manifest/backend/AMI identity and effective lifecycle IAM plan.
These are not present in26/29 and must not be hidden in the final approval packet.
Material owner decision is the grouped NEW spend/access/read-of-originals/destructive
retirement/email/24h cycle, not cosmetic parameters. This document requests no consent
and launches nothing. PKI/new API features remain out of scope.