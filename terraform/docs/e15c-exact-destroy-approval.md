# E15-C — exact DEV destroy approval and single-use consumption

CURRENT CONTRACT, 2026-10-12. Baseline main/HEAD:
`484995b299d99be06520fcd7476eecbf87476ac8`. Work is local on
`codex/e15c-exact-destroy-approval`, in the existing batch1 checkout.
No AWS operation (including reads), provider initialization, installation,
deployment, remote state operation or remote Git operation occurred.
**PARTIALLY_READY: complete DOWN/EXECUTE remains denied.**

## Reused guarantees and the actual gap

[WP5](e1-protected-environment-lifecycle.md) already authenticates closed requests,
checks active exact package installation and fixed roots/backend/layers/membership,
requires independent administrator-owned operator and teardown approvals, applies
a fixed saved binary plan under [E2](e2-environment-mutation.md), records immutable
intent before mutation and observes an independent terminal readback. UUID replay
returns retained status and cannot reapply. Ordinary/create/reconcile and PROD
lifecycle contracts are unchanged. [WP7 retired sources](../../ci/authority/retired)
are historical provenance, not an alternative deployment authority.

[E15-B](e15b-dev-down.md) already supplies exact DEV scope/review/consent identity,
binary/JSON/preparation-context integrity and current ECS snapshots. Its local
review is explicitly unauthenticated; neither local hashes nor generic request
approval authenticate the administrator's review of that exact binary.
E15-C adds [the narrow contract](../../scripts/lifecycle/exact_destroy.py), not a
new public lifecycle operation, deploy controller or replacement for WP5.

| Capability | Classification |
| --- | --- |
| Exact approval validation, protected-port publication/readback contract and journal consumption algorithm | READY_IN_REPOSITORY (contract/algorithm); PARTIALLY_READY end-to-end |
| Saved binary load/inspection, final approval/state/E2 checks and immutable attempted marker in WP5 runtime | READY_IN_REPOSITORY; default DEV destroy rejects absent installed handoff |
| Administrative session authentication, private prepared-artifact acquisition/publication and protected approval registry | PARTIALLY_READY: required trusted ports; no concrete installed AWS adapter |
| Narrow approval-storage authorization and administrator integration | REQUIRES_OWNER_DECISION before implementation/installation |
| Real S3 concurrency, version/deletion protection, Terraform applicability and IAM enforcement | REQUIRES_LIVE_AWS_VALIDATION |
| ECS controller closure and NAT issued-effect settlement | Independent remaining blockers; not implemented by E15-C |

## Exact evidence and approval identity

The approval reuses the existing E15-B review **without duplicating scope or state
formats**. Its scope binds application terragrunt_demo, DEV account/region,
high-risk lifecycle binding, operation UUID, layer, request/package/source commit,
installed-layer digest, fixed backend bucket/key/region and default workspace.
Only the existing five DEV DOWN layers are accepted. The review includes complete
exact destructive address/type/resource-ID/action summary, the reviewed binary
and canonical JSON digests, creation/expiry context and exact claimed state
lineage, serial, VersionId and bytes digest. Identical text summaries cannot
replace binary identity. Generic create/update/security-root/cross-scope changes
remain rejected. Existing WP5 authorization is still mandatory.

A protected prepared packet has exactly `binary`, `plan`, `review`, `seal`,
`artifacts`, `preparation_generation`. `seal` is E15-B's binary/JSON/context digests.
Artifact references have exactly bucket/key/version_id/sha256. Their fixed private
locations are in the existing lifecycle bucket:

```text
e1-lifecycle-dev-<account>-<region>
operations/environment-lifecycle/infra-high-risk-dev/<operation_uuid>/exact-destroy/plan.bin
operations/environment-lifecycle/infra-high-risk-dev/<operation_uuid>/exact-destroy/plan.json
```

Protected acquisition must return exact versions/bytes and inspect the same binary
using approved Terraform; E15-C compares that rendering to the supplied JSON.
The executor independently runs `show -json wp5.tfplan` on the acquired saved
binary too. Local fixture JSON is never treated as authenticated provider evidence.
The prepared packet's publication/acquisition adapter is not installed here.

