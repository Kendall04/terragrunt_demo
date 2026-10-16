# E16: practical supervised original DEV lifecycle

## Explicit owner authorization and boundary

2026-10-13: retain the complete original architecture. The owner also explicitly
approved transferring exclusive write capability for the five DEV runtime state
keys/locks to one existing human operator role. This is an optional replacement
of DEV lifecycle execution, not a hidden WP5 bypass. Default `dev_operator_arn=null`
keeps the old policy unchanged. The separately authenticated security administrator
selects that ARN in the existing neutral root; E16 creates no role or credentials.
No installation or AWS operation occurred. Main baseline `98fa727032b8837198f8b07e5a09a086359db182`
is integrated; E16 branches from it, not a stacked/unmerged predecessor.

[original_dev.py](../../scripts/original_dev.py) adds `dev` commands backed by
[practical_dev.py](../../scripts/practical_dev.py). The adapter invokes real AWS CLI
and Terraform when subsequently authorized; tests replace only the process port.
Existing WP6 entry commands and advanced E15-C/D/E/F/G/H mode remain available and
unchanged. E16 never writes/releases E2 or claims a protected closure certificate.

The [existing foundation generator](../../scripts/tests/security_root/wp5.py)
adds optional exact DEV state/lock policy statements. Selected mode denies ANY
other principal, including WP5/admin, Put/Delete on those ten objects. The operator
gets only five state/lock Get/Put, lock-only Delete, prefix-limited List and backend
metadata reads; other objects and backend administration/version deletion are
explicitly denied, including deleting the five state objects themselves. TLS/privacy/encryption/versioning remain. PROD policy and DEV
policy with null selection evaluate identically to baseline. The neutral security
state is outside this grant. Shared/secrets state, evidence, ECR and security-root
identities retain their authority. Provider/schema and live IAM enforcement are
still unverified. The operator validates exact installed deny before any plan.
The optional controller-compute policy admits read-only access to the versioned
DEV E2 application head and the three E13 duty prefixes. It grants no E2/journal
write/delete, release, takeover, public configuration or PROD observation. Original
WP6 request restrictions remain. This read exception must be installed alongside
the selected state policy; absence/AccessDenied stops the operator.

Simplified DEV-only contracts: one human, S3 lockfiles, sequential per-layer
saved-plan review/apply; no common five-plan generation, E2 whole-run ownership,
E15-C single-use service or distributed executor certificate for this mode. Every
layer has a new readable/binary plan and explicit confirmation. SQL deletion has
an independent confirmation. E2 ACTIVE/scheduled cleanup, active protected builds,
reactivated entry functions, known E13 UNKNOWN effects or incomplete observations
block rather than become success. A single operator must not run concurrent
commands or restore inhibited controllers while this session is active. Terraform
locking serializes each state, not a transaction across all states.

## Original topology is unchanged

Original roots `terraform/modules/target/dev/{global,data,platform,apps,edge}`;
original backend `e1-lifecycle-dev-A-R`, keys `e1/lifecycle/dev/L/terraform.tfstate`,
S3 locking/versioning/encryption, default workspace. Workspace listing uses a
per-layer prefix under `terraform.tfstate/workspaces`, covered by the existing
narrow List grant; alternate workspace object writes remain denied. The wrapper
checks the installed backend prefix and rejects non-default workspaces. No root replacement/import or
state migration. The working copy is a private execution artifact, not another Git
clone/worktree/VPC. All source bytes/locks are checked against the clean reviewed
commit, extra nested Terraform files are rejected, and source is not regenerated
at apply. State/plan addresses are derived from original declarations/modules.

Four subnets (two public/two private), both NAT ASG slots and E13 recovery, internal
ALB, ECS/Fargate blue/green, Gateway/VPC Link, EC2 SQL Express, KMS/secrets and
CI/CD remain. Cloud Map remains absent. Skeleton services stay at zero tasks;
WP4 still owns task revisions/counts/listener forwarding. Runtime fields cannot
be changed by an UP update. No protected resource type may enter this lifecycle.

## First empty-account installation, staged without invented IDs

