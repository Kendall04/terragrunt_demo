# E1 WP4D: exact protected controller materialization

Classification: WP4D implementation candidate on
`codex/e1-wp4d-iam-materialization`, based on integrated
`400e1d12cec99372057ad5058d7c779dcf2e6893`. Acceptance and integration remain
separate from this local checkpoint. The approved [E1 spec](../../specs/iam-hardening/spec.md)
and [plan](../../specs/iam-hardening/plan.md) remain unchanged.

WP4D describes the reviewed WP4A/WP4B/WP4C controller topology in the protected
security root. It does not activate any of the eleven external request identities.
The repository is undeployed; the checked-in installation, runtime approval, and
environment binding maps are empty. Consequently no WP4D Lambda or CodeBuild
instance is currently creation-supported. This is a truthful target declaration,
not an AWS installation receipt.

## Selected compute and installation

The WP2C reserved Lambda gateways for `deploy-dev`, `promote-prod`,
`emergency-dev`, and `emergency-prod` start only their exact corresponding WP2C
CodeBuild controllers. WP2B reserved cleanup and NAT classes expand to one
cleanup Lambda and three independent NAT handler Lambdas in each environment.
The 16 selected bindings are listed in the protected `authority.json` WP4D
section. No WP5, WP6, or WP7 identity is selected. The undeployed target-group
skeleton names are aligned to the accepted WP4A `demo-{environment}-{color}`
identity checked during authorization.

`scripts/tests/security_root/pack_wp4d.py` produces a canonical, deterministic
JSON package for one binding. The package contains the exact accepted WP4 sources
and the WP4D adapter/entrypoint source, binds the WP2 reservation digest, and
has a reviewed SHA-256 in `authority.json`. It can also verify package bytes
offline. A security administrator must conditionally install exactly these bytes
at `bundles/sha256/<digest>.json`, retain the returned S3 VersionId, and read
back that exact version before supplying an installation record. The controller
runtime reads that VersionId with `s3:GetObjectVersion`, verifies the SHA-256 and
closed package contents, then extracts only its own fixed binding. A changed
source changes the package identity.

The WP4D `install()` helper reuses WP2D's `AdminBundleStorage` port and emits a
receipt only from the returned bucket/key/VersionId and exact version byte
readback. That port requires separately authenticated administration; a fixture
subclass and its returned synthetic version prove only the local contract.
No receipt is checked in. Shared Python adapters include their complete import
and schema dependencies; only normal-delivery packages include the Bash E3
payload. Warm Lambda invocations reload modules from each verified extraction.

The approved runtime image URI must be the exact ECR repository for the binding
with `@sha256:<digest>` and an administrator approval bound to the package digest.
The image must contain the fixed `/opt/e1/scripts/wp4d/runtime.py` and
`installed.py` bootstrap bytes; the runtime compares both against the verified
package before executing installed controller code. The image also needs
Python/Boto3 and, for normal CodeBuild, Bash, AWS CLI and jq required by E3.
The Lambda bootstrap must expose `runtime.handler`. A runtime approval is an
installation prerequisite, not an assertion that AWS has run the image.
Environment bindings must be administrator-published protected configuration;
they cannot be supplied in a request. Terraform gates admission on exact
environment/account/region, canonical service and role names, dev/prod ALB
resource identity, two disjoint NAT slots, and the reviewed install/readback
claims. Missing or malformed gates leave compute absent. The gate does not
default any prerequisite to true.

## Trust, invocation, and evidence

Lambda roles trust `lambda.amazonaws.com`; CodeBuild roles trust
`codebuild.amazonaws.com` with exact project SourceArn and SourceAccount. No
controller role trusts GitHub/OIDC or another controller role. Gateway policies
allow only `codebuild:StartBuild` on the matching project; the gateway passes
only `projectName`, with no build overrides. No external Lambda invoke grant is
added. Cleanup invocation is restricted to the exact named EventBridge cleanup
rule and published Lambda alias. NAT handlers are invoked only by the exact
environment's ASG launch rule. Event payloads do not select AWS resources.