`E15C_DESTROY_APPROVAL_V1` contains `state=APPROVED`, the exact review, seal and
artifact references, expected E2 generation, exact installed configuration digest,
both E15-B confirmations, attributable administrative identity and explicit
integer `issued_at`/`expires_at`. Approval expiry cannot outlive review or consent;
no default TTL or time SLA is invented. DEV data approval must use the same
administrator-owned `dev-sql-loss/<uuid>` consent already checked by E15-B.
Other DEV layers also require the two independently matching review phrases;
the SQL policy remains exclusive DEV disposal, not shared/PROD authorization.

The approval reference fixes bucket/key/VersionId/bytes digest. The narrow proposed
admin-owned storage path is:

```text
demo-release-artifacts-<account>
lifecycle/environment-lifecycle/infra-high-risk-dev/destroy/<operation_uuid>/approval.json
```

This is a **contract for a future protected handoff**, not an installed storage
path or a caller-selected file. E15-C does not create it, publish from the CLI,
change its bucket policy or grant its reads. The active reference must come from
independently installed administrative authority; event/CLI JSON cannot select it.

## Administrative authentication: supported contract, missing live adapter

`ProtectedPlanChannel` is an abstract trusted port, following WP5's existing
separately authenticated `LifecycleAdminChannel` model. It is not an authentication
implementation. `administrator_role()` must return the administrator ARN from
independently authenticated installation, preserving security-admin versus
ordinary infrastructure/delivery operator separation. `authenticate_admin()` must
verify the current execution context against that installation and return the
exact account/role ARN and attributable STS assumed-role principal ARN. The
contract rejects mismatched accounts, roles, sessions and extra caller claims
such as `approved_by=admin`. These ARN checks are validation of authenticated
channel results; **strings alone are not authentication**.

`issue()` calls this trusted authentication port, validates WP5 approvals and
current evidence/state/configuration, then asks the administrative channel to
publish the exact approval and independently reads back its exact version/bytes.
`validate()` uses the current installed reference and protected exact readback;
it rejects missing, revoked, altered, foreign, expired or substituted approval.
No public event supplies the channel, approver identity, approval or reference.
No concrete production subclass is provided. Tests explicitly substitute synthetic
trust ports; they never install roles or prove an AWS administrative session.

The minimum remaining authority/integration prerequisite is a genuine admin
publication/acquisition adapter and protected immutable storage/read control for
these artifacts/approvals and their active references. WP5 currently only grants
approval configuration reads at `lifecycle/<binding>/current.json`; it does not
grant reads of the proposed per-operation approval prefix. An eventual accepted
installation must supply narrow exact-object/VersionId reads and admin-only
immutable publication/registry semantics, or approve an equivalent handoff within
the existing protected configuration. No broad S3 read/write, new privileged
role, PassRole or IAM administration is added to solve this by convenience.

## Atomic single use and withdrawal

`DecisionJournal` implements actual SDK-shaped S3 `put_object`/`get_object` calls
at the existing own-operation journal prefix, always using `IfNoneMatch='*'`.
It requires returned exact VersionId and matching fresh bytes/version readback.
No check-then-write lock or process-local flag supplies exclusivity. The atomic
service primitive is S3 conditional creation; deterministic doubles test algorithm
interleavings, not real service atomicity or installed IAM.
[AWS documents the conditional-write semantics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).
The current WP5 own-prefix policy already allows conditional create/read; no new
IAM grant is necessary for these two journal objects.

```text
operations/<binding>/<uuid>/exact-destroy/decision.json
operations/<binding>/<uuid>/exact-destroy/attempt.json
```

The **decision key is operation-scoped**, not version/generation-scoped. A renewed
approval cannot reopen a consumed operation. `decision.json` contains either
CONSUMPTION_CLAIMED (exact approval reference, executor-generated consumer UUID,
request hash and generation) or WITHDRAWN (same approval reference and independently
authenticated administrator context). Claim and withdrawal compete for the same
conditional-create slot: only one wins. Withdrawal cannot cancel an already
claimed/issued effect. Changing a mutable registry alone is not a concurrency-safe
withdrawal of an already-read approval; the shared decision slot is required.

