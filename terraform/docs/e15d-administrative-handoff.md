# E15-D — protected administrative handoff and artifact storage

CURRENT CONTRACT, 2026-10-12. Baseline main/HEAD:
`e0fc9941210ab4cb276b566970546d5e28872fc6`; existing batch1 checkout,
`codex/e15d-administrative-handoff`. **PARTIALLY_READY overall; full DOWN remains
denied.** No AWS operation, including reads/STS, provider initialization, remote
state, IAM installation, deployment, teardown or remote Git operation occurred.

## Gap assessment and reused authority

[WP5](e1-protected-environment-lifecycle.md) already supplies closed requests,
protected current configuration, installed package/image admission, fixed backend,
saved-plan application and terminal readbacks. [E15-B](e15b-dev-down.md) supplies
DEV scope, two separate destructive confirmations, context seal and local review.
[E15-C](e15c-exact-destroy-approval.md) supplies exact approval validation and the
single-use WP5 journal. Its administrative/acquisition/current-state ports were
abstract and the real runtime did not wire them. Missing were actual SDK session
verification, private publication/version reads, a deterministic cross-invocation
selector and an accepted storage installation/permission boundary.

This increment adds [one adapter](../../scripts/lifecycle/handoff.py), reusing
E15-C's approval and E15-B's identities unchanged. It does not install authority,
redesign planning, create a role/service/workflow or implement ECS/NAT quietness.
WP7 retired code remains historical, not an alternative operational entry point.

| Capability | Classification |
| --- | --- |
| Concrete SDK session/storage adapter and exact cross-invocation selection | READY_IN_REPOSITORY; uninstalled |
| WP5 administrative API and protected executor wiring | READY_IN_REPOSITORY; end-to-end installation PARTIALLY_READY |
| Internal preparation publication under an existing distinct WP5 plan owner | READY_IN_REPOSITORY; accepted preparation dispatch/installation route still required |
| Narrow storage access/denies and external admin installation | REQUIRES_OWNER_DECISION before protected installation |
| Authentic AWS sessions, S3 IAM/versioning/atomicity and Terraform state/locking | REQUIRES_LIVE_AWS_VALIDATION |
| ECS controller/scheduler closure, NAT retries and issued-effect settlement | Independent blockers; DOWN stays denied |

## Exact trust chain; no self-declared administrator

The neutral security root selects an **existing separately held human admin**;
ordinary WP5/WP6 identities cannot assume or install it. The current root permits
an existing IAM user or role, but this adapter deliberately supports only a role
session. An IAM-user-only installation needs an explicit accepted role decision;
there is no fallback or automatically created role. The role's human trust/MFA/SSO
policy stays external administration, not an invented GitHub admin workflow.
[WP6](e1-protected-workflows.md) continues to authenticate only its eleven request
identities with exact repository, audience, environment and immutable entry claims;
those OIDC sessions are not administrative approval authority.

Current administrator-owned WP5 `bootstrap.exact_destroy_handoff` must pin a
`{bucket,key,version_id,sha256}` installation record at the fixed location:

```text
demo-release-artifacts-<account>/lifecycle/environment-lifecycle/infra-high-risk-dev/handoff-installation.json
```

The exact encrypted version contains `schema=E15D_HANDOFF_INSTALLATION_V1`, binding,
account, region, package revision/source commit, administrator role ARN and its
unique RoleId, exact existing executor RoleId, and the accepted installation
contract `E15D_PRIVATE_VERSIONED_CONDITIONAL_NO_DELETE_V1`. It is external
administrator-owned installation evidence, not a public request or local proof.
The storage contract name is an obligation on the installation administrator,
**not a runtime verification of bucket policy/versioning**. The role IDs must be
independently acquired and verified during that future installation. No such
record/reference or installation is populated in this repository.

The adapter compares real SDK `get_caller_identity()` account, assumed-role ARN
and `UserId=installed_RoleId:session_name`, rejecting another account, workload
role, session or recreated role with the same name. The principal comes from the
service response, never CLI fields/environment identity labels. Administrator and
executor role IDs must differ. Approval requires the admin session; executor
resolution requires the exact existing `e1-controller-infra-high-risk-dev-exec`
session. Authenticated withdrawal can resolve the same evidence as administrator.
Missing storage/identity/installation/ref/version/hash fails closed. A Boolean
cannot create installation or approval. Runtime client construction is SDK-based;
test doubles are dependency injection inside hermetic tests, never an installed
fixture mode or activation switch.
[AWS STS describes the identity response](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html).
There is no STS/IAM invocation during this task and no new AssumeRole/PassRole grant.

## Private exact publication and resolution

All paths derive from E15-B's DEV account/environment/binding/operation UUID and
scope digest, which also bind layer/backend/workspace, revision, source, request
and installed membership. No public input selects a bucket/key or arbitrary plan.
Preparation uses the existing lifecycle bucket's own operation prefix:

```text
operations/environment-lifecycle/infra-high-risk-dev/<uuid>/exact-destroy/plan.bin
operations/environment-lifecycle/infra-high-risk-dev/<uuid>/exact-destroy/plan.json
operations/environment-lifecycle/infra-high-risk-dev/<uuid>/exact-destroy/prepared.json
```

`publish_prepared()` requires the exact installed executor session, already sealed
runtime binary/JSON, a current original E2 owner for a **distinct existing WP5
plan request** of the same layer/revision/parameters, and state/configuration
readbacks. It does not acquire, finish or release ownership. Preparation records
N; that plan owner must safely finish/release before destruction acquires N+1.
Reusing the teardown UUID as preparation would conflict with E2's terminal replay
contract and is rejected. Public WP5 `plan` still means its existing normal plan;
this method does not turn it into an unapproved destroy-preparation request.
An accepted protected dispatch route for this internal preparation step is still
an installation/architecture prerequisite; no parallel orchestrator is created.

Binary and canonical JSON publish first; `prepared.json` publishes last, pinning
those versions and the existing review/seal/generation packet. Writes use
`IfNoneMatch='*'`, SSE-S3 `AES256` and `ExpectedBucketOwner`. Bounded reads request
the exact VersionId and compare returned version, bytes digest and encryption.
The manifest preserves E15-B context and E15-C generation formats. Rendering uses
approved Terraform `show -json` on a fixed private `wp5-review.tfplan`, independent
of the executor's final `wp5.tfplan`. Repeated rendering rejects binary substitution.
Current configuration and exact layer state are read through fixed SDK paths;
state lineage, serial, VersionId and bytes hash must match the approved context.
Terraform's saved-plan applicability/locking remains an independent real check.

The admin API acquires the same admitted package, authenticates before Terraform
preparation, reviews exact stored artifacts and uses E15-C `issue()`. Its unchanged
approval schema publishes at the E15-C fixed `approval.json` path. A final
write-once `selection.json` under the same admin-only operation directory binds
scope/request hashes, the prepared manifest exact reference and approval exact
reference. Publication of a selector is not a second approval or a lock.

A new invocation derives the one selector key from its protected operation; it
never lists candidates, accepts a caller reference or chooses a newer plan.
Fixed immutable anchors are discovered once and immediately read at their exact
returned version; executors then follow only pinned manifest/artifact/approval
versions. Changes of the selection within an invocation reject. Cross-invocation
immutability requires the accepted no-overwrite/no-delete installation, including
admin operations: versioning alone is **not** that guarantee. Foreign/missing or
corrupt scope/ref/bytes, conflicting publications and stale approval fail closed.
The approval cannot be refreshed to reopen a consumed operation.