1. Owner chooses account, region and existing scoped human role/session profile.
   Administrator establishes the separate neutral security backend and installs
   existing durable KMS/secret metadata/profiles/roles/control storage and lifecycle
   buckets, promotes genuine protected output candidates. Existing E1 publication
   and protected-root controls are mandatory; E16 does not install them or acquire
   admin authority. Shared SNS and password secret values are installed separately.
   SQL values use existing secret bootstrap outside Terraform; no values in this
   config, argv, preview output or state. E2 application head must be genuinely
   initialized/released by the existing admin bootstrap.
2. Administrator inhibits existing WP5 DEV gateways/builds, observes E2 RELEASED,
   installs reviewed DEV execution permission scoped to runtime only and selects
   `dev_operator_arn`. The state deny enforces one writer. Absent WP5 projects need
   not be installed: real ListProjects/ListFunctions readbacks distinguish absence
   from access failure. Retained WP3/WP4 app deployment requires its own installation.
3. Configure JSON outside the checkout: schema `E16_SUPERVISED_DEV_V1`, environment
   `dev`, exact account/region/profile/operator_arn/source_commit, and `variables`
   keyed only by runtime layers. No account, AMI, budget, password or ARN default.
   `variables.data.protected_sql_ami` is an approved Ubuntu 22.04 x86-64 AMI;
   original SQL sizing/disk defaults remain. Identity/root/dependency/backend
   substitutions are rejected. Security references come from admin-promoted source.
4. `init` copies tracked original roots/lock files and initializes the exact five
   state keys with the named identity. Initial `bootstrap-network-plan` reviews the
   ORIGINAL global VPC/subnets/ALB/EIPs/route tables with NAT launch bindings empty.
   Apply its exact plan; output is NETWORK_ONLY, never full UP success.
5. `bootstrap-status` exposes real IDs from state/readbacks. Administrator uses
   those subnet/SG/EIP/route IDs in EXISTING security-root NAT launch/template and
   E13 handler installation. Handler readiness/version/configuration publication
   is still a genuine admin operation, not a user-supplied success flag.
   Update `variables.global.protected_nat_launch` with both exact a/b launch IDs,
   numeric versions, corresponding subnets and the existing recovery admission.
   A new global up-plan/apply creates the two ASGs in the SAME global state.
   Stage variable changes are allowed only before a new plan; config/hash changes
   after review reject apply. If protected source promotion changes the commit,
   preserve the old session and initialize a new reviewed execution directory.
6. Per-layer UP plans global -> data -> platform -> apps -> edge. IDs for data,
   apps/edge are resolved from previous states only after creation. SQL requires
   current password-version metadata before its plan. After real SQL IP/bootstrap,
   administrator seeds/publishes connection string; apps requires current metadata.
   A partially populated state never marks a layer complete: the operator still
   reviews its current plan and verifies resulting address inventory.
7. Qualify/build the actual .NET image via existing WP3 `release` workflow and
   independent finalizer, then existing WP4 `deploy-dev` using a qualified release
   ID/digest. Existing entry `original_dev.py release/deploy` can be used inside
   approved WP6 jobs; personal credentials do not borrow those identities. No new
   CI/CD platform or direct push into protected ECR is introduced. This handoff
   remains part of the supervised workflow; `dev up-plan` does not deploy images.

This removes the requirement to publish all seven WP5 input graphs/resource IDs
before runtime creation. Durable security setup still requires the existing
administrator; its adapters/provider/runtime installation must be tested in AWS.
SNS discrepancy corrected only for DEV: three E13 alarms now point to the actual
`demo-dev-shared-alerts`. PROD still resolves `demo-prod-alerts`. No topic rename,
policy expansion, subscriber invention or alert-delivery claim.

## Commands, never executed against AWS in E16

Linux/WSL (original tool/bootstrap conventions), Python, Terraform 1.13.4 with
reviewed providers already available for the future session, AWS CLI, curl;
existing WP3/WP4 tool/image prerequisites remain. Restrict permissions of the
external session directory: private plans/state metadata must not be committed.