A successful claim is followed by a separately immutable EXECUTION_ATTEMPTED
marker **before** Terraform dispatch. It means dispatch was reserved and may have
occurred, not proof that a process started or completed. No failed/lost write ACK
is retried or treated optimistically. If a write reached S3 but its response or
readback is lost, the journal remains potentially consumed and no apply follows.
A crash after claim but before attempt leaves consumed/not-attempted; a crash after
attempt leaves dispatch/remote effect UNKNOWN. Neither state authorizes automatic
reuse. No delete/reset/new generation, force-unlock or takeover is implemented.

| Evidence | Meaning |
| --- | --- |
| Protected APPROVED record, no known decision | Approved, not proven consumed; missing readback remains unknown |
| CONSUMPTION_CLAIMED, no attempt | Consumption reserved; no automatic continuation after crash |
| EXECUTION_ATTEMPTED | Dispatch reserved, effect may have started; never completion |
| Existing WP5 completed SUCCESS | Independent required readbacks observed success |
| Existing attributable pre-effect failure | Existing WP5/E2 failure behavior; approval may still be burned |
| Existing WP5 intent UNKNOWN / E4 UNCERTAIN | Preserve holds/evidence; never redispatch blindly |

These are substage evidence under WP5's journal, not a parallel terminal state
machine. The existing controller still owns intent/completed/public results. It
now retains the exact approval reference and binary digest in private intent and
completion metadata when the protected handoff is used. It never logs plan bytes.
A consumed approval is not SUCCESS. A nonzero apply, timeout, ambiguous response,
failed readback or persistence gap remains UNKNOWN under existing behavior; no
post-effect attributable FAILURE classification is fabricated.

## Executor and current applicability checks

[Runtime](../../scripts/lifecycle/runtime.py) accepts an internal `Execution`
instance only from protected installed code. No request schema, CLI flag or
arbitrary plan-file path can inject it. With that handoff, DEV destroy `plan()`
loads the exact acquired binary at fixed `wp5.tfplan` and inspects it; it does
**not** compute a new destroy plan. The E15-B context/seal must still match.
The same saved file is used by WP5 apply, with final seal verification.

At the final supported subprocess boundary, after existing E2 authority checks,
`before_dispatch()` revalidates current exact approval/artifact identities, request,
source/configuration, consent and expiry. It requires the original E2 owner,
request/domain/binding/operation and generation. Preparation records generation N;
approved execution must acquire N+1. Any intervening application-domain operation
invalidates that preparation rather than silently accepting stale applicability.
This is conservative, not permission to retain/reacquire an interrupted owner.
The future preparation adapter must independently acquire/release proven
preparation ownership; current WP5 has no installed cross-invocation preparation
publication/resume route, so this is an additional integration prerequisite.

