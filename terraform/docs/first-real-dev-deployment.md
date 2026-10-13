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
and `demo/dev/db/sql-sa-password`; no secret values were seeded or put in Terraform.

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