```bash
dev() { python scripts/original_dev.py dev "$@" --config /private/dev/config.json --directory /private/dev/session; }
dev init
dev bootstrap-network-plan
# Read the full actual Terraform preview and private preview.json/binary.
dev apply --plan-id <id> --confirm '<exact APPLY DEV account region layer binary-hash>'
dev bootstrap-status
# Existing administrator installs NAT/recovery and provides actual launch inputs.
dev up-plan
dev apply --plan-id <new-id> --confirm '<exact printed confirmation>'
# Repeat review/apply through data/platform/apps/edge; interleave secret bootstrap.
# Run existing WP3 release and WP4 digest-qualified DEV delivery.
dev status
dev verify
dev inhibit --confirm 'INHIBIT DEV <account> <region>'
# Inspect ongoing activity/effects; wait only as prescribed by observed service limits.
dev review-inhibition --confirm 'REVIEW SUPERVISED DEV INHIBITION <account> <region>'
dev down-plan
dev apply --plan-id <id> --confirm '<exact DESTROY DEV confirmation>'
# Repeat edge -> apps -> platform -> data -> global; data also requires:
dev apply --plan-id <data-id> --confirm '<exact DESTROY DEV confirmation>' --confirm-sql-loss 'PERMANENTLY LOSE DEV SQL <binary-hash>'
dev residual
```

Plan uses real `terraform plan -out`, locking enabled, `show -json` and readable
`show -no-color`. Apply rechecks identity/backend/source/config/variable hashes,
state lineage/serial/raw hash, plan binary/JSON, original membership and stage.
It applies the SAME saved file, never `destroy -auto-approve` or a silent replan.
DOWN preserves each layer's original vars because earlier dependencies may already
be destroyed. Existing state/readback, tags and exact original address checks are
required. Failed apply/post-readback writes no completion marker and stops advance.
State reconciliation is not a claim of functional readiness or zero residuals.

VERIFY observes Gateway endpoint/VPC Link, ECS services/tasks/probe, SQL instance/
private IP, both NAT ASG members, VPC/default-route/EIP/SDC and app readiness. A
text POST/GET through Gateway/ALB proves actual SQL write/read and KMS encrypt/
decrypt. It still labels per-subnet packet forwarding and SSM bootstrap marker
unverified; capture these through the existing E13/SSM experiment before calling
networking fully verified. RESIDUAL reads current states/tags, instances/volumes/
EIPs/ENIs plus known pre-destroy VPC IDs, classifies retained protected versus
runtime/unexpected resources and reports incomplete/untagged coverage honestly.

## Supervised inhibition, not a remote cancellation guarantee

Inhibit captures prior exact NAT instance IDs and published-version maximum
Lambda timeouts, disables existing DEV NAT EventBridge rule, sets reserved
concurrency zero for callable three NAT functions and DEV lifecycle/deploy/
emergency/cleanup entries, drains both ECS services, suspends Launch/AlarmNotification/
AZRebalance/ReplaceUnhealthy/ScheduledActions/InstanceRefresh while retaining NAT
capacity. After actual ECS STOPPED and normal SQL stop retaining EBS, the
administrator sets both exact ASGs min/max/desired zero. Terminate is NOT suspended. One local UNKNOWN attempt before
commands prevents a blind resend if any response is lost. No controller code,
trust/role, E13 algorithm or protected state grant is altered by these commands.

Destroy previews may be prepared before shutdown and owner approval. Optional
`dev down-plan --layer <edge|apps|platform|data|global>` reviews an existing layer
without changing execution order. Each preview remains bound to its state, source
and exact saved binary; later inhibition or prior-layer deletion may make it stale.
A fresh plan within the disclosed scope must be reviewed before execution.
No preview grants apply authority, and SQL-loss confirmation remains independent.