NAT launch ASG names select a protected slot, whose membership is independently
verified. They never authorize an instance supplied by an event. Cleanup uses
the native Scheduled Event envelope and rederives the inactive service. CodeBuild
receives no overrides; a protected build-ID-to-operation record connects it to
the closed gateway request. A lost StartBuild acknowledgement is UNCERTAIN and
is not resubmitted. Caller operation UUIDs bind idempotency, not AWS authority.
All SDK clients use one total attempt with bounded connection/read timeouts;
automatic SDK retries cannot resend an ambiguously acknowledged mutation.
Effect readback after the deadline cannot become APPLIED. Durable acknowledgements
bind the exact request/result; independently observed matching state completes
that evidence. Without the acknowledgement, retries remain UNKNOWN.

The WP4D evidence buckets are environment-specific, versioned, encrypted with
SSE-S3, TLS-only and deny non-admin deletion. Immutable operation/effect paths
require conditional creation; class-owned IAM policies restrict read/write
prefixes. Qualification, eligibility, membership, and environment bindings
remain protected records in the existing security-root evidence bucket and
are only read by delivery/recovery controllers. Prod reads the exact dev
activation prerequisite but has no dev evidence write grant. Normal delivery
alone can publish its own success index and the dev activation prerequisite.
Emergency reads historical WP4B receipts from the protected delivery prefix;
its own immutable attempts remain in the separate recovery prefix.

## Effective authority

Normal delivery can register only the two environment task-definition families,
pass only the four exact environment task/execution roles with
`iam:PassedToService = ecs-tasks.amazonaws.com`, update the two exact services,
modify the exact listener/candidate rule, and manage its exact cleanup schedule.
It cannot run/start tasks, execute commands, administer IAM, or write protected
qualification/eligibility/security-root records. Emergency can update the exact
services and routing but has no `RegisterTaskDefinition`, `PassRole`, image
publication, or qualification/eligibility write grant. Cleanup has its own role
for the exact services and cleanup rule; its code selects only the inactive
side. NAT handlers have separate roles: `assign_eip` gets `AssociateAddress`,
`change_rt` gets `CreateRoute`/`ReplaceRoute`, and `disable_sdc` gets only
`ModifyInstanceAttribute` for SourceDestCheck. None inherits another handler's
mutation verb.

| Principal and trust | Positive authority | Protected inputs and conditions |
| --- | --- | --- |
| Four WP2C gateway roles; Lambda service | StartBuild on one exact partner; own gateway-prefix reads/conditional writes | Fixed project, operation record and immutable package; no build overrides |
| Dev/prod normal CodeBuild roles; exact project/account service trust | Register two families, pass four roles, update two services, modify one listener/rule, schedule one cleanup target | WP4A qualification/current eligibility/role pairing; WP4B/E3; PassedToService; all target ARNs must equal the cleanup alias |
| Dev/prod emergency CodeBuild roles; exact project/account service trust | Exact capacity/routing/schedule actions and read-only history | WP4C successful immutable receipt, current non-revoked eligibility and live unmixed task/target observations |
| Dev/prod cleanup roles; Lambda service and exact EventBridge source permission | Update exact services; describe/remove target/delete exact cleanup rule | Fresh active-capacity and inactive-side checks; no registration, role passing or routing mutation |
| Six NAT roles; Lambda service and exact EventBridge source permission | Each handler's one mutation vocabulary; shared bounded observation reads; exact GetInstanceProfile | Protected two-slot configuration, exact WP2 NAT profile/role, live ASG/EC2/LT/instance user-data membership; exact EIPs/RTs, ENI subnet and SourceDestCheck conditions |
| Every selected execution role | Exact package GetObjectVersion; own class evidence; own log-stream creation/writes | Exact SHA/key/VersionId, conditional immutable writes; no package installation or log-group administration |

All Allow actions are explicitly enumerated in the generated policy templates.
Routing/capacity APIs cannot express inactive-side or release eligibility in IAM;
protected code is the additional boundary. Controllers have no permission to
replace that code/configuration, edit launch specifications or tags, administer
qualification/eligibility, assume another role, or publish images. Admin-only
resource-policy denies protect membership, bindings and prod approval records.

