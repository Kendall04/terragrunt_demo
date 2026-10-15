# First real original DEV session â€” 2026-10-13

This report records the first cycle. For the current reconstructed environment,
see the [second real DEV cycle](second-real-dev-cycle.md).

Latest checkpoint (2026-10-14): all five original DEV layers are applied and the
public application SQL/KMS round-trip passes, including 4096 UTF-8 bytes. Both
colors, both NAT slots, SQL, internal ALB and API/VPC Link are running. See
[the final functional evidence](#successful-public-functional-verification--2026-10-14)
and [retention/recovery limits](#operating-costs-and-retained-boundary). Earlier
sections below preserve the chronological checkpoints, not current blockers.
Normal GitHub delivery and complete destructive rehearsal remain unverified.

## Verified scope and progress

Profile `cnp-cert-dev`, account `341936017254`, region `us-east-1`.
The bootstrap caller is `arn:aws:iam::341936017254:user/cnp-cert-admin`.
Its pre-existing AdministratorAccess was inspected; this task adds no administrator policy.
The new supervised role is `arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`.
Its trust permits only that existing user, with a maximum one-hour session.

The initial inventory contains unrelated cloud-native-platform resources. They are
excluded. Existing GitHub OIDC is also unrelated and has not been adopted or changed.
The original two-AZ topology is preserved. No reduced lab or Cloud Map is installed.

Installed and observed:

- Security backend `terragrunt-demo-security-341936017254-us-east-1`,
  key `e1/security/terraform.tfstate`, native S3 `.tflock`, Terraform 1.13.4.
  Private, versioned, AES256, BucketOwnerEnforced, TLS and admin-only policies.
  A real saved-plan apply exercised locking successfully.
- 34 DEV-only prerequisite resources from the existing security root: workload
  and NAT roles/profiles, KMS, three empty secret metadata records, immutable ECR
  and the private versioned lifecycle backend.
- DEV coordination bucket `e1-wp4-dev-341936017254-us-east-1` and four protection
  resources, applied from a reviewed create-only five-resource binary plan.
- Authentic 20-record DEV output publication, created conditionally and read at
  its exact returned S3 VersionId before source promotion. The complete 43-record
  publication contract remains available. No PROD/shared references are fabricated.
- E2 initial RELEASED application head, conditionally created and exact-version
  read back; no owner takeover.
- E16 DEV state-writer handoff policies, with installed readbacks. Only the human
  role writes the five runtime keys, including against the admin and WP5 principals.
  Backend administration and state deletion remain denied to that role.

Runtime bucket `e1-lifecycle-dev-341936017254-us-east-1` retains these keys:
`e1/lifecycle/dev/{global,data,platform,apps,edge}/terraform.tfstate` and their lockfiles.
Shared/secrets/security state is excluded from the operator.

KMS key `50d3fe36-8128-4d09-ac13-8f5536a230a7`, alias `dev-kms-service`.
ECR repository `demo-dev-shared-demo-ms` contains the original application image at
`sha256:c53545834f80b1dbe452c2544c4f34243fd4dcc2ba9728d13c41e4861fcee5e6`.
The existing OCI publisher uploaded it from Windows, with exact manifest readback.
No mutable latest tag, VM AWS authentication or WP3 qualification claim is involved.
Secret names are `demo/dev/app/db-connection-string`, `demo/dev/db/sql-app-password`
and `demo/dev/db/sql-sa-password`. SQL SA/app passwords are now generated and seeded
outside Terraform, with exact AWSCURRENT metadata readback. The connection string
is unseeded until a real SQL private IP exists; no value enters Terraform or logs.

## Deployment corrections

Provider validation also found the DEV SQL AMI output referencing a removed data source. It now reads `aws_instance.db.ami`, matching the created instance. PROD source remains unchanged.

The five DEV runtime locks contained an unused TLS provider. Terraform 1.13.4
refused readonly initialization. Those locks now retain only the existing AWS
5.100.0 provider; PROD and shared/secrets locks are unchanged.

An all-environment output publication forced PROD and neutral infrastructure
before first DEV installation. A strictly scoped DEV publication now serves only
DEV consumers whose complete required references are present. It cannot serve
PROD or the shared consumer requiring neutral references. DEV publications are
excluded from PROD lifecycle packages, keeping those package identities unchanged.

A broad controller-module dependency unnecessarily pulled all protected resources
into a DEV bucket plan. Removing that ordering does not remove installation or
activation gates. Some for_each policy dependencies still pull uninstalled PROD
buckets into targeted plans. Those mixed plans were rejected, never applied.
The administrator installed only the two exact DEV policies evaluated by the real
Terraform preview; readback comparison accounts solely for AWS singleton-array
normalization. The security root inputs retain the real operator ARN for subsequent
refresh/review. No PROD resources were created.

Windows provider-local TLS failed despite a valid signed provider. The local
Windows WSL path uses the checked-in Terraform distribution checksum and existing
Windows credential files in place. Nothing is copied to a remote machine.
The operator accepts `--aws-config-file` containing only a same-profile role
configuration and `--terraform-wsl-bin` for that verified local binary. Public
config allows exactly region, source_profile, role_arn, session name, duration and
CA bundle; embedded credentials/credential_process and foreign roles are rejected.

## Operator permission installation

The five [installed policy documents](../../scripts/first_deployment/)
are the reviewed account-specific DEV grants. AWS IAM Access Analyzer checked them;
the installed default versions were read back and compared with the documents.
They derive original lifecycle actions from WP5, restrict creates by DEV request
tags/names, existing mutations by resource tags or fixed DEV names, and every grant
by `aws:RequestedRegion=us-east-1`. PassRole is restricted to the existing DEV
workload/NAT/flow roles and services. They exclude SNS/shared state, PROD,
security state, E2 writes, IAM administration and backend administration.

The first checks exposed two policy-construction issues in the proposed operator
copy: ListenerProtocol requires a multivalue qualifier, and the tagging service IAM
namespace is `tag:GetResources`. The installed documents correct both. This does
not assert that every eventual provider call is covered; actual AccessDenied errors
must be reconciled narrowly against owned resource identities.

## Build and credentials

The VM source directory is `/home/kendall/work/terragrunt-demo-first-dev-build-20261013`.
It is a build artifact directory, without .git, not a clone/worktree. Required source
hashes were checked against Windows before execution; an older VM repository was
not used or changed. Pinned SDK 8.0.425 ran the actual solution: **99 tests passed**.
The original Dockerfile built successfully. Image config digest:
`sha256:2138941d1bcef84204d3d60375b84786f639020e011ef9b22dcb3c95ff33cd8c`.
The packaged readiness-probe capability is available. This is not SQL/KMS readiness.

The VM has no `cnp-cert-dev` authentication. No STS credentials or ECR token were
sent there. The VM exported only a digest-checked OCI artifact to Windows. The existing
publisher uploaded it using Windows authentication, so independent VM AWS
credentials are not required for this publication path.

## Retention and failure safety

Security prerequisites are retained outside five-layer DOWN: KMS, secret metadata,
ECR, IAM, backend versions and coordination evidence. KMS and secret metadata can
incur charges before workloads exist; S3/evidence versions also persist. DOWN does
not promise zero cost or delete these protected resources.

Evidence, binary plans and state stay in the private Windows task directory under
TEMP, not Git. Failed/ambiguous attempts are not retried without readback. The first
runtime apply must use the exclusive E16 role, reviewed source and saved plan.
Reverse order remains edge â†’ apps â†’ platform â†’ data â†’ global, with separate SQL
loss confirmation and real ECS/NAT/ASG inhibition/reconciliation before teardown.
No force unlock or broad account cleanup is permitted.

Provider/runtime and full acceptance results, final runtime progress and any
remaining live blockers are recorded in the session delivery report. The facts
above do not certify a running application or complete DEV deployment.

Historical tests that assumed an entirely empty output registry were updated for
the explicitly authenticated first-session publication. They still validate closed
records, inactive compute and the exact original authority checksum after excluding
only allowed output metadata. The protected-resource snapshot excludes the new DEV
output only after proving it equals the DEV subset of the complete output. No
IAM/trust/activation checksum was relaxed or replaced.

## Actual first runtime plan and targeted correction

The real global networking plan had 43 creations and no updates/deletions. Its
saved binary was applied through E16 with the exclusive role and native S3 locks.
It partially completed: VPC `vpc-0947cfaf91cb48ee9`, two public and two private
subnets, routes, security groups, the two EIPs and internal ALB resources exist.
No SQL, NAT ASG, Fargate task or Gateway was created at that stage.

Provider readback exposed missing `ec2:DescribeAddressesAttribute` and
`elasticloadbalancing:DescribeListenerAttributes`; logs creation also needed the
actual `/aws/vpc/demo-dev-flow-logs` ARN. The operator policy's second version adds
only those reads and the exact DEV log group operations. Live attributes and
ownership are checked before clearing the three post-create taint flags. State
and failed attempt evidence are preserved; a new reviewed plan is required.

The partial apply does not count as reconciled global UP. ALB and two public
IPv4 allocations incur charges while this stage remains present. The original
reverse dependency order remains available for supervised cleanup, subject to
actual controller absence/inhibition and Terraform state reconciliation.

First NAT installation had a circular source gate: even NAT handlers required
ECS color and cleanup IDs, while SQL bootstrap needed NAT first. The existing
WP4D environment binding now accepts a closed `E1_WP4D_PROTECTED_NAT_NETWORK_V1`
only for the three DEV NAT duties. It contains authenticated account/region,
repository metadata and both exact a/b ASG/network/launch specifications; it
cannot authorize application delivery, cleanup or PROD. Package/VersionId/digest
approval, fresh membership resolution, narrow duty IAM and E13 UNKNOWN handling
remain mandatory. No alternative coordinator or admission registry is added.

Terraform/Python parity now explicitly covers the network-only binding and
foreign-ASG/PROD rejection. Real Terraform console also exposed list-versus-tuple
comparison in the DEV two-slot validation; both operands are now sorted lists.
PROD wiring and lifecycle packages remain unchanged.

The minimal WP4D Docker assembly copies only the existing runtime/installer and
requires a digest-pinned Lambda Python base with boto3/awslambdaric already present.
The VM built it without credentials using the observed official base
`public.ecr.aws/lambda/python@sha256:c05509c1a303e7ca10acc26782f530ff1a8573411132e2a67c1924d687a65a96`.
Its OCI image digest is `sha256:1f55128f3203d38f452405d9625011573865ac71710635eecd21ea17304162c4`.
A built image alone is not an installed handler or callable-version proof.

A duplicate local provider cache filled C: and invalidated one gate/initialization.
Only exact task-generated provider binaries in obsolete private execution caches
were removed; no state, plans, other project files or evidence were deleted.
`--terraform-plugin-cache` can reuse an existing external cache on local WSL.
Readonly provider locks/checksums remain enforced, so cache presence is not trust.

AWS's [ELBv2 authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elbv2.html)
does not support resource-level scoping for `DescribeListenerAttributes`. An ARN-only
read grant remained denied in both simulator and live calls. Policy part 4's third
version uses `Resource: "*"` for that one read action with `aws:RequestedRegion`
fixed to `us-east-1`; mutation grants remain scoped. The original listener uses
HTTP **8080**, as the actual source and reviewed plan specify.

After independent reconciliation, a new session can prepare a networking bootstrap
plan for partial owned global state. It rejects ASGs recorded in state and independently
requires both exact native ASG names to be absent. This does not reopen the failed
attempt, bypass unresolved evidence or authorize blind replay of its binary plan.

The first real NAT plan also exposed another inert-source limitation: the security
root passed only empty checked-in installation maps, so an administrator's tfvars
could not install its declared launch templates or handlers. Four explicit
administrator-only inputs now feed the existing gates: `dev_nat_launch_inputs`,
`dev_nat_installations`, `dev_nat_runtime_approvals`, `dev_nat_network_binding`.
Their default is empty/null; validation restricts keys to dev/a, dev/b and the three
original NAT duties, with exact account/region and the closed network-only schema.
They cannot install PROD or application controllers. The source catalog remains
inactive; live receipts, published image digests and observed network IDs must be
supplied by the authenticated security administrator, never the DEV operator.

Windows cannot inspect WSL-created provider-cache symlinks using Path.is_file. Source verification now excludes only .terraform/.terragrunt-cache before inspecting paths; actual root/nested executable sources remain checked, with a regression proving foreign extra.tf is rejected. Readonly provider lock verification remains independent.

## Live recovery: state serialization and Lambda quota

The recovery plan stopped before any apply because Terraform state pull reordered
its `check_results` entries between calls. Independent reads had the same lineage,
serial, resource values and check results after sorting by check identity. E16 now
hashes canonical JSON with only check-result/object ordering normalized. It retains
all checks and statuses, every resource value and ordered resource arrays; a changed
value at the same serial still rejects execution. The old rejected plan stays in
private evidence; a fresh plan must be reviewed against the corrected source.

All three NAT runtime ECR repositories now contain the exact OCI digest above,
with manifest readback. The installed versioned packages and image approvals do
not mean the Lambda handlers are installed or invoked.

The account's actual us-east-1 Lambda concurrency quota is **10**. The original
handlers reserve one execution each; their safeguards have not been removed.
AWS definitively rejected the requested 110 with `IllegalArgumentException`:
requests must exceed the service default of 1,000. Request
`43e5dc5811104434a40854a2c8b3e583ahAgHwhY` for **1,001** was accepted as PENDING.
An accepted request is not an increased quota. No NAT ASG may be started before
the authentic handler installation and recovery binding are ready.

The targeted handler preview also included unrelated controller roles, including
PROD roles, through the shared IAM dependency expression. That binary plan was
rejected and never applied. Any administrator installation must select only the
three exact DEV recovery roles/policies/functions, retain the source-defined
trust and duty scope, and record authentic readbacks. It cannot apply that mixed
preview or fabricate an installed binding to proceed with ASGs/SQL.

The repository gate at `c3eeb8d404c5c155a5b0911a984e0dbaaa81d3cd` passed
983 E1/WP tests and AC1–AC16. This is not AWS application health. The corrected
operator passed 41 tests; bootstrap now passes 17, including both Flow Log
resource authorizations.

Network recovery created the candidate ALB rule and VPC log group, then
failed definitively on CreateFlowLogs for the new vpc-flow-log resource.
Operator Part4 version v4 adds only that create action on same-account/region
flow logs, requiring DEV/demo request tags. The original parent-VPC DEV/demo
resource-tag check and scoped PassRole remain. IAM analysis, installed readback
and simulator confirmed the addition. A new missing-resource plan is required;
the failed binary is not replayed and its state/evidence remain retained.

Three exact original NAT execution roles/policies and two encrypted diagnostic
queues are installed. No Lambda function or target is installed. Policy import
encountered unknown EventBridge target for_each dependencies. A scoped
policies-only preview excludes PROD and unrelated roles and is independent
of function activation. Quota request is CASE_OPENED (case 179193009300032),
while actual Lambda concurrency remains 10.

Pinned TFLint mislocates deprecated-index diagnostics in escaped JSON. The new
DEV-only branch uses equivalent element(slots, 0) for its first slot, whose
closed two-element length is already validated. The existing full-binding/PROD
branch remains unchanged. Actual console policy/trust parity passes all 11
cases; no finding is suppressed.

## Reconciled checkpoint before AWS quota approval

The saved single-resource recovery completed under the exclusive human role.
Global networking has **43 managed resources**; data/platform/apps/edge have zero.
Flow Log `fl-04a223185c4dc25e0` is ACTIVE with CloudWatch delivery SUCCESS.
The VPC has both original public and private subnet pairs, original ALB/listener,
candidate rule, target groups, EIPs and routes. Global UP is only network bootstrap;
no NAT ASG, SQL EC2, ECS task/service or API Gateway is claimed healthy.

Three NAT roles/policies, two encrypted diagnostic queues and their exact queue
policies are reconciled in the original security state. EventBridge rule
`e1-wp4-dev-nat-launch` is independently confirmed DISABLED and has no targets.
The three runtime images and protected package versions are installed, but the
Lambda functions are not. Quota request/case above remains the next activation gate.

Real RESIDUAL initially found missing DescribeNetworkInterfaces authority.
Part4 version **v5** adds only that regional read; installed document and an
actual assumed-operator EC2 read succeeded after IAM propagation. RESIDUAL then
completed with authenticated observations, reported the two EIPs and a VPC ENI,
and correctly retained partial/unverified status rather than a zero-bill claim.
Tag directory candidates require direct EC2 reconciliation; tags alone never
identify a safe deletion target. No account-wide cleanup is permitted.

The two originally empty SQL password secrets now have generated AWSCURRENT
versions. The short-lived input files had explicit user-only Windows ACLs and
were removed; passwords were never logged, placed on command lines or put in
Terraform state. SQL and its connection-string secret remain unprovisioned.

At revision `90bc3ce58b1845f67cbd8e81ab6e8feae2d162f7`, the complete E1 gate
again passed **983 tests, AC1–AC16 and all 44 checks**, including E15-H.
The final source used the already installed AWS **5.100.0** provider with Terraform
**1.13.4**: local no-backend validate passed, zero errors/warnings, without a
provider download. Real provider plans/applies and S3 native locking also executed.
Pinned TFLint/tfsec retain exactly **24/46** findings by identity/multiplicity.
The final ENI grant is a read-only installation-document correction, verified live
and by focused bootstrap/source-inventory checks after that complete gate.

Current base running cost is about USD **0.0325/hour** (0.0225 Application ALB,
plus two IPv4 allocations at 0.005 each), or **0.78/day**, before LCU, logs,
KMS/secrets, S3/ECR storage, requests and transfer. This is a list-price estimate,
not an AWS bill or approved budget. The original future NAT slots are t3.micro
(0.0104/hour each); SQL's t3a.small is 0.0188/hour, plus EBS and workload costs.
Backend, identities, keys, secrets, images and diagnostic evidence are retained.

Emergency cleanup remains the original E16 sequence: inhibit and review authentic
controller/ASG/ECS observations, review each next-layer down-plan, then apply that
exact saved binary with independent SQL-loss confirmation when data exists.
IAM simulation permits DeleteVpc, DeleteFlowLogs, ReleaseAddress and ALB deletion
on the actual DEV IDs. No destroy, forced unlock or executor-finality certification
was performed. Preserve failed attempts and original state; never replay them.

Next: AWS must approve the pending Lambda quota; install/read back only the three
DEV handler versions, package read access and EventBridge failure/target bindings,
then complete global with both original ASGs. Data → platform → apps → edge and
WP3/WP4 application qualification/deployment follow using real created IDs.
The SNS email subscription still needs the owner's actual destination; it cannot
be invented. A published application image is not yet a qualified/deployed release.

The tag directory returned two additional subnet IDs. Exact EC2 lookups for
`subnet-0e56abf760ef9212c` and `subnet-0e1be451d6570d5bb` both returned
InvalidSubnetID.NotFound, so these are not confirmed surviving subnets. Their
absence was reconciled independently; no adoption or deletion was attempted.
The bounded residual report remains partial because the real ALB/EIPs/ENI and
protected retained resources are still present.

Pricing sources: [public IPv4](https://aws.amazon.com/vpc/pricing/);
Application ALB and EC2 values were independently read from AWS Pricing
GetProducts in us-east-1. Lambda's [reserved concurrency API](https://docs.aws.amazon.com/lambda/latest/api/API_PutFunctionConcurrency.html)
requires 100 unreserved executions, explaining why the effective quota 10 cannot
support the unchanged original reservation. A request is not approval.

## Owner correction: optional email and resolved Lambda quota

The owner authorized the original SNS topic with **no email recipient**.
DEV alert_email now defaults to null; zero email subscriptions are created.
Topic `arn:aws:sns:us-east-1:341936017254:demo-dev-shared-alerts` was created
from an inspected saved one-resource Terraform plan and verified encrypted
with the original alias/aws/sns, DEV/demo tags and no subscriptions.
State remains `e1/lifecycle/dev/shared/terraform.tfstate` under the existing
security administrator; human five-layer authority is unchanged. This independent
SNS bootstrap targets its original declaration, requires no fabricated neutral
references and does not claim the full protected shared publication is installed.
The shared root's unused TLS lock entry was removed only for DEV; PROD package
SHA-256 identities remain unchanged. Email delivery is inactive until a real
recipient is configured and confirms the subscription. Encrypted CloudWatch-to-SNS
publishing has not been functionally tested; service-publisher KMS requirements
remain subject to genuine validation before claiming alerts work.

AWS now reports actual Lambda concurrency **1,000**, so the earlier activation
blocker is resolved even though the 1,001 request still shows CASE_OPENED.
CreateFunction then definitively rejected the original 4,952-byte environment
configuration; authentic inventory proved no NAT function was created.
Only NAT DEV's redundant resources copy is now omitted (an empty object);
the complete authoritative nat_slots remains, and runtime/package/image bytes
and duty IAM remain unchanged. Production and application configuration preserve
their full resource copy. Actual Terraform console configurations are 2,592,
2,588 and 2,596 bytes including the environment-variable key, below 4 KB.
All 11 Terraform policy/trust/configuration parity cases and 33 WP4D tests pass.
SNS/source change tests pass 18; WP5 49, security foundation 18 and publication
52 also pass. No earlier rejected creation is blindly replayed.

The exact original storage policies now permit only the three authenticated NAT
roles to read protected package versions and write their own conditional E13
journals. TLS, no non-admin delete, immutable evidence, E2 conditional ownership
and human read-only access remain. Mixed plans containing PROD were rejected;
only the two evaluated DEV policies were installed and read back.

The original three NAT functions are now installed as published **version 1**,
Active, immutable runtime digest verified and reserved concurrency **1** each.
The three qualified EventBridge targets, exact invocation permissions and E13
async failure destinations are read back. The native rule remains DISABLED until
both ASG slots are prepared. Original NAT logs exist with **14-day** retention.

Terraform import exposed an unknown-key dependency on untracked EventBridge
target attributes. The same protected target selection is now a stable local
binding map used by target/permission/async-alarm for_each, with explicit target
dependencies preserved. This changes no target membership, IAM or PROD behavior;
actual console parity verifies all environments and inactive rejection cases.
Installed resources are imported through Terraform into original security state,
never by editing or replacing state files. The old mixed plans remain unapplied.

Lambda automatically added ECR permissions including repository-policy management
and a wildcard function source. These three new NAT repositories now use the
original source-defined service read-only policy, limited to their exact DEV
function/account. No unrelated ECR repository was modified.

A final gate attempt at 0438913 failed while copying fixtures because C: ran out
of space. It is not a PASS. Only five identical, task-generated provider binaries
in the obsolete private dev-runtime-session-1fb9bee cache were removed after
path, size, SHA-256 and inactive-process verification; all state/plans/evidence and
the active checksum-locked cache were preserved. Fresh acceptance must complete
before delivery. The complete gate at 90bc3ce remains earlier evidence.

## Original NAT launch: first supervised attempt

Six original E13 diagnostic alarms were installed, read back and imported into
security state. The mixed convergence plan containing PROD roles was not applied.
The DEV NAT launch rule is ENABLED; all three original published handler versions
and exact invocation permissions were verified before activation.

The human reviewed a six-create global plan: two original NAT ASGs and four
capacity alarms, without changes/deletions. Both ASG calls were definitively
AccessDenied in CloudTrail. Exact readbacks found none of those six resources;
global state still held its prior 43 resources. Preserve that failed plan/attempt.
It is never replayed; further deployment uses a fresh supervised plan/session.

An operator EC2 dry-run identified missing ec2:RunInstances. AWS documents
[launch-template permission checks](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-launch-template-permissions.html)
for Auto Scaling. TerragruntDemoDevOperatorPart5 v1 now matches the installed
account-specific source policy: only the two observed NAT template ARNs, their
exact AMI/public subnets/security group, t3.micro and required IMDSv2. Instance
tagging is limited to RunInstances with original DEV/demo/NAT tags. No template
mutation, IAM administration, state permission or PROD/shared access is added.
Independent successful dry-runs are required before preparing another ASG plan.

Acceptance at dbba1bc executed all 983 baseline tests but failed four checks:
three historical authority snapshots still expected mandatory DEV email, and
the NAT projection omitted the production stable target-map local. Corrections
validate only the authorized optional-email delta before the historical hash;
all other authority/inert-binding assertions remain. NAT now evaluates its actual
target-map expression. Focused reruns pass: exact_destroy 46, ephemeral 30,
retention 18, NAT projection both cases and first-deployment 19. This does not
claim a successful complete final gate or AWS application readiness.
Static debt remains 24 TFLint / 46 tfsec, unchanged by identity/multiplicity.
SQL, ECS and API Gateway remain unprovisioned at this checkpoint.

## Both original NAT slots created; E13 absence-read correction

A fresh reviewed global plan after the exact-template EC2 permission fix applied
all six resources. Both ASGs have one InService/Healthy t3.micro, version 1:
A i-0a1ffe2dcf7c0889a / eni-0c571d9ef27631ea7;
B i-0afcbfdf10a181f94 / eni-05f3589d7243685d3.
The original global state is reconciled, not functional networking evidence.

Native launch events invoked the three handlers. All six E13 operations retained
UNCERTAIN outcomes; the journal directory contained no intent/attempt/effect.
Fresh EIP/route/SDC readbacks still show no association, no private default route
and SDC true. No SQL/app deployment proceeds from that incomplete networking.
The DEV rule and new Lambda invocations are inhibited during diagnosis. This is
not a claim that concurrency zero terminates earlier executors.

S3 [GetObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)
returns 403 for missing keys without bucket-list authority. The original adapter
cannot establish absence from that response. Only the three DEV NAT packages now
select a bounded NatObjects reader: after a denied GET it independently lists the
exact key prefix (at most two entries), requires a complete matching observation,
and returns absent only if that exact key is absent. Denied, partial or existing
key observations remain failures. Each DEV NAT role receives ListBucket only for
its own recovery/dev/recovery/DUTY prefix; E2, other duties and PROD are rejected.

The common adapter, runtime/image bootstrap and all 13 non-DEV-NAT WP4D package
identities remain unchanged. Every WP5 package remains unchanged. No PROD IAM
installation occurs. Three DEV bundle hashes are intentionally regenerated and
need exact-version conditional installation/readback before reactivation.
WP4D 33 tests and all eleven real Terraform expression parity cases pass.
Earlier UNCERTAIN operations/evidence remain preserved; no forced settlement or
blind resend is performed. Private plans/state/password values remain outside Git.

## Both original NAT slots reconciled

Authenticated readbacks confirm both original ASGs have one Healthy/InService
t3.micro, launch-template version 1. Both exact EIPs are associated to their
current ENIs; both private default routes are active; source/destination checks
are false; both fixed bootstrap CONFIGURED markers are present. Private-subnet
packet forwarding still needs live workload evidence. NAT-A is
i-0a1ffe2dcf7c0889a; NAT-B is i-0afcbfdf10a181f94.

Three DEV-only bundle version/readbacks and published Lambda version 2 retain
the original runtime image. Targets, permissions and failure destinations are
verified. Native launch events were read from the preserved failure queue and
processed sequentially only after complete journal reads showed no prior attempt.
NAT-B completed EIP/route/SDC and E13 bootstrap verification with SUCCESS.

NAT-A SDC was rejected definitively: CloudTrail event
98730b62-65c7-49d1-8f3b-ea1f227dae89 identifies the exact execution role, instance
and sourceDestCheck=false request with UnauthorizedOperation. Only DEV's IAM
attribute value changes from sourceDestCheck to SourceDestCheck; actions,
resources and ownership conditions are unchanged. PROD retains its original
policy. A separately identified authenticated human reconciliation completed
SDC with operation 41ff966c-8f56-5cc9-a2ab-4ba64f6e4333. This is explicitly
not a native AWS delivery. The earlier UNCERTAIN journal is preserved unchanged
with its attributable denial evidence; no forced settlement or blind resend.

The exact SQL operator policy Part6 v1 is installed/read back: observed Ubuntu
AMI, first private subnet, SQL SG/profile, t3a.small, required IMDSv2 and DEV/demo
request tags. After propagation the real dry-run returned DryRunOperation; no
SQL instance was created by the check. State/PROD/shared protection is unchanged.

Complete acceptance at 8ce1cf0 passed 983 tests, AC1-AC16 and all 44 checks.
After the IAM case correction, WP4D 33, first-deployment 20 and all eleven
Terraform policy/trust projections pass. Every package identity is unchanged
by that policy correction; no PROD IAM installation occurred. The final source
commit was temporarily blocked because automatic approval review reached its
usage limit, not because a safety rejection identified unsafe behavior.

## SQL and ECS platform verified — 2026-10-14

The fresh reviewed data plan created i-0e47f560bf71333e4, Ubuntu 22.04 x86_64,
t3a.small, private address 10.0.100.10, encrypted 30 GiB gp3, no public IP.
SSM agent 3.3.4793.0 is Online through NAT-A. SQL Server 2022 Express bootstrap
completed, mssql-server is active, and an authenticated SSM check connected to
demodb as fargate_user. This proves actual SQL login and private-A outbound access;
application SQL/KMS round-trip and private-B traffic remain unverified.

The connection secret was seeded once outside Terraform using the observed SQL
address and the existing application password. Password quoting handles connection
string delimiters. Only returned version/AWSCURRENT metadata was retained;
the private temporary input was removed. No values entered Terraform or Git.

The exact SQL metadata/read grants now match Part6 v3. Part7 v2 scopes logs to
the two original ECS groups and original API access group. Part8 v1 scopes HTTP
API/VPC-link creation by original names and DEV/demo tags and resource changes by
DEV ownership; installed documents were independently read back. These add no IAM,
state, secret-value or PROD permissions. The native ECS service-linked role was
absent and separately installed by the security administrator; the existing API
Gateway service-linked role was inspected without modification.

The reviewed one-resource platform plan created the original ECS cluster. The
first apps plan was retained unexecuted: its role-free inert Fargate definition
incorrectly included awslogs, which requires an execution role. The DEV-only
source generator omits that log configuration from the zero-count bootstrap.
Both log groups, the actual two-container application template, its awslogs
configuration, and WP4 role bindings remain unchanged. PROD extraction is unchanged.
See the AWS [task execution role requirements](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-ecs-iam-role-overview.html).
A new source-bound session and fresh reviewed plans are required after this fix;
no previously reviewed binary is silently edited or replayed. Only DEV WP5 source
package hashes change; their installations remain inert, and no PROD or NAT
runtime package is replaced by this correction.

At 0cb0355, TFLint 24 and tfsec 46 findings match the preceding baseline by
rule/resource/description/severity identity and multiplicity. This checkpoint does
not claim deployed application readiness or completed API Gateway provisioning.

The same pre-apply inspection found ECS Exec enabled by the extracted module
variable default, despite the accepted inert/normal-delivery contracts requiring
it disabled. DEV's two zero-count service calls now explicitly set it false.
A role-free definition cannot support ECS Exec; no task-role/SSM authority is
added to work around that mismatch. PROD and the real runtime template remain
unchanged. The pending source-6c session must fail its clean-source identity check
before any application when the corrected source is committed.

## First apps partial apply: attributable read denial

The corrected apps plan created both log groups and inert definitions revision 2,
but stopped before either service. DescribeTaskDefinition does not support
resource-level authorization: AWS returned AccessDenied on resource *, despite
the earlier task-definition ARN grant. Part9 v1 adds only that read operation,
in us-east-1. See the [ECS authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html).
No mutation wildcard, secret-value read or PROD mutation authority is added.

Both definitions were independently compared with the reviewed plan (all requested
container fields, family, CPU/memory, networking, tags and absence of roles).
Environment/secret lists are normalized only by name. After exact authenticated
readback, Terraform untaint reconciles the failed read without replacing the
already-correct definitions; the original failed attempt remains preserved.
A fresh session/plan must create only the missing services/alarms.

SQL's next plan found missing root-volume tags. Part6 v4 permits only CreateTags
on observed vol-013e417f112c5fe43 with the five exact original tags. The saved
plan added them; independent volume readback verified tags, attachment, size and
encryption without restarting/replacing SQL. No general disk mutation was added.
The unused DEV bootstrap region data source is removed; real application logging
and PROD generation remain unchanged.

Acceptance on stable 4d1c490 passed 983 baseline tests, AC1–AC16 and all checks.
The previous gate ran while source was being corrected and failed source-drift
checks; it is not acceptance evidence. tfsec remains 46 by identity/multiplicity.
TFLint detected one unused region declaration after removing inert logging; its
source is now removed and a fresh scan is required, without suppression.

## First real application and edge checkpoint — 2026-10-14

Both original ECS services use immutable image
`sha256:9671c5484c60de9db50f54abade794bb86263a5d636bca96a5eb3522c8643a50`,
revision 4 in their original color families. Each desired count is one. These are
supervised first-installation updates by the authorized account administrator,
not WP3 qualification or an installed GitHub/WP4 delivery execution. Terraform
continues to ignore task revisions/counts; ALB default forwarding remains blue.

The first real Fargate startup exposed root-owned mode-0600 configuration copied
from the private build context. The publish stage now grants `a+rX` within
`/app/publish`; it retains root ownership and runtime UID 1654 and adds no write
permission. Actual Docker non-root readability/non-writability and liveness
checks pass. No secret values are built into that directory.

The existing ciphertext-expansion migration lacked EF discovery attributes.
Adding its exact DbContext and migration identity makes EF discover the existing
migration without changing its Up/Down operations. A SQL Server provider test
scripts the real ALTER without opening a connection. Real SQL now records both
migration identities and `DemoTexts.Text` max_length=-1. The corrected image
applied the migration; no manual schema alteration was used. All 103 .NET tests
pass on the isolated VM with network disabled and cached packages. The exact
four modified/new source files match the tested VM copy by SHA-256.

The edge apply stopped after creating its 30-day log group. Attributable
CloudTrail records show both tagged create requests rejected: API creation needs
an encoded tag-resource POST, while VPC Link's rejection names
`apigateway:TagResource`, which IAM Access Analyzer rejects as an invalid action.
That invalid candidate was never installed. No permissions were broadened.
The already-authorized administrator created only the exact reviewed DEV API,
VPC Link and default stage; their authentic IDs and tags were read back, and the
exclusive DEV state writer imported them into the existing original Terraform
root with ordinary S3 locking. No unrelated resource was imported. A fresh
session/plan is mandatory for the remaining resources; the failed attempt and
original binary remain preserved. Future recreation requires this same small
administrator bootstrap until AWS's tagged-create permission discrepancy is
resolved; the current operator policy does not claim that capability works.

API ID: `wjjhpal9ig`; VPC Link ID: `7fe58y`. Availability and functional public
round-trip remain pending at this checkpoint. This entry must not be interpreted
as completed application access or successful complete teardown.

## Operating costs and retained boundary

The authenticated runtime inventory contains exactly the two original NAT EC2
instances, one private SQL EC2 instance, two final Fargate service tasks, the
internal ALB and two EIPs. Original NAT root volumes are 8 GiB gp2 each (the
original launch configuration does not encrypt those disks); SQL is 30 GiB
encrypted gp3. All three root attachments are DeleteOnTermination. No extra
application compute from the diagnostic one-off tasks remains running.

Observed regional unit rates produce a running base of approximately USD
0.096785/hour with both colors at one task: two t3.micro at 0.0104 each,
t3a.small at 0.0188, ALB at 0.0225, two IPv4 at 0.005 each and two Fargate
0.25-vCPU/0.5-GiB tasks at 0.0123425 each. This excludes EBS, ALB LCU, logs and
Container Insights, API requests, data transfer, KMS, Secrets Manager, ECR and
S3/evidence storage. It is not an approved budget or a zero-cost teardown claim.
Rates are the session's regional pricing observations, not a future price promise.

Before DOWN: inspect the exact account and states, inhibit actual deployments and
NAT triggers/invocations, reconcile outstanding requests and failure messages,
then native ASG activities/membership. Disable/zero concurrency does not cancel an
already-dispatched effect. The preserved NAT-A SDC UNCERTAIN attempt has a
specific CloudTrail UnauthorizedOperation denial and later successful separately
identified human reconciliation; its original journal is not overwritten.
Existing E16 shutdown admission still requires attributable terminal evidence and
failure-message reconciliation. Do not force it through or force-unlock state.

Use reviewed saved plans in reverse order edge -> apps -> platform -> data ->
global, with the independent SQL-loss confirmation. A failed layer stops the
sequence, preserves state and requires a fresh review after reconciliation.
No complete destructive rehearsal has been performed. The administrator's
owner-authorized emergency path is restricted to these recorded project-owned
identities, with state reconciliation through the exclusive operator; it is not
account-wide cleanup. Retain the backends, state versions/locking protection,
security/IAM, KMS/secrets, ECR images, journals, failure evidence and intended log
retention. Email alerts remain inactive by the owner's decision. GitHub OIDC and
normal protected WP3/WP4 delivery still require separate installation and GitHub
authorization; the successful local image build/bootstrap does not certify them.

## Successful public functional verification — 2026-10-14

All five original DEV layers are applied. The endpoint is
https://wjjhpal9ig.execute-api.us-east-1.amazonaws.com. VPC Link 7fe58y is AVAILABLE;
integration anw2uwb targets the original internal ALB listener. Four original
routes and the auto-deployed default stage are installed with 30-day access logs.
Both original color services are COMPLETED with desired=running=1, pending=0,
revision 4, the final digest, readiness-probe exit 0 and one healthy ALB target each.
Blue task 607b5fedb0274cf2b18b7cac3e0f2919 uses private address 10.0.100.130; green
a90ec1bb8d324da0b358251099dd8e1e uses 10.0.100.9. The listener remains blue.

Authentic public /ready reports database and KMS Healthy. POST/GET /text round trips
succeeded for a 46-byte synthetic marker and 4096 UTF-8 bytes (2048 ñ characters),
proving actual SQL persistence and KMS Encrypt/Decrypt through Gateway/VPC Link/ALB.
No secret values are included in those test records. Actual private-B diagnostic
Fargate execution and private-A SQL/SSM/application execution also prove outbound
service access through both original NAT routes; failover/forced replacement has
not been exercised. All diagnostic one-off tasks are stopped.

The completed edge plan 64cab12d-c1d7-4fbc-8b35-ddf224ca26c6 created only the
integration and four routes, using the exclusive operator, exact reviewed binary,
unchanged imported resources and normal S3 locks. All ten installed operator
default policies match the source exactly; no invalid tagging grant was installed.
The owner requested leaving the successful environment running for inspection;
ongoing charges continue. No complete DOWN, production deployment, GitHub push,
merge or protected release qualification is claimed.

## Final operator readback and repository acceptance

The production E16 verify path initially stopped on ecs:DescribeTasks denial.
Part9 v2 adds only that read on task/demo-dev-platform-main-cluster/* in
us-east-1; the regional DescribeTaskDefinition grant remains unchanged. IAM Access
Analyzer returned no errors and the installed default document was independently
read back exactly. No ECS mutation, IAM administration, secret-value or PROD
authority was added. The real E16 verify path subsequently completed its original
state/backend, both NAT routes/EIPs/SDC, SQL, ECS per-task readiness and public
application SQL/KMS round-trip checks.

Complete repository acceptance on clean 5329085 passed 983 E1/WP tests, AC1–AC16
and all 44 suites/checks. All 103 .NET tests pass with network disabled on the VM;
the Docker build/export and runtime readability/liveness probes pass. The tested
source matches the committed application files. ShellCheck, explicit-file
Actionlint and Bash parsing pass on the existing VM tools. TFLint 24 and tfsec 46
match the preceding baseline by identity and multiplicity, without suppression.
The final Part9 read-only addition has a focused regression and refreshed source
inventory; it does not change Terraform resources or protected package identities.

Independent CloudTrail observations also contain successful KMS Decrypt calls by
the real application task role. The exact API access stream contains all five
functional-test requests with HTTP 200 and no integration error; an initially
empty FilterLogEvents page was not treated as proof of missing delivery.
All private plans, state, credentials and log evidence remain outside Git.
Future source commits require a new E16 execution session/configuration and a
review of retained original layer variables; old source-bound plans are never
replayed under a different commit.