Multi-object S3 writes are **not a transaction**. A failed or lost binary/manifest/
approval/selector acknowledgement is not retried. A partially published sequence
cannot be considered ready without the complete selected version graph. No new
plan replaces a failed publication under the same UUID; evidence stays retained
and safe reconciliation is required. Delete markers can allow new conditional
creation, so routine deletion must be denied for every handoff/decision object.
[AWS documents conditional creation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
and [version-specific read permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html).

## Minimum permissions: proposed, not installed

`storage_requirements(scope)` produces exact per-operation object ARNs and
installation obligations for review; it grants nothing and is not Terraform.
The actual WP5 IAM policy/generator/trust/PassRole remains unchanged.

| Participant | Existing or proposed narrow needs |
| --- | --- |
| Protected plan preparer | Existing own conditional Put/Get journal and exact state/config/package reads; additional exact-version reads of binary/JSON/manifest and installation |
| Existing separately held admin | Exact-version private prepared artifacts/package/installation, current config/state and fixed selector reads; conditional writes only approval/selector and authenticated withdrawal decision |
| Exact DEV high-risk executor | Fixed selector GetObject, installation/approval/artifact GetObjectVersion, existing exact state/current config reads and own conditional decision/attempt writes |
| Ordinary requester/delivery/workload | No handoff writes, no private plan/approval reads, no admin session or new grants |

New `s3:GetObjectVersion` must be constrained to accepted exact object resources
and, where installed, `s3:VersionId`. Fixed selector discovery additionally needs
`s3:GetObject`. No ListBucket, arbitrary S3 administration, delete, wildcard action,
IAM read/write or broad PassRole is introduced. Installation needs actual private
bucket access, TLS, enabled versioning, SSE-S3, conditional-create enforcement and
no overwrite/delete (including routine admin) on the fixed namespaces; only admin
may publish installation/approval/selection. Existing own journal grants do not
alone supply those bucket guards or exact-version reads. These narrow additions
must be approved through the **existing separately authenticated security-root
installation and WP5 exact package/image/publication gates**. They are not silently
inserted in generated IAM or accepted by populating a local fixture. Admin storage
at this new prefix and private-plan version reads remain installation blockers.

## Runtime, single use and safe DOWN denial

`runtime.execute()` now constructs this adapter for DEV teardown only, from current
protected installation and fixed clients, and connects it to E15-C `Execution`.
Missing installation rejects before a generic plan can be generated. The executor
loads/inspects only the selected approved saved binary. Package verification now
also compares installed `dev_down.py`, `exact_destroy.py`, `handoff.py` bootstrap
bytes; eight derived package identities include the new source. No external
identity, active contract, runtime approval or compute binding is activated.

The internal `runtime.approve_destroy()` API is separately administrative. It is
**not exposed by the public gateway/handler or an operator CLI**. It rereads protected
configuration, verifies the admin session and exact package, prepares fixed tools,
and publishes the existing E15-C approval/selector. It returns a reference only,
not binary/JSON/state. No raw sensitive plan values, credentials or DB contents are
logged or committed. Keep private artifacts and ephemeral review directories private.

The existing E15-C `decision.json` is still the only authoritative consumption/
withdrawal slot: both compete using conditional creation. No second distributed
lock, update/delete/reset or check-then-write claim is introduced. Crash after
claim burns approval; attempted dispatch/response loss stays UNKNOWN and never
blindly resends. Intent/public/completion and terminal readbacks remain WP5-owned.
E2 ACTIVE/interrupted owners and E4 uncertainty remain blocking; no takeover or
release of an already issued effect is claimed. The concrete adapter's quiescence
method always denies: ECS/schedulers and NAT retries/in-flight effects are unresolved.
Thus even authentic approval cannot cause this installed adapter to dispatch DOWN.
The operator `down-execute` also remains denied. Ordinary/non-destroy/PROD paths
are unchanged; DEV disposal consent does not authorize shared/PROD destruction.

## Operator runbook and future acceptance

The existing [E15-B local commands](e15b-dev-down.md#operator-procedure-and-supported-commands)
remain available; `down-review` validates only local consistency and drafts exact
independent DEV destruction/SQL-loss acknowledgements. It does not authenticate an
AWS admin or publish approval. No new CLI is invented for an uninstalled API.

Future, separately authorized installation must accept the storage/principal
boundary, install verified package/image/config refs and a protected preparation
route, then acquire/review/private-publish through the admin API and resolve through
WP5. Both confirmations and E15-C applicability/expiry remain mandatory. Before
any real DOWN, independently finish ECS/controller/scheduler closure, NAT issued-
effect settlement and genuine readbacks. Retain shared/secrets/security root,
backend/state/locks, ECR and audit/reconstruction evidence. Monetary budget and alert
recipient/threshold decisions remain unchanged and outside this increment.

Live acceptance must prove authentic admin/executor session and unique RoleId
attribution; IAM and external actor denial; private version/encryption/conditional
and no-delete controls; exact artifact graph and selector immutability across
invocations; lost ACK/partial-publication and claim/withdraw contention; state drift
and Terraform locking; genuine E2 generation/fencing; ECS/NAT settlement and WP5
terminal readbacks. A provider-free SDK double proves none of these AWS behaviors.

## Offline validation

`python -I -B scripts/tests/handoff/run.py` runs 50 hermetic tests against actual
SDK-shaped publication/load/selection, STS session validation, admin/runtime entry
points and E15-C journal calls. Installation metadata, service responses and
Terraform rendering are explicitly synthetic fixtures. Deterministic barriers
exercise claim/withdraw races without timing sleeps. The protected executor test
resolves approval, retains UNKNOWN and never dispatches Terraform because quietness
is uninstalled. E15-C's 46 tests continue covering lost execution responses/crashes
at the separate existing abstract boundary, not proving this adapter can execute.
The E1 gate includes this check while preserving 983 E1/WP and AC1–AC16 requirements.

## Accepted offline results

Full E1 acceptance passed: 959 regressions + 24 WP7 = 983, AC1–AC16, E2 41,
E2-R 23, E4 28 and all 18 additional checks, including E15-D 50, E15-C 46,
E15-B 42, E15 30, E8 18 and E13 40. Independent E11 33, E7 8 and E14-B 19 passed.
The gate also passed actual package extraction/hashes, source inventory,
authoritative security/workflow generation, IAM/trust/PassRole/installation,
KDD links, parsing (167 Python, 50 JSON, 22 generated YAML), Terraform formatting
and whitespace. Activation remains 0/11 external, 0/16 WP4D, 0/8 WP5.

Installed offline Ubuntu TFLint/tfsec reproduced exactly the accepted 24 warnings
and 46 findings, by rule/severity/file/resource/message multiplicity; none added
or removed. Inherited nonzero lint exits are not described as clean lint. One
bounded self-acceptance checked 174 Terraform/HCL files unchanged, only eight
derived WP5 hashes changing authority, reviewed source admission and no IAM/trust/
PassRole/activation expansion. Native E3/app and unchanged shell suites were not
rerun because their implementation inputs are unaffected.

Reports outside the checkout bind precommit source content at baseline
`e0fc9941210ab4cb276b566970546d5e28872fc6`. No executable source changed after the
full gate; these result paragraphs were added afterward and checked separately.
No live SDK client or fixture installation activated AWS authority. The concrete
adapter is repository code, not live session/storage enforcement or teardown
proof; E15-D remains partial until the named installation/owner/live gates close.
