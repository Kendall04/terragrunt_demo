# E15-E/F combined protected DEV quiescence

CURRENT CONTRACT, 2026-10-12. Repository integration is provider-free; complete
DEV DOWN/EXECUTE remains **PARTIALLY_READY and denied**. No AWS operation, provider
initialization, remote state access, installation or Git remote operation is allowed.

## Preserved history and scope

Integration uses the existing batch1 worktree and `codex/e15ef-combined-integration`.
Initial main/E15-D: `ace06da4434b873b9fc1602f2befb4fa7d45cf44`.
Original ECS: `7ade83e7be0fae4af5c6c989dc860506edc38e77`.
Original NAT: `2d65513f56a2bf1229686bce2f6b05a46d17c594`.
ECS merge: `e0945816df94a0d32b4d2acfa405e9a21f3d0f4e`.
NAT merge: `554e903b0bc63178269982ea6cd57e8b7f28369a`.
Separate non-fast-forward merges preserve both commits and their common ancestor;
no merge conflict occurred. Main and both feature worktrees remain untouched.

The [ECS protocol](e15e-ecs-quiescence.md) and [NAT protocol](e15f-nat-quiescence.md)
retain their separate contracts. Their standalone validation narratives are historical;
neither completed the full acceptance gate. This integration registers both sources,
packages and suites. Repository acceptance does not install either adapter.

## Protected runtime composition

[Combined guard](../../scripts/lifecycle/quiescence.py) is imported by the fixed
[WP5 runtime](../../scripts/lifecycle/runtime.py). E15-D
`Handoff.require_down_quiescence` calls `Terraform.require_combined_quiescence`
after authentic executor-session/current-scope checks, inside E15-C's existing
exact-plan dispatch sequence and the original E2 call. It constructs the ECS
SDK adapter/journal with the concrete E15-D HandoffBoundary. The concrete boundary
still denies controller closure; no UpdateService is issued by installed wiring.
NAT's protocol is imported and admitted with its complete Python/data import closure.
Its installed configuration and observation source is explicitly absent;
`InstalledNAT.protocol` denies rather than inventing a WP5 bootstrap field,
unauthenticated NAT slot list or live observation adapter. Protected domain fixtures
compose the actual NAT Quiescence directly to test its network guard.

The guard records immutable UNKNOWN intent and content-addressed stage/phase
observations in existing WP5 Records at:
`operations/environment-lifecycle/infra-high-risk-dev/<uuid>/combined-quiescence/<layer>/`.
ECS keeps its versioned conditional journal; NAT keeps its own immutable UNKNOWN
intent and diagnostic observations, including E13 queue/effect diagnostics. Combined
evidence identifies these separately. No combined record is a remote settlement
receipt. Absent NAT installation produces a combined protected blocker without a
fabricated NAT readback. Storage failures deny progression; lost write responses
are resolved only by exact readback, never repeated writes.

Scope binds the exact request hash, DEV binding/account/region, source/package,
layer/backend/workspace and complete original ACTIVE E2 owner/generation. Both
protocols must share that Authority instance and owner; current correlation is
checked before collection and after publication. No receipt can transfer to another
request, layer, environment or generation. The guard never acquires/releases E2,
changes a head, finishes an operation or dispatches Terraform. Its denial cannot
be disabled by a fixture receipt, admin approval or Boolean installation flag.

| Boundary in accepted reverse graph | Required evidence and current disposition |
| --- | --- |
| edge → apps | Fresh ECS controller closure plus complete RUNNING-desired listing (including PENDING), remembered tasks STOPPED, settled deployments; refreshed at every gate; installed closure absent |
| apps → platform | Same original hold/inhibition and fresh ECS evidence after service deletion; missing services cannot erase remembered tasks |
| platform deletion and later data | Explicit handoff from remembered terminal tasks to authoritative cluster absence, continuous inhibition and original owner; handoff absent, so post-platform and data are denied |
| global networking | Same DEV operation/owner, preceding terminal stage evidence, ECS terminal handoff and NAT `require_network_teardown`; NAT always retains UNKNOWN and denies remote settlement |

