# E1 WP5 protected environment lifecycle — implementation candidate

WP7 milestone disposition: the stage narrative below records its accepted package.
Legacy overlap is now retired; see [final E1 repository contract](e1-final-acceptance.md).
Installation/governance/live evidence remains unverified and compute stays inactive.

Starting revision: `66857ed70b21e56798720fd060434b7434db1f99`.
This implements [approved plan section 6.2](../../specs/iam-hardening/plan.md#62-legitimate-lifecycle-through-protected-terraform-execution).
It is an offline repository candidate, not an integrated acceptance or an AWS
installation. There is no migration, adoption or coexistence path.

## Protected execution and ownership

The eight existing [WP2 reservations](e1-controller-compute.md) supply four
Lambda gateways and four CodeBuild projects: ordinary/high-risk, each dev/prod.
Gateways receive only operation UUID, operation, layer, installed revision and
bounded parameters. The current routine parameter is data `enable_alarms` (bool).
Ordinary layers are shared, secrets, global, platform and edge; high-risk also
owns data/apps and approved full teardown. High-risk mutations require an exact
protected operator approval; teardown additionally requires its own exact
environment/layer/revision approval. No public identity is activated by WP5.

Each gateway verifies its own currently active package and the selected downstream
package before submitting only the exact CodeBuild project name. Conditional
request objects and a protected build-ID mapping deliver the request without
source, environment, image, role, command or buildspec overrides. Every invocation
rereads admin-owned `lifecycle/<binding>/current.json` configuration. Retained
packages/images/endpoint versions cannot bypass a revoked active contract.

The installed runtime extracts verified bytes, compares its privileged bootstrap
Python bytes with the package and executes the fixed Terraform binary using the
approved readonly provider mirror and reviewed locks. Caller environment injection,
backend replacement, hooks, plugins, provisioners and arbitrary HCL are absent.
The future live runtime uses readonly init; no init, provider or AWS call is part
of offline validation.

All seven original roots are represented under `terraform/modules/target/<env>`.
Platform/edge complete the WP2 extraction; secrets remain a protected metadata
consumer. Shared ordinary ownership contains SNS, not IAM/KMS/ECR/storage.
SQL uses an exact admin-selected AMI and pinned user-data/profile. Password and
connection-string bootstrap stays outside Terraform values/state. Apps retain
role-free, secret-free, zero-count bootstrap, Fargate and disabled Exec. Task
revisions/counts and ALB actions remain ignored by Terraform and owned by WP4.

Reconciliation rejects replacement, execution-binding changes, authorizing-tag
changes and unexpected drift. Only independently identified drift in the exact
delivery-owned fields is admitted. Service/listener replacement requires approved
teardown at zero, separate create, then qualified normal delivery. Authoritative
ECS observations require the exact cluster/two services and complete running/pending
task listings; only exact ECS MISSING observations establish absence. Nonzero,
partial, ambiguous or wrong-environment observations reject. Lost mutation/readback
acknowledgements retain UNKNOWN; retrying a UUID cannot apply again. The [E2 arbitration adapter](e2-environment-mutation.md) now holds environment
mutation ownership through this existing plan/apply/readback contract.

## IAM and protected inputs

The explicit action inventory is [wp5_iam.py](../../scripts/tests/security_root/wp5_iam.py);
the saved-plan contract is [contract.py](../../scripts/lifecycle/contract.py).

| Principal/trust | Actions/resources/conditions | Protected input and boundary |
| --- | --- | --- |
| `e1-gateway-infra[-high-risk]-<env>-exec`, Lambda service | Exact downstream StartBuild; exact-version packages; own/partner current configuration reads; conditional own request writes; own logs | Current active set, exact package and fixed request; no skeleton API grant |
| `e1-controller-infra[-high-risk]-<env>-exec`, CodeBuild service with exact project SourceArn/account | Explicit create/existing/read inventory for own environment; published exact ARNs for existing writes; typed/tagged new graph dependencies | Fixed source/locks, protected graph and live existing-ID membership; no caller access to execution role |
| Same project | Exact env flow-log PassRole to `vpc-flow-logs.amazonaws.com`; NAT PassRole to EC2; SQL PassRole to EC2 only on high-risk | No ECS task/execution PassRole, profile replacement or IAM administration |
| Same project | Own permitted layer state Get/Put; lock Get/Put/Delete; own conditional operation records | Separate env bucket and exact layer keys; no state delete, security/evidence/eligibility/package/config writes |
| Separately held security admin | Owns IAM/policies, active contracts, publications, images, state buckets, launch templates and installations | Authenticated installation/publication ports, never assumable by lifecycle controllers |

EC2/ELB/AutoScaling unscoped Describe APIs and Logs DescribeLogGroups have explicit
read actions, separate statements and requested-region conditions. ECS ListTasks
uses an exact cluster condition. No mutation grant uses Resource `*`.
Generated IDs cannot be named before creation. EC2 multi-resource creation splits
parent authorization, tagged typed children and creation-only CreateTags.
Existing-ID validation and installed graph membership remain mandatory; tags/names
alone never authorize caller code. ELB listener/rule creation authorizes parent
ALB/listener resources. API Gateway POST uses root/child collection ARNs, with only
installed integrations/routes/stages admitted. No domains, authorizers or caller
integration credentials are granted.

SQL launch separately authorizes exact image/subnet/SG; instance with fixed
profile/type/IMDSv2; encrypted volume; and private ENI. Conditions are applied to
their applicable resource types. Primary references:
[EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html),
[ELB](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elbv2.html),
[ECS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html),
[AutoScaling](https://docs.aws.amazon.com/service-authorization/latest/reference/list_autoscaling.html),
[API Gateway V2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_apigatewayv2.html).
IAM conditions cannot express the entire installed graph or every ECS request
field; protected execution supplies the remaining boundaries. Live behavior is
unverified. Lifecycle permissions exceed the aggregate inline ceiling; admin
splits exact project statements into at most eight customer-managed policies,
each checked against the 6,144-character limit before creation. These are not broad
AWS-managed policies. Execution roles cannot edit policy versions/attachments.
See [IAM quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html).

## Installation and bootstrap gates

Packages are canonical JSON with sorted exact paths/base64 normalized bytes:
all environment roots/modules, reviewed provider locks, fixed SQL user data and
four runtime sources. Eight binding-specific hashes include WP2 reservations and
exclude self-referential hash maps. The authenticated AdminBundleStorage port
installs at `e1-control-bundles-<account>-<region>/bundles/sha256/<hash>.json`.
VersionId comes only from conditional storage response and exact-version readback.
Identity binds package, consumer and reviewed immutable source commit. Approved
images bind that package/source to an immutable ECR digest and tool/mirror contract.

LifecycleAdminChannel publication requires complete authoritative observations and
installation/image/configuration checks, then validates the returned configuration
VersionId and bytes. These are externally authenticated admin ports; JSON owner or
status labels do not authenticate anyone. No live AWS port implementation is
claimed by provider-free mocks.

Security root declares separate versioned, encrypted, public-blocked dev/prod state
buckets, without force destroy. Resource policy excludes unrelated controllers and
environments. Service-linked roles and state/publication readiness require admin
verification. Required root inputs derive from installed source; missing inputs or
replaced backend/account/region deny compute.

Global can create two EIP foundations before NAT activation. Admin-owned NAT launch
templates preserve reviewed fixed iptables user data/profile and accept only exact
verified network/AMI inputs. Outputs are unverified candidates, not installations.
ASGs require integer template versions and verified installation of all three WP4
handlers with exact runtime membership. No `$Latest`, caller user data, template
mutation or new failover algorithm is added. Empty bindings create no templates or
ASGs. The original NAT alarms remain installed-source skeletons gated with ASGs.

Registries remain empty: zero WP5 gateways/projects or NAT templates/ASGs are
active. All 16 WP4D bindings remain inactive; eleven external identities remain
inert. AWS IDs/VersionIds, membership readbacks and installed runtime/provider
mirror remain genuine prerequisites, not fabricated repository evidence.

## Bounded validation and remaining work

Focused tests cover lifecycle/authority positive and negative tuples, installation
and publication, revocation, runtime ownership and saved plans. Static checks
evaluate actual generated gate, policy, policy-size and service-trust expressions
in a disposable provider-free root. Synthetic fixtures prove no live authorization.
The focused suite executes 49 tests with zero failures, errors or skips. Eight
actual Terraform expression cases cover undeployed, fully synthetic, missing
partner installation, malformed installation identities, revocation and replaced
backend inputs. Existing WP4D expression and deterministic package checks also pass.
All twelve accepted regression suites pass: 849 existing tests plus 49 WP5 tests,
898 total, zero failures/errors/skips. Two WP2D assertions were mechanically
updated for provider-only roots, the exact NAT skeleton declarations and the
earlier WP5 source-admission diagnostic; their complete 52-test suite was rerun.
Source inventory (489 entries), generated model/wiring, Python/JSON parsing,
check-only Terraform formatting, local documentation links and staged diff
whitespace checks pass. Provider-backed validation was not initialized.
The bounded self-check corrected IAM size, creation dependencies, package selection,
expected delivery drift and exact absence handling. No independent adversarial
review cycle or architecture decision was introduced.

WP6 owns GitHub/OIDC workflow cutover/external activation. WP7 owns legacy retirement
and final acceptance. WP5 is not integrated; E1 is not complete. Live IAM/provider
execution, installation, membership and fresh Linux E3 remain unverified.

## E13 administrator maintenance extension

[E13](e13-nat-reliability.md) supersedes the original extracted NAT bootstrap
bytes with a fixed completion marker and readback checks. Exact AMI, integer
launch version and user-data hash remain administrator owned. Routine reconcile
still rejects launch-binding changes. Patch approval preserves network/profile/SG
and configuration identity and requires separately observed versions plus an
explicit single-AZ maintenance window; no caller or recovery-role launch control
is added. Live rollout and end-to-end forwarding remain unverified.

## E15-E/F combined DEV quiescence boundary

[Combined contract and remaining decisions](e15ef-combined-quiescence.md) wires
separate ECS/NAT guards into protected WP5/E15-D, with immutable UNKNOWN evidence
and the original E2 hold. Whole-operation ownership/stage order, terminal ECS
cluster handoff, installed authenticated adapters and issued-effect settlement
remain unavailable. Complete DOWN stays denied; no IAM or activation is added.