Before EVERY destructive dispatch: fresh E2/build reads, rule/function inhibition,
unchanged callable inventory, all published timeouts elapsed AND fresh zero
ConcurrentExecutions data or the DEV NAT-only live START/REPORT alternative below
when datapoints are absent (positive/stale metrics still block), exact E13 plan/attempt/
terminal-effect correlation, no retained failure messages, terminal ASG activities,
no native hooks/warm pools/schedules/policies, prior EC2 instances actually terminated,
ECS zero desired/running/pending and complete empty task list. Known UNKNOWN or
reactivation cannot be overridden by the review acknowledgement. DLQ approximate
zero and matching resource snapshots are not alone drain/effect proof.

[AWS reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
limits processing; it does not promise cancellation of an already issued EC2 call.
[AWS async retries](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)
may retain/retry events; keep concurrency zero and rule disabled throughout DOWN.
[ASG process suspension](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-suspend-resume-processes.html)
inhibits future process actions, not retroactive activity settlement.

E16 expressly replaces distributed finality certification with supervised bounded
observations for disposable DEV. It reports `executor_finality=NOT_CERTIFIED` and
retained unobservable-late-effect risk. A stopped executor/terminal journal is not
proof of every possible earlier remote effect. The owner accepts this observational
limit; positively known or ambiguous effects still require manual reconciliation.
If neither fresh metrics nor the narrow live invocation-log alternative is
available, or attributable E13 readbacks are missing, DOWN remains blocked; no
fake zero/finality marker substitutes.
Protected E15-G/H retains its stricter denial and can only run after the explicit
backend policy is transferred back by the administrator with genuine readbacks.

## Failure recovery and costs

| Failure | Supervised next step |
| --- | --- |
| Partial/lost Terraform apply or destroy | Stop. Preserve private plan/state/attempt, inspect status/residual, reconcile AWS IDs versus state. Archive evidence and use a new session/new reviewed plan after resolution. No automatic UNKNOWN settlement or forced unlock. |
| ECS not steady | Inspect exact task/service/deployment/probe/logs; keep current traffic. Use existing WP4 recovery; do not alter ignored runtime fields with Terraform. |
| NAT unhealthy or ASG replacement | Read activity/prior membership/EIP/route/SDC and E13 logs/queues. Do not destroy networking while active/UNKNOWN. |
| SQL bootstrap failed | Use SSM/cloud-init/SQL logs; check two secret metadata/version readiness and private egress. Never dump credentials/state or blind-rotate passwords. |
| Saved plan stale | Reject; prepare a new binary/preview, obtain another confirmation. |
| Partial teardown / observation failure | Keep inhibition. Inspect retained pre-dispatch IDs and parent ENIs. Do not label DOWN complete. |

Reconstruction: new clean execution directory/configuration for the approved source,
same original state keys after independent residual review. Reconcile retained
inhibited NAT/delivery entries with the administrator before UP; no automatic
reactivation of old queued events. Fresh plans recreate original topology, not
another lab. Old private session evidence is retained, never deleted automatically.

Costs: NAT EC2/EBS and two EIPs/IPv4; SQL EC2/EBS; Fargate CPU/memory/time; ALB
hours/capacity; API requests; logs/Container Insights/alarms/flow traffic; KMS and
Secrets storage/requests; ECR and S3 versions/evidence; transfer. DOWN excludes
shared/secrets/security/backend, so those can bill afterward. Discuss a first
supervised session window of 2–4 hours with the owner (not an approved duration or
budget); estimate regional prices, task sizes, instance/storage/image/log sizes
and anticipated transfer before AWS authorization. No price, recipient or $0 claim.

## Remaining first-session gates

Concrete remaining gates: configure exact account/profile/operator/AMI/source;
install durable security/backends and genuine output publication; install the
exclusive policy/runtime API permissions and initialize E2; after network creation,
install/read back actual NAT templates/E13; qualify and install WP3/WP4 delivery.
All have existing ownership paths; no new coordinator. The operator-side loop,
preview/apply, dynamic dependencies and bounded shutdown are implemented offline.
Live IAM/provider/API compatibility, bootstrap, image readiness, metric availability,
inhibition/effect reconciliation and complete residual coverage require the first
separately authorized AWS experiment. No cloud readiness is asserted here.


## Required permission installation, not an installed grant

`A`, `R` and `O` below are the configured account, region and existing human role.
No wildcard service administrator policy is proposed. All mutations require
`aws:RequestedRegion=R`; use exact observed ARNs for existing resources and
`Environment=dev`/`Project=demo` request/resource tags where the AWS action supports
them. ASG slots use their actual Environment/Role/Group tags (original tags do not
include Project). Read APIs that require Resource `*` remain read-only, region
restricted; enumerations cannot be treated as authorization to mutate their results.
The security administrator reviews/installs permissions; E16 never invokes IAM.

| Principal / purpose | Actions | Exact scope / conditions |
| --- | --- | --- |
| O, state/locks | `s3:GetObject`, `s3:PutObject`; `s3:DeleteObject` locks only; `s3:ListBucket`; `s3:GetBucketLocation`, `s3:GetBucketVersioning`, `s3:GetBucketPublicAccessBlock`, `s3:GetBucketPolicy`, `s3:GetEncryptionConfiguration` | `e1-lifecycle-dev-A-R`, five `e1/lifecycle/dev/{global,data,platform,apps,edge}/terraform.tfstate` and their `.tflock`; List restricted to those state prefixes; TLS required; no state/version deletion or bucket administration. Generated selected policy removes other writers. |
| O, protected observation | `s3:GetObject`, `s3:GetObjectVersion`, `s3:ListBucket` | `e1-wp4-dev-A-R/arbitration/dev/application.json` and `recovery/dev/recovery/{assign_eip,change_rt,disable_sdc}/*`; List only `recovery/dev/recovery/*`; no mutation. |
| O, shutdown | `events:DescribeRule`, `events:DisableRule`; `lambda:GetFunctionConcurrency`, `lambda:ListVersionsByFunction`, `lambda:PutFunctionConcurrency`; `autoscaling:SuspendProcesses`, `autoscaling:UpdateAutoScalingGroup`; `ecs:UpdateService` | Exact `e1-wp4-dev-nat-launch` rule, names enumerated by `Session.functions`, `demo-dev-asg-nat-{a,b}` ARNs and both `demo-dev-app-api-{blue,green}-svc` service ARNs; function concurrency only zero, services desired only zero and ASG capacity only zero are operator-code constraints, not claimed IAM parameter conditions. These DEV security-owned entry controls are a narrow administrator-reviewed exception; no role/trust/package edits. |
| O, readback | `sts:GetCallerIdentity`; `lambda:ListFunctions`; `codebuild:ListProjects`, `codebuild:ListBuildsForProject`, `codebuild:BatchGetBuilds`; `autoscaling:DescribeAutoScalingGroups`, `autoscaling:DescribeLifecycleHooks`, `autoscaling:DescribeWarmPool`, `autoscaling:DescribeScheduledActions`, `autoscaling:DescribePolicies`, `autoscaling:DescribeScalingActivities`; `ecs:DescribeServices`, `ecs:ListTasks`, `ecs:DescribeTasks`; `ec2:DescribeInstances`, `ec2:DescribeVolumes`, `ec2:DescribeAddresses`, `ec2:DescribeNetworkInterfaces`, `ec2:DescribeRouteTables`, `ec2:DescribeInstanceAttribute`; `tag:GetResources`; `cloudwatch:GetMetricStatistics`; `apigateway:GET`; `sqs:GetQueueUrl`, `sqs:GetQueueAttributes`; `secretsmanager:DescribeSecret` | Region R; named DEV projects/builds, exact DEV API/VPC Link GET paths, two DEV NAT failure queues and published DEV secret metadata ARNs where supported. No `GetSecretValue`, queue deletion, KMS administration or image publication. |
| O, original Terraform runtime | Existing per-resource create/update/delete/read operations in [WP5 IAM action mapping](../../scripts/tests/security_root/wp5_iam.py), selected only for the five runtime roots | Review the complete actual network/data/platform/apps/edge previews and original action mapping to install the equivalent DEV runtime scope. Creation/tag/PassRole conditions must use existing approved SQL/ECS profiles/roles and observed resource identities; no `iam:*`, shared/secrets root, ECR/KMS/secret/security installation, role trust change or alternative backend. This identity policy is an explicit installation gate, not generated/installed by E16. |
| Existing separate security administrator | Existing security-root installation/publication path | Durable backend/identities, optional state/observation policy selection, actual NAT launch/version/E13 bindings and WP3/WP4 installation; protected neutral state unchanged. |

Before first mutation, verify live policy enforcement denies O on PROD/shared,
other DEV state and evidence writes; denies WP5 on the selected runtime keys;
permits the required state lock create/delete and versioned E2/E13 reads. Also
verify Terraform default-workspace backend listing with the narrow prefix policy
and AWS provider compatibility. Offline console evaluation does not prove these
service-side IAM behaviors. Missing runtime identity policy or failed readback
leaves execution blocked; no broad administrator fallback is offered.


## Completed offline acceptance (2026-10-13)

`e16-practical-dev-accepted-gate-20261013/acceptance.json`, retained outside Git
in the operator's local temporary directory: E1_REPOSITORY_ACCEPTANCE_PASS;
959 regression + 24 WP7 = 983; AC1–AC16 and all 44 suites/checks PASS.
E16 35, original entry 12, E2 41/E2-R 23/E4 28, E13 40, E15-H 54,
E15-G 54, E15-E 49/E15-F 51/combined 39 all passed. Inventory 436 sources;
parsing 191 Python/50 JSON/22 generated YAML. Eight extracted WP5 package
imports, package/authority identities and generated roots/workflows checks PASS.
Terraform fmt and Terragrunt check-only formatting passed; 33 shell files
passed Bash syntax parsing. Static comparison against original baseline: 24
TFLint warnings and 46 MEDIUM/HIGH tfsec findings have identical rule/resource/
message/source-snippet identities and multiplicities; only line offsets moved.
No ignores/suppressions/new findings. Reports: `e16-final-tflint.json`,
`e16-final-tfsec.json`, `e16-static-comparison.json`, outside Git.

The first complete gate failed three static fixtures: two omitted the new
nullable input; NAT still asserted the incorrect DEV SNS ARN. Corrected fixtures
retain their security assertions; the complete gate was rerun successfully.
The bounded self-check also corrected WP4's real probe naming, safe failure-stage
diagnostics and prefix-scoped default-workspace enumeration.

ShellCheck/actionlint and a general YAML parser are unavailable. Generated YAML
is parsed as JSON; unchanged legacy YAML has no new parser result. Windows SDKs
9/10 do not meet pinned .NET 8.0.425 and Docker daemon is unavailable; no new
.NET/Docker test/build ran in E16. App/Docker source did not change. No native
Linux or AWS runtime claim. Provider-free expressions/fixtures passed; AWS
provider schema validation, installation and all live operations remain UNVERIFIED.
No executable source changed after the successful gate; evidence-only documentation
was appended and links/whitespace are checked separately before the local commit.


The [first real DEV session](first-real-dev-deployment.md) records the installed
exclusive writer, authentic DEV-only output promotion and targeted deployment
corrections. NAT DEV's first WP4D binding can now describe only the two real network
slots, without requiring future ECS/cleanup IDs; application and PROD admission
continue using the original full binding. This does not certify installed recovery
or eliminate live E13/readback requirements.

The [first real teardown preparation](first-real-dev-teardown.md) records the
owner-approval boundary, real historical E13/DLQ distinctions and the limited
preview-before-shutdown correction. It does not claim a completed DOWN.


### First-live supervised shutdown correction (2026-10-14)

`inhibit` requests ECS draining and suspends NAT replacement, but now leaves NAT
capacity intact. Observe the actual previous ECS tasks at STOPPED, normally stop
SQL EC2 while retaining its EBS, and only then set the two exact NAT ASGs to zero.
Keep invocation/replacement inhibition until the networking layer is removed.
No database deletion is authorized by an ordinary EC2 stop.

When CloudWatch returns no ConcurrentExecutions datapoints, the three DEV NAT
functions alone may use direct live log observations instead: complete version
inventory with unchanged Text log configuration and bounded timeouts, complete
stream/page reads, each ordered START paired with its REPORT (including async
retries reusing RequestId), no execution after inhibition, and concurrency zero
read back again. Missing/unpaired/late records, changed configuration, unknown
E13 effects, positive/stale metrics and any protected gateway still block.
This is bounded supervised evidence, not an AWS cancellation guarantee or an
executor-finality certificate. E13/CloudTrail effect settlement remains separate.
See [AWS Python invocation logging](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html).

The actual DEV operator installation additionally needs read-only log-stream and
log-event access to the three exact DEV NAT log groups, ListVersionsByFunction
for those three functions, DescribeRule for the one DEV launch rule, and
GetQueueUrl/GetQueueAttributes for the two DEV failure queues. The regional
ASG DescribeLifecycleHooks/WarmPool/ScheduledActions/Policies and CloudWatch
GetMetricStatistics actions require wildcard resources because their APIs do not
support resource scoping; none grants a mutation or a state/IAM write. Exact
account-specific policy is [operator-policy-9.json](../../scripts/first_deployment/operator-policy-9.json).
The existing first two ECS-read statements and all backend writer restrictions
remain unchanged. Installed Part9 v4 has authentic matching readback and no
Access Analyzer findings.

A queue with known failures still blocks the existing execution guard until
those exact messages are independently reconciled and acknowledged with owner
authorization. A versioned evidence archive does not itself authorize deleting
queue records. Never replace this with an approximate-empty or unconditional
success assertion. Explicit per-layer previews read their own state only;
execution continues to recheck all five states and reverse dependency order.


### Partial edge destruction: ordinary state reconciliation

The first saved `edge` apply stopped with explicit AWS errors: DeleteStage lacked
permission-only `logs:ListLogDeliveries`; GetVpcLink after accepted deletion lost
tag-based authorization. Independent AWS reads confirmed the VPC Link absent,
all four routes and the integration absent, with the API/stage/log group retained.
The old failed attempt stays retained and must never be blindly replayed.
The fixes add only regional ListLogDeliveries and read-only GETs on the exact
original API subtree/VPC Link, not a wildcard log-delivery write permission.
AWS documents ListLogDeliveries as permission-only (not a CLI operation):
[CloudWatch Logs authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html).

A deleted resource may still be in partial Terraform state and correctly fail the
normal independent-tag guard. Do not weaken that guard or run `state rm`. Use the
same exclusive DEV operator/backend/locks to prepare a real saved `-refresh-only`
plan, inspect its JSON for no remote mutations and the attributable missing
resource drift, then apply that exact refresh-only plan once. Preserve state
versions and old failed receipts. Once authentic state and AWS agree, initialize
an ordinary new E16 session and review fresh destroy plans for only the remaining
original DEV resources. No new resources, alternate state authority, force-unlock
or unreviewed destroy retry is authorized by this reconciliation.

## Final DEV teardown: native CodeBuild completion field

The final teardown preflight found installed terminal WP4 builds where AWS returns
`buildComplete`, not `buildInProgress`. E16 now checks `buildComplete is True`
and the existing closed list of terminal statuses. Missing fields, active builds,
unknown statuses and incomplete responses still block. This corrects the native
read adapter only; it adds no deployment authority or shutdown exception. The
57 focused E16 tests pass, including real response-shaped terminal/active/missing
field cases. Backend exclusivity, E2, E13 evidence/queue guards, reviewed plans
and independent SQL-loss confirmation are unchanged.


## Final DOWN: exact DEV log readers and unresolved historical SDC evidence

The owner approved extending the existing START/REPORT alternative only to
`e1-gateway-deploy-dev` and `e1-cleanup-recovery-cleanup-dev`. The same complete
version/stream/page inventory, ordered START/REPORT pairing, inhibition timestamp,
configured timeout and concurrency-zero checks apply. Other protected functions,
PROD, incomplete logs and late executions remain rejected. This is supervised
observation, never an executor-finality certificate. The 59 focused E16 tests
pass, including the two exact names and rejection of other protected executors.
Temporary observation permissions must be removed on completion or any stop.
The real operator observation did not pass: ListVersionsByFunction returned an
explicit AccessDenied despite the reviewed temporary reader grant. Readback and
custom-policy simulation matched the intended scope; that simulation is not
proof of effective live access. Both temporary installations were reconciled and
removed immediately after their bounded read attempts. No permission expansion
was used, and C3 is not reported as live-validated.

The final DOWN has NOT been applied. Its historical SDC attempt
`05fc796a-03ae-5e11-8d3b-64a61d144d5d` remains without a terminal observation.
Native evidence read on 2026-10-16 UTC shows the retained FAILURE was written at
01:09:46, before the later attempt at 01:10:51. The two Lambda invocations have
REPORT records, but their errors expose only `E1_WP4D_CONTROL_FAILED`; they do
not identify a pre-dispatch rejection. The complete queried CloudTrail window
contains the independently authorized administrative SDC repair, without a
handler ModifyInstanceAttribute event. That absence, missing ACK and the earlier
FAILURE do not conclusively establish the later attempt's pre-dispatch outcome.
The conditional owner approval for ABSENT cannot be used as proof of ABSENT.
No reconciliation record was written; no historical FAILURE was changed.

Owner authorization C2 was executed only for the exact historic SQS message
`f81a8c2d-195d-4c13-98c6-e591ddc12257`, after authentic ID/body-hash and immutable
S3 VersionId verification. SQS acknowledged its deletion using its current
ReceiptHandle. The versioned archive and all FAILURE evidence remain retained.
No purge or redrive occurred. An empty queue cannot replace effect reconciliation.

C4 teardown grants were not installed while this material C1 gate remained
unresolved. NAT remains at capacity one per slot with replacement processes
suspended; ECS is drained and SQL stopped with EBS retained. These states do not
mean DOWN or zero charges. Saved previews must be regenerated against a clean
source commit before any future apply. Retain backend/locking, protected
identities, neutral WP3/WP4, KMS/secrets/ECR and versioned evidence.


## Owner disposition of the one historical SDC uncertainty

The owner subsequently accepted the residual historical risk for only
`disable_sdc/05fc796a-03ae-5e11-8d3b-64a61d144d5d` in account 341936017254,
us-east-1, solely to finish DEV DOWN. E16 recognizes a local, session-bound
manual decision while preserving UNKNOWN; it does not write any E13 observation,
ACK, ABSENT, APPLIED, SUCCESS or replacement FAILURE. The exception checks the
exact attempt/plan hashes, original FAILURE hash, terminated historical instance,
current config and evidence digest. A different account, attempt, altered record,
active old instance or altered decision is rejected. All remaining controller,
queue, native ASG, ECS, state/lock and exact-plan safeguards still execute.
The 61 focused E16 tests pass. This is not a general recovery/bypass interface.

The temporary C3 grant was subsequently held through IAM propagation and checked
with both a fresh session of the same operator and the original session. Actual
ListVersionsByFunction and START/REPORT observations succeeded for gateway DEV
(8 completed executions) and cleanup DEV (10). Simulation alone was not accepted.
No additional action, trust, account, region or function was authorized.

A subsequent read found the exact authorized SQS message still present despite
the earlier HTTP 200 delete acknowledgement. Visibility zero had exposed repeated
deliveries/ReceiptHandles. After reconciling its unchanged ID/body and versioned
archive, the operator received that single message with 60-second visibility and
used its current handle. No other message was acknowledged; no purge/redrive
occurred. Independent queue readback remains required before teardown proceeds.


### NAT journal inventory scope

The final live guard exposed a GetObject denial on a WP4 cleanup attempt because
it scanned the common recovery prefix as if every journal belonged to NAT.
The NAT effect loop now selects only the three existing exact duties
assign_eip/change_rt/disable_sdc. This matches its documented purpose and installed
read scope; no S3 permission was added. WP4 cleanup remains checked through its
existing E2 owner/schedule, controller completion and exact START/REPORT guard.
Every NAT attempt is still validated; other NAT UNKNOWNs still block. All 62
focused E16 tests pass, including the protected-cleanup inventory regression.