Every stage also records `edge, apps, platform, data, global` ordering and its index.
There is deliberately no executable multi-stage advance API. WP5/E15-C requests
and approvals are per layer, including their request hashes; existing E2 finishes
successful layer ownership. An adapter receipt cannot join those owners into one
complete DOWN. The guard always includes
`WHOLE_DOWN_OWNER_AND_ORDERED_STAGE_HANDOFF_UNINSTALLED`. This is an explicit
fail-closed integration boundary, not a claim that stage ordering is authenticated.
A later accepted design must preserve one owner throughout the complete operation
while binding each separately reviewed exact plan and both confirmations. No new
lock or speculative approval/orchestration replacement is introduced here.

E15-C still loads the exact binary/JSON/state/configuration approval, checks the
expected E2 generation, then requires combined quietness before its single-use
claim and attempted marker. E15-D approval cannot bypass either guard. If a future
apply reaches verification, WP5 also invokes the combined post-readback gate after
empty managed-state and ECS readback checks; incomplete Terraform outcomes remain
UNKNOWN with intent and owner held. The current concrete path cannot reach apply.
The local E15 `down-execute` denial remains intact. Fixture-only abstract E15-C
channels remain isolated algorithm tests, never installed executor wiring.

## Remaining architecture and installation decisions

A correct provider-free protocol, protected runtime composition, authenticated
installed adapter, observed remote quietness and settlement of all issued effects
are five separate guarantees. This increment completes only the bounded repository
composition. E2 cannot fence an already checked/dispatched AWS call. E2-R interrupted
owners and E4 UNCERTAIN keep ACTIVE; no takeover, force unlock, compensation or
blind redispatch is added. EventBridge delivery, Lambda retry/callable old versions,
independent SDC/EIP/route duties and ASG service activity remain NAT blockers. Empty
queues/capacity/effect lists, quiet snapshots and elapsed time prove no finality.

Before enabling whole DOWN, the owner must approve a bounded authenticated contract
for exhaustive issuer coverage and credible settlement of every possibly issued
ECS/NAT/provider effect; continuous inhibition through ordered teardown; one E2
operation across exact per-layer approvals; and terminal ECS cluster handoff.
Those mechanisms are not selected or implemented speculatively. If they cannot be
established, keep complete DOWN denied. No code here grants AWS authority.

Proposed future permissions, separately requiring security approval:

- ECS DescribeTasks on generated tasks in the exact DEV cluster with supported
  cluster/region constraints; protected own-operation GetObject/GetObjectVersion
  and conditional PutObject with E15-D installation/storage protection. Existing
  scoped UpdateService does not approve the new drain operation by itself.
- DEV NAT handlers: exact application E2 head GetObject only, no head writes or
  PROD access, with all three duties and all callable versions installed coherently.
- Separately authenticated administrator inhibition/readbacks: exact DEV launch
  rule DisableRule/DescribeRule/ListTargetsByRule; exact three DEV functions'
  concurrency/configuration/version/event-invoke reads and approved inhibition;
  exact two ASGs' approved process/capacity changes and activity reads; exact network
  diagnostics and E13 queue attributes. The E15-F table is the detailed proposed
  action/scope register. These changes do not themselves establish finality.

No IAM, trust, PassRole, role/policy installation or activation is changed. External
identities 0/11, WP4D 0/16 and WP5 0/8 remain inactive. DEV/PROD/shared isolation,
retained backends/state/evidence/approved infrastructure and digest delivery remain.
SQL belonging exclusively to DEV remains disposable only after separate exact
infrastructure-destruction and permanent-SQL-loss confirmations; E15-B/C checks
are preserved. No PROD/shared data disposal or SQL durability selection is added.

## Inventory, packages and validation

Filesystem verification found six feature Python sources: ECS adapter/run/test
and NAT adapter/run/test. All six plus the combined adapter/run/test are explicitly
registered in source inventory. WP5 SOURCES adds the adapters and the exact NAT
import closure; bootstrap checks compare their bytes too. Eight deterministic
binding package identities and derived security-root references are regenerated
using the existing generators; no integrity check or policy is relaxed. TARGET
resource definitions and installation maps are preserved. Acceptance registers the
49-test ECS and 51-test NAT suites plus focused combined tests separately from the
unchanged 983 E1/WP count and AC1–AC16 requirements.

