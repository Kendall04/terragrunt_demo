# E15-B — safe DEV teardown preparation

CURRENT CONTRACT, 2026-10-12. Initial HEAD:
`28116d7dcbda3e037a568ee43167bd8814082737`; local branch
`codex/e15b-dev-down` in the existing batch1 checkout. No AWS operations,
provider initialization, installation, deployment or remote Git operation occurred.
This increment is **PARTIALLY_READY**. Complete DOWN/EXECUTE remains denied.

## Recovered implementation and remaining blockers

[E15](e15-ephemeral-lifecycle.md) already implements five offline report modes,
217 declaration/implicit inventory entries, retained-resource and budget drafts,
and WP5 per-layer teardown terminal readbacks. WP3 qualification and WP4 delivery
already supply exact immutable digest/manifests, protected release eligibility,
independent production approval and prior-success restoration. None is replaced.
[WP7 retired sources](../../ci/authority/retired) are historical provenance.

| Capability | Classification and boundary |
| --- | --- |
| DEV loss consent, runtime binary/context seal and fresh ECS pre-apply readback | READY_IN_REPOSITORY; REQUIRES_LIVE_AWS_VALIDATION |
| Local scope, artifact identities, destructive summary and consent draft | READY_IN_REPOSITORY; cannot approve or execute |
| ECS workload/controller/schedule closure | PARTIALLY_READY: current snapshots checked, no authorized active-color stop |
| NAT executor and issued-effect settlement | PARTIALLY_READY: reproducible race witnesses; no safe retirement authority |
| Exact reviewed-plan approval handoff | PARTIALLY_READY: local review and same-invocation integrity, no protected cross-invocation handoff |
| Full DEV DOWN and UP after reconstruction | PARTIALLY_READY; REQUIRES_LIVE_AWS_VALIDATION after architectural gates |
| Budget, alert parameters, recipients and log preservation | REQUIRES_OWNER_DECISION |
| Live resource absence, notifications and residual billing | REQUIRES_LIVE_AWS_VALIDATION |

## Owner-approved DEV SQL policy and explicit consent

All SQL data belonging exclusively to **terragrunt_demo DEV** may be permanently
lost during DOWN. No SQL backup or new snapshot is required. Existing backups,
PROD, other projects, shared resources, security root, Terraform backend and
protected audit/reconstruction evidence remain outside that decision.
Approval of this policy does not authorize an AWS operation during implementation.

[DEV scope](../../scripts/lifecycle/dev_down.py) binds application, environment,
account, region, high-risk lifecycle binding, operation UUID, layer, package
revision, installed source commit, installed-layer digest, request digest, exact
DEV root, backend bucket/key/region and default workspace. Only the five existing
DEV teardown layers can be reviewed. Identity mismatches fail closed.

For an existing **DEV data teardown** request, the administrator-owned WP5
`teardown_approvals` dictionary must also contain
`dev-sql-loss/<operation_uuid>`. This extra entry has exactly:

- `schema`: `E15B_DEV_CONSENT_V1`.
- `scope_sha256`: the exact derived DEV scope digest.
- `issued_at`, `expires_at`: explicit integer UTC Unix seconds; no default expiry
  or owner-approved time SLA is invented.
- `destroy_ack`: `DESTROY terragrunt_demo DEV <account> <region> <operation_uuid> <scope_sha256>`.
- `sql_loss_ack`: `PERMANENTLY LOSE terragrunt_demo DEV SQL DATA <account> <region> <operation_uuid> <scope_sha256>`.

Both phrases must match independently and the window must be current. Missing,
incorrect, expired, future-dated, cross-operation, cross-layer or changed-membership
consent is rejected. It supplies no credentials or database contents. Existing
request approval and teardown environment/layer/revision approval remain mandatory.
The public request schema does not accept caller-selected consent or a force flag.
The record must reach the controller through the existing independently authenticated
administrator-owned configuration channel; the local CLI never publishes it.
That channel's genuine installation/publication remains an external prerequisite.