The current-state port must return the exact lineage/serial/VersionId/bytes hash
and configuration digest. Checks repeat after quiescence and after consumption;
missing/corrupt/changed evidence blocks. The saved binary is never rebuilt to
accommodate changed state. These reads cannot themselves eliminate the final
read-to-send race; Terraform's real backend lock and saved-plan stale-state checks
must still be demonstrated with the approved runtime/provider installation.
[HashiCorp explains saved-plan serial/lineage checks](https://discuss.hashicorp.com/t/question-on-error-saved-plan-is-stale/52912/2).
No approval or CAS can cancel an already dispatched remote effect; E2-R's limitation
remains [explicit](e2r-owner-recovery.md).

The trusted port must also prove accepted ECS-controller/scheduler closure and
NAT executor/issued-effect settlement. There is **no implementation of those
proofs here**. A fresh E15-B task/service snapshot additionally remains mandatory.
Unproven ECS quietness, NAT quietness, E2 ownership or readbacks rejects even a
correctly approved plan. Active/interrupted owners and E4 uncertainty remain
blocked. No synthetic `quiet=true` flag is accepted from a public request.

`runtime.execute()` deliberately wires **no exact-destroy adapter**. Therefore
its current DEV teardown final dispatch rejects absent protected handoff even
if generic approvals and snapshots would otherwise pass. Ordinary plans, create,
reconcile and PROD behavior are preserved. Generic DEV teardown is not an escape
around the exact-plan contract. `ephemeral_lab.py down-execute` still rejects all
invocations. This increment supplies a tested integration boundary, not installed
remote single-use execution.

## Operator workflow and pending work

Existing implemented local commands remain STATUS, UP/PREPARE, DOWN/PREVIEW,
`down-review`, VERIFY and RESIDUAL; use the [E15-B commands](e15b-dev-down.md#operator-procedure-and-supported-commands).
No new approval/publish/consume/execute CLI is invented. Keep raw plan binary/JSON,
configuration and any state private: saved plans can contain sensitive values.
Do not commit or log them. The operator reviews exact private acquired binary,
its protected Terraform rendering and sanitized E15-B scope/summary, independently
acknowledges destruction and SQL loss, and obtains administrative approval through
the future installed channel. Local `down-review` output cannot perform that step.

Before real DOWN: finish and accept administrative acquisition/publication/current
reference integration and narrow protected storage, cross-invocation WP5 preparation
handoff, ECS closure and NAT settlement. Preserve shared/secrets/security-root,
state/locking/manifests/ECR and the reverse-layer order edge → apps → platform →
data → global. Budget/log/notification owner decisions remain separate; E15-C
adds no SQL backup, ECR cleanup, budget action, NAT controller or permanent service.

Future explicitly authorized AWS acceptance must verify authentic session and
role attribution, admin/operator separation, immutable private artifact/approval
storage and exact VersionId reads, current reference revocation, claim/withdrawal
parallel contention, no-delete/conditional-write enforcement, lost ACK/crash
behavior, state drift/locking and saved binary correspondence, genuine E2 fencing,
ECS/NAT proof/readbacks and WP5 terminal evidence. The project remains undeployed;
no live S3/IAM/provider/teardown evidence is claimed.

## Offline validation entry point

`python -I -B scripts/tests/exact_destroy/run.py` runs 46 hermetic tests against
actual approval validation, SDK-shaped journal calls, E2, Controller and Terraform
runtime boundaries, with deterministic barriers and fault injection. Both positive
executor progression and administrative context are explicitly synthetic ports.
The E1 gate adds this check without changing its 983 E1/WP count or AC1–AC16.

## Accepted offline results

The full E1 gate passed: 959 regressions + 24 WP7 tests = 983, AC1–AC16,
E2 41, E2-R 23, E4 28 and all 17 additional checks. The latter include E15-C
46, E15-B 42, E15 30, E8 18, E13 40, actual source admission, package extraction
and deterministic hashes, generated security/workflows, IAM/trust/PassRole and
installation gates, KDD links, Terraform formatting and whitespace. Independent
E11 33 and E14-B 19 tests passed. Parsing covered 164 Python, 50 JSON and 22
generated YAML files. Activation remains 0/11 external identities, 0/16 WP4D
and 0/8 WP5; authoritative Terraform/HCL files are unchanged.

Installed offline TFLint/tfsec in Ubuntu reproduce exactly the accepted 24
warnings and 46 findings, including rule/file/resource/message multiplicity,
with no new or removed findings. Their inherited nonzero exits are not relabeled
as clean lint. One bounded acceptance self-check confirmed only eight derived
WP5 package hashes changed in authority, with no IAM/activation expansion.
No executable source changed after the full gate; this results paragraph was
added afterward and checked separately. Reports reside outside the checkout and
bind precommit source content at the stated baseline. Native E3/app tests and
unchanged shell suites were not rerun because this increment does not affect them.
No synthetic trusted port is live authentication, service atomicity, installation,
quiescence or successful AWS teardown evidence. Overall E15-C remains partial.

## E15-D continuation

[E15-D](e15d-administrative-handoff.md) adds a concrete installed SDK session/private
storage/selection adapter and runtime wiring. The adapter absence described above
records E15-C's milestone. Protected installation/permission/preparation-route
acceptance and real AWS evidence remain unverified; ECS/NAT quietness always denies
DOWN. E15-C's exact approval schema, single-use journal and safety gates are reused.