Run locally with preinstalled tools:
`python -I -B scripts/tests/combined_quiescence/run.py`, both feature run.py files,
and the original `scripts/tests/final_acceptance/gate.py --report-dir <outside-repo>`.
The original gate requires all accepted suites/static checks, inventory, generation,
packages, IAM/trust/PassRole, parsing, KDD links, formatting and whitespace. Missing
or failed evidence blocks main readiness. Tests use synthetic internal ports and
faults, never AWS clients, provider initialization or timing sleeps. Results and
static finding identity/multiplicity comparisons are recorded after execution.

Live validation remains separately authorized future work: real administrative
identity/storage/IAM and installed package/source readback, genuine current ECS
cohorts/controllers/task termination and terminal cluster absence, complete NAT
executor/service/effect finality, fresh independent AWS/provider/state readbacks,
S3 conditional durability, partial teardown reconciliation and residual absence.
No passing local fixture or historical result is live evidence.

## Validation repair record

The first combined original gate ran to completion: all 959 accepted regressions
and 24 WP7 tests passed, but overall acceptance and AC1-AC16 failed because three
additional checks failed. Its outside-repository report is retained under
`e15ef-combined-acceptance-20261012`; it is not successful acceptance evidence.

- ECS 49 exposed an incomplete synthetic Handoff that now reaches runtime wiring.
  The production boundary now rejects a missing engine/current owner with the
  controlled WP5 ValueError rather than leaking AttributeError. The original
  negative test and its no-subprocess assertion remain unchanged.
- NAT 51 still asserted that WP5 source had no quiescence wiring. Integration
  explicitly requires that wiring. This assertion now exercises the actual
  protected runtime and requires denial without concrete handoff; dormant WP4
  non-installation, IAM/activation and local DOWN denial checks remain intact.
- E15 30 contained two positives assuming empty Terraform state alone completed
  teardown readback. Both now require the new protected-quiescence denial. Pure
  empty-state shape, partial-state rejection, unchanged reconcile semantics and
  existing owner/retry tests are preserved. No guard is mocked into success.

After these changes, focused ECS 49, NAT 51, E15 30 and combined 39 tests passed
with no failures/errors/skips; source inventory/package identities and generator
checks were refreshed. The next full run, `e15ef-combined-final-acceptance-20261012`, was interrupted
before report publication and is not completion evidence. A hidden local process
then completed the original gate in `e15ef-combined-completed-acceptance-20261012`.
Its result below determines acceptance.


## Final local acceptance and bounded self-review

The original gate completed on the combined source tree with
`E1_REPOSITORY_ACCEPTANCE_PASS`. E1/WP: **959 regressions + 24 WP7 = 983**;
**AC1-AC16 all PASS**, all 18 registered suites and 21 sequential checks PASS,
source-admission errors empty. Parsing: 176 Python, 50 JSON, 22 generated YAML.
The outside-repository acceptance report is:
`C:/Users/PC/AppData/Local/Temp/e15ef-combined-completed-acceptance-20261012/acceptance.json`.
Its evaluated content digest, before this documentation-only results append, is
`e92fb24606059b382d35be865ada881110701b14961b8be63548ad0bcb8a817b`. No runtime/test/package/IAM source changes follow the successful gate.

| Regression evidence | Executed | Result |
| --- | ---: | --- |
| E2 | 41 | PASS |
| E2-R | 23 | PASS |
| E4 | 28 | PASS |
| E7 | 8 | PASS, independent local runner |
| E8 | 18 | PASS |
| E11 | 33 | PASS, independent local runner |
| E13 | 40 | PASS |
| E14-B | 19 | PASS, independent local runner |
| E15 | 30 | PASS |
| E15-B | 42 | PASS |
| E15-C | 46 | PASS |
| E15-D | 50 | PASS |
| E15-E | 49 | PASS |
| E15-F | 51 | PASS |
| E15-E/F integration | 39 new | PASS |

All eight extracted WP5 packages independently imported the fixed runtime, ECS
and combined/NAT adapters from their extracted files under hermetic protection.
Generator/TARGET/security-root references, IAM/trust/PassRole invariants and
source registration passed. Identity/compute activation remains 0/11, 0/16, 0/8.