[Controller](../../scripts/lifecycle/controller.py) checks consent before preparing
or planning and again before applying. The runtime additionally rechecks exact
DEV data request and consent after final readbacks at subprocess dispatch. Expiry
after intent persistence returns existing UNKNOWN evidence without apply. A valid
dispatch does not cancel an already issued AWS effect if consent expires while it
runs. Reusing the same UUID reads its
retained terminal/uncertain result without applying again, even after expiry;
consent is not reusable for a new request or a changed request. Reading historical
SUCCESS does not freshly verify AWS. Production behavior is unchanged; DEV consent
can never grant production authority. Resource destruction of other layers still
uses WP5's existing exact approvals; data-layer removal additionally needs the
independent SQL-loss phrase.

## ECS quiescence: snapshot versus closed mutation sources

WP5 already observes the exact installed DEV cluster and both fixed service names,
service desired/running/pending counts and bounded full RUNNING/PENDING task lists.
It accepts exact authoritative missing-resource responses, rejects incomplete or
ambiguous observations and requires all counts/tasks zero. E15 requires the same
independent observation after empty complete Terraform teardown readback.

[Runtime](../../scripts/lifecycle/runtime.py) now repeats this observation before
saved destroy apply, including at the final subprocess boundary after the E2 guard.
A requested zero count, stopped task request, service with positive desired count,
still-running task, missing readback or growth between checks blocks execution.
No new ECS mutation or IAM read is introduced.

This proves only the observed snapshot. WP4 normal delivery requires positive
replicas; existing cleanup stops only the inactive color and requires active
capacity. Neither authorizes stopping the active workload. A still-installed
controller/schedule can reactivate zero services, and per-layer E2 ownership does
not hold one exclusive owner across the whole reverse-layer sequence. A future
accepted bounded shutdown operation must close competing delivery/promotion/
rollback/schedules, stop the exact services through authorized authority, preserve
operation/effect evidence and observe actual termination under arbitration.
No such operation or new role is improvised here; DOWN/EXECUTE remains denied.

## NAT quiescence: demonstrated blocker, no false quiet flag

[E13](e13-nat-reliability.md) uses three distinct authorities: source/destination
check, NAT EIP assignment and route recovery, with exact installed membership,
EventBridge, Lambda async retries, diagnostics/DLQ and ASG replacement activity.
They are security-root-owned. WP5 global owns network/ASG dependencies but cannot
retire these handlers. NAT authorities do not read the E2 application head.

Actual handler tests show that a late valid event still mutates after a local
quiet request and while an application E2 owner is ACTIVE. A controlled
interleaving pauses after membership verification but before EIP assignment:
changing a quiet flag cannot cancel the issued effect. Ambiguous retries retain
UNCERTAIN without resending. These are blocker witnesses, not a quiet-state
implementation or permission to disable security globally.

[Disabling an EventBridge rule](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_DisableRule.html)
can leave events matching briefly; it cannot retract delivered callbacks.
[Event retries](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-retry-policy.html)
and pending Lambda invocations must be accounted for. ASG desired zero alone
cannot establish replacement/callback settlement. A future approved contract
must fence all three mutation boundaries, handle environment membership,
ASG replacement and delayed/retried callbacks, retain failed-event diagnostics,
and prove executor termination or neutralization **and settlement of already
issued effects**. [E2-R](e2r-owner-recovery.md) demonstrates why an ownership
record change, last check or elapsed wait alone cannot prove that. No quiet state,
new IAM permission, force-unlock or takeover is added. Unknown effects block DOWN.

## Exact saved-plan integrity and the missing approval handoff

WP5 previously compared the saved plan's JSON digest, while its approvals bound
request/layer/revision rather than a separately reviewed binary destroy artifact.
The runtime now seals the actual bounded regular `wp5.tfplan` bytes before/after
JSON inspection, the selected JSON digest and prepared installed/configuration/
variables/workspace context. It fixes workspace to default, rejects changed
workspace/variables/backend/reference/configuration, absent/symlinked/substituted
binary bytes and mismatched selected JSON. It repeats the seal immediately before
applying the same saved file. It never replans after this seal or substitutes
`terraform destroy -auto-approve`. This same-invocation seal does **not** bind an
administrator's earlier approval to that binary or independently certify state.

