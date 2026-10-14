# First real original DEV session â€” 2026-10-13

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