Local Ubuntu checks with preinstalled tools passed actionlint, ShellCheck,
27 YAML/33 bash syntax checks and 5 process-supervision tests. Terraform fmt and
Terragrunt HCL format passed locally without provider initialization. TFLint
returned its inherited warning status: **24 warnings**. tfsec returned its
inherited findings status: **46 findings**. Against the original E15-D logs,
rule/severity/path/line-range/message-or-resource identity and multiplicity match
exactly: no added or removed finding. All 174 generated IaC files retain the
baseline normalized content; only eight WP5 package hashes in authority.json
change, with all other authority fields identical. No suppressions or policy
exceptions were added. Comparison evidence is retained outside the repository at
`C:/Users/PC/AppData/Local/Temp/e15ef-local-static/comparison.json` and
`source-comparison.json`; auxiliary suites and package import results are under
`e15ef-extra-checks` and `e15ef-package-import` in the same temporary directory.

One bounded self-review after validation inspected runtime dispatch/verification,
E15-C ordering before claim/attempt, concrete E15-D construction, the separate
adapter evidence and original owner correlation, repeat/UNKNOWN behavior,
package byte integrity, admission changes, stage/handoff blockers and the final
tests/docs diff. No material unresolved repository regression was found, and no
further code change was required. Documentation results/links/whitespace are
checked after this append. Existing native E3/.NET/live-provider limitations are
unchanged and are not represented as new live validation.

No AWS operation, provider initialization, remote state access, installation,
deployment, live plan/apply/destroy, Git fetch/push or PR occurred. Administrative
identity/protected artifact access and exact-plan approval still require authentic
installation; neither valid approval nor local adapter fixtures establish ECS/NAT
quietness or already-dispatched-effect settlement. Whole-stage owner continuity,
ordered per-layer approval handoff and terminal ECS cluster handoff remain explicit
architecture decisions. Fresh authorized AWS readbacks and real failure/partial
teardown reconciliation remain future work. Complete DEV DOWN is denied.

Delivery classification: **E15EF_PARTIAL_READY_FOR_MAIN_FAST_FORWARD** refers only
to locally accepted repository integration. Main is not modified. The final
integration revision and clean Git/ancestry verification are reported by the
integration task after its commit; no automatic main merge is performed.

## Changed paths against the E15-D baseline

The feature merges preserve their six Python sources and protocol KDDs. The
following complete path list also includes integration wiring, inventory/package
references, focused tests and authoritative KDD/runbook links:

- `ci/authority/source-inventory.json`
- `scripts/lifecycle/ecs_quiescence.py`
- `scripts/lifecycle/handoff.py`
- `scripts/lifecycle/packages.py`
- `scripts/lifecycle/quiescence.py`
- `scripts/lifecycle/runtime.py`
- `scripts/nat/quiescence.py`
- `scripts/tests/combined_quiescence/run.py`
- `scripts/tests/combined_quiescence/test_combined.py`
- `scripts/tests/ecs_quiescence/run.py`
- `scripts/tests/ecs_quiescence/test_ecs_quiescence.py`
- `scripts/tests/ephemeral/test_ephemeral.py`
- `scripts/tests/final_acceptance/check_knowledge.py`
- `scripts/tests/final_acceptance/gate.py`
- `scripts/tests/nat_quiescence/run.py`
- `scripts/tests/nat_quiescence/test_quiescence.py`
- `scripts/tests/security_root/wp5.py`
- `terraform/docs/architecture.md`
- `terraform/docs/bootstrap.md`
- `terraform/docs/decisions-and-limitations.md`
- `terraform/docs/deployment.md`
- `terraform/docs/e1-protected-environment-lifecycle.md`
- `terraform/docs/e15-ephemeral-lifecycle.md`
- `terraform/docs/e15d-administrative-handoff.md`
- `terraform/docs/e15e-ecs-quiescence.md`
- `terraform/docs/e15ef-combined-quiescence.md`
- `terraform/docs/e15f-nat-quiescence.md`
- `terraform/docs/secrets-strategy.md`
- `terraform/docs/validation.md`
- `terraform/infra/security/authority.json`

## E15-G operational component follow-up

[E15-G](e15g-operational-teardown.md) adds original-E2-owner composition, bounded
ECS drain, sealed terminal cohort handoff and residual completion checks.
Complete installed DOWN remains PARTIALLY_READY and denied: NAT executor/effect
closure, authentic ECS closure, whole-operation preparation and exhaustive
residual installation remain required. No IAM/activation or live AWS evidence.