Some AWS read actions do not support resource-level IAM scope: ECS
`DescribeTaskDefinition` and `ListTasks`, ELBv2 listener/rule/target-health
describes, EC2 instance/ENI/EIP/route-table/launch-template describes, and
ASG describe. They are confined to the dedicated role and requested region
where supported. Dynamic NAT replacement ENI/instance IDs likewise cannot be
listed as fixed ARNs before launch. `AssociateAddress` is constrained by exact
EIP ARNs and the protected subnet condition; `ModifyInstanceAttribute` by
instance resource tags and `ec2:Attribute = sourceDestCheck`. The protected
resolver independently verifies the exact ASG, VPC, subnet, AZ, instance, ENI,
EIP, route table, launch-template version, AMI, user-data hash, profile and
contained role before acting. Names/tags alone never grant NAT membership.
These limits are part of the effective authority boundary, not resource-scoped
claims for unsupported actions.

The resource and condition choices follow the AWS [ECS authorization
reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html),
[EventBridge target conditions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-conditions.html),
and [CodeBuild ECR pull policy guidance](https://docs.aws.amazon.com/codebuild/latest/userguide/sample-ecr.html).
EC2 resource/condition applicability follows the [EC2 authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html);
unscoped ALB reads follow the [ELBv2 reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elbv2.html).

The ASG name in an AWS launch event selects one of the two already protected
slots; it supplies no membership authority. The resolver independently verifies
that slot's live ASG/EC2 relationships before any handler mutation. This also
allows both AZ replacements to recover when they launch close together.

The WP4D ECS/ALB observation adapter compares the full candidate task ARN set,
one completed deployment, exact task-definition revision, task ENI IPs, and the
exact target-group health set. It rejects mixed/foreign/extra targets and
malformed IDs. This implements the WP4C live adapter obligation in code but
remains unverified against AWS. WP4C's nonblank target-ID check is retained;
nonblank alone does not prove task-to-target membership.

## Verification and remaining work

The provider-free WP4D suite tests exact action/resource/condition tuples,
trust, invocation, dev/prod isolation, package determinism, selective gating,
and representative task-to-target membership. Existing WP1-WP4C regression
tests remain required. No AWS apply, IAM simulation, provider-backed Terraform
run, Linux E3 run, installation, or deployment was performed. WP5 owns lifecycle
administration; WP6 owns GitHub/OIDC request cutover; WP7 owns final legacy
retirement. WP4A-N2 (an invalid UTF-8 byte in WP4A documentation) remains
maintenance debt.

Run the focused hermetic suite with `python -I -B scripts/tests/wp4d/run.py`.
Run `python -I -B scripts/tests/wp4d/check_static.py` to evaluate the actual
Terraform gates, policies and service trusts in disposable provider-free
configuration, then compare those policies with the tested canonical generator.
Its all-installed case and partial cases are explicitly synthetic. The checked-in
case admits zero functions/projects, including the unchanged WP3 compute gates.
Generated wiring is checked by `scripts/tests/security_root/render.py`.

One bounded self-check corrected production imports, transitive package/schema
dependencies, warm module reuse, missing configuration shapes, registration-family
derivation, SDK timestamp normalization and NAT membership envelope closure.
Instance user-data hash and service-to-target-group checks now use independent
observations. Target-group names in both extracted greenfield skeletons match
WP4A; pinned legacy sources remain outside this candidate's authority claim.
No second reviewer or open-ended review cycle was invoked.

Local validation completed with 33 WP4D tests and all 816 accepted regression
tests passing (849 total, no skips). The accepted counts are WP1 236, WP2A 18,
WP2B 22, WP2C 24, WP2D 52, WP3A 110, WP3B 150, WP3C 33, WP4A 20,
WP4B 98 and WP4C 53. The WP2B administrator-replacement fixture now refreshes
WP4D's fixed reservation references, and WP2C's closed resource list includes
the protected cleanup alias. Initial source admission captured concurrent final
edits; it was rerun successfully after the candidate stabilized.

All 16 packages rebuilt deterministically and matched the declared hashes;
exact-version synthetic extraction and preserved WP3 package checks passed.
Eight provider-free Terraform gate/policy/trust cases, generated wiring, source
inventory, 104 Python ASTs, 17 JSON files, Terraform check-only formatting,
packaged Bash syntax, changed-document local links and `git diff --check` passed.
Synthetic positives establish representable permissions and prerequisites;
negative cases reject foreign environments/roles/targets, missing conditions,
unbound versions and incomplete resource membership. They establish no live IAM,
AWS membership, image installation or operational readiness. Existing Linux E3
and provider/live verification gaps remain open.