[Terraform saved plans](https://developer.hashicorp.com/terraform/cli/commands/plan)
can contain sensitive values. Keep raw binary, JSON and configuration privately;
never commit them or place credentials in a preview. The local review emits only
exact addresses/types/IDs/actions and sanitized scope/digests, not before/after
contents, variables, database contents or raw configuration.

`down-review` requires already supplied private local binary and JSON artifacts
plus a context envelope `{request, protected, review_context}`. `protected` has
WP5's existing installed configuration shape. `review_context` has exactly:
`schema=E15B_DESTROY_REVIEW_V1`, `scope_sha256`, explicit integer `created_at`/
`expires_at`, `binary_sha256`, canonical-JSON `json_sha256`, `workspace=default`,
and `state={lineage, serial, version_id, sha256}`. Changes must be complete
installed-member deletes/no-ops; cross-scope/protected/create/update/drift/deferred
changes fail closed. It displays exact claimed state and source context, resource
summary and both required phrases. Missing binary cannot be replaced by a summary.

These are **UNTRUSTED_LOCAL_ARTIFACTS**. Matching local hashes cannot prove JSON
was generated from binary, authenticate state, certify current applicability or
create immutable approval. Local consistency checks reject changed artifacts,
state version/serial/lineage, scope, expiry or edited review. They always return
`execution_authorized=false`. No caller can turn these notes into authority.
A future protected acquisition/publication, exact immutable administrator approval
and single-use current-state consumption contract is still required. No runtime
accepts a locally reviewed binary as an execution request in this increment.

## Operator procedure and supported commands

Run from the repository root with explicit intended account/region. These commands
are offline reports only; successful exit means a report was rendered, never that
AWS UP/DOWN completed:

```powershell
python -I -B scripts/ephemeral_lab.py status --account <account> --region <region>
python -I -B scripts/ephemeral_lab.py down-preview --account <account> --region <region> --sql-policy DISPOSABLE
python -I -B scripts/ephemeral_lab.py down-review --account <account> --region <region> --review-context <private-context.json> --plan-binary <private-plan.bin> --plan-json <private-plan.json>
python -I -B scripts/ephemeral_lab.py residual --account <account> --region <region> --notes <private-notes.json>
python -I -B scripts/ephemeral_lab.py verify --account <account> --region <region> --notes <private-notes.json>
```

The second review invocation may add `--destroy-ack "<exact displayed phrase>"`,
`--sql-loss-ack "<exact independently reviewed phrase>"`, `--issued-at <seconds>`
and `--expires-at <seconds>`. All four must be present/current/correct. It emits
`consent_draft` with `LOCAL_DRAFT_NOT_PROTECTED_APPROVAL`. No file, remote object,
installation or approval is mutated. The older preview Boolean acknowledgements
only annotate the report; they cannot satisfy protected WP5 data consent. The
legacy preview policy selector does not reopen the approved owner policy; the
runbook supplies DISPOSABLE explicitly and still requires current exact consent.
Do not use synthetic test artifacts as genuine installation or AWS evidence.
`down-execute` rejects every invocation, including both preview confirmations.

Future live sequence after separate authorization and architectural gates: status
and exact protected preview, two DEV/data acknowledgements, WP5 approvals and E2
preflight, proven ECS and NAT closure, protected exact reviewed-plan consumption,
then **edge → apps → platform → data → global**, verifying each layer before
progression, followed by independent residual review. Dependencies are recovered
in [E15's graph](e15-ephemeral-lifecycle.md#ownership-and-dependency-graph).
Shared/secrets and security root are retained; backend/state must survive all
stages. A partially failed data stage stops before global; UNKNOWN/UNCERTAIN never
causes blind rerun, duplicate cleanup or optimistic SUCCESS. ACTIVE or interrupted
E2 owners and unresolved E4 recovery block conflicting mutations. Retain original
UUIDs, generations, evidence and holds; there is no administrative takeover.

## Residues, reconstruction and cost

The existing 217-entry inventory identifies runtime compute/network/service
candidates and retained shared/secrets/security/backend resources. Local notes
can classify expected retained resources, unexpected PRESENT DEV resources,
PARTIAL, UNKNOWN and **UNKNOWN_OWNERSHIP**. Ownership uncertainty and incomplete
absence evidence add blockers. Notes remain untrusted; neither empty parent state
nor an ABSENT note proves AWS child-resource absence or billing cessation.

Retain Terraform state/locking, security-root identities/installation, shared
alerts/secrets, KMS/SNS, ECR repositories and all images, protected manifests,
audit evidence/control logs and any existing approved backups. SQL root EBS and
exclusive runtime logs can be lost when their owning layers are destroyed; this
SQL loss is explicitly approved only with current consent. E8 retention remains
unchanged and image storage remains unbounded.

Potential residual charges include retained image/object versions, keys/secrets,
logs/alarms/queues/notifications and snapshots, plus any surviving SQL/NAT EC2,
EBS, allocated EIPs, Fargate tasks, ALB and transfer. DOWN is never promised $0.
Reconstruction uses genuine retained installations/backend/evidence, fresh exact
membership and provider/bootstrap/source approvals, protected plans and WP3/WP4
release/DB-KMS readiness. Old bindings cannot substitute for new AWS IDs.

Monthly budget, actual/forecast warning thresholds, recipients and scope remain
unset in E15's draft; no hard cap or automatic destructive shutdown is added.
The pre-existing `demo-dev-shared-alerts` versus E13 `demo-dev-alerts` mismatch
(and prod equivalent) remains a separate installation prerequisite. It does not
close any of the three DOWN blockers, so no SNS/IAM/generator expansion is made.

## Validation and future live evidence

Run `python -I -B scripts/tests/dev_down/run.py` for 42 hermetic tests. The existing
E1 gate includes it as an additional check, retaining the 983 E1/WP count and
AC1–AC16. Tests exercise the actual Controller/runtime/E2/NAT boundaries, faults,
controlled interleavings, replay/expiry, binary substitution, observations,
reverse-layer partial progression, CLI sanitization and residual classification.
Successful synthetic progression is test-only per-layer composition, not a new
production orchestrator or proof of live teardown.

Future explicitly authorized AWS acceptance must prove real configuration/package
installation and IAM/S3/current-version controls; protected approval acquisition
and consumption; state staleness/locking and actual provider schema; ECS controller/
schedule closure plus observed termination; NAT replacement/late events/async retry/
issued-effect settlement and DLQ retention; E2 contention/interruption and E4
uncertainty; exact reverse-layer terminal readbacks; independently enumerated child
and orphan EC2/EBS/EIP/ENI/ALB/ECS/API resources; retained state/evidence/ECR;
SNS delivery/residual billing; and a genuine DOWN → VERIFY → UP cycle. No lifecycle
preview, resource absence or runtime quiescence result from AWS is fabricated.

Local acceptance: `E1_REPOSITORY_ACCEPTANCE_PASS`, **983 E1/WP**, **41 E2**,
**28 E4**, **23 E2-R**, AC1–AC16 and all **16 additional checks** passed with no
failures/errors/skips. Additional focused checks passed **42 E15-B**, **30 E15**,
**40 E13** and **18 E8** tests. Separately **8 E7**, **33 E11** and **19 E14-B**
tests passed. The gate checked source admission, 161 Python/50 JSON/22 generated
YAML parses, deterministic package extraction/hashes, generated security/workflows,
actual provider-free IAM/trust/PassRole/installation expressions, empty-plan shape,
KDD links, immutable approved E1 contract hashes, check-only Terraform formatting
and diff whitespace. Activation remains 0/11 request identities, 0/16 WP4D, 0/8 WP5.

Ubuntu TFLint 0.64.0 returned exit 2 with the same 24 accepted warnings; tfsec
1.28.14 returned exit 1 with the same 46 accepted findings. Comparison included
rule/file/severity/message/resource where relevant and multiplicity, with no
additions/removals or suppression. One bounded self-check confirmed 174 unchanged
Terraform/HCL sources and unchanged authority except eight derived WP5 package
hashes. No new IAM/trust/PassRole, installation approval, backend/ECR cleanup or
activation was introduced. Reports live outside the checkout in the local temp
folders `e15b-final-acceptance-final` and `e15b-lint`. The first gate was interrupted
to correct final-dispatch consent expiry; only the consistent final gate above is
accepted evidence. This evidence paragraph and line wrapping were added afterward
and checked separately; no executable source changed after acceptance. Unchanged
.NET/application and E3 shell suites were not rerun. No local fixture establishes
real AWS teardown, current resource absence, secure approval acquisition or future
retention/quiescence. Full DOWN remains PARTIALLY_READY.
