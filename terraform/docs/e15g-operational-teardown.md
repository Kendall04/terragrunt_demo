# E15-G operational DEV teardown components

CURRENT CONTRACT, 2026-10-12. Initial main/HEAD
`f1bfa6e738c77d597e8c3f29316d447e2d2c820b`; existing
`C:/proyectos/terragrunt_demo-wt-batch1`, branch `codex/e15g-operational-teardown`.
**PARTIALLY_READY. Complete installed DOWN remains denied and is not structurally
executable end to end.** No AWS operation, provider initialization, remote state,
installation, activation or Git remote operation occurs in this increment.

## Concrete gaps and implemented protocol

The [combined baseline](e15ef-combined-quiescence.md) releases E2 per layer, lacks
a terminal ECS cohort handoff, and has no installed NAT settlement adapter.
E15-C/D approvals remain exact and per request. These mechanisms are reused.

[Operation](../../scripts/lifecycle/operational.py) validates five independently
protected, distinct request UUIDs, one DEV account/region/revision/configuration,
exact `edge -> apps -> platform -> data -> global` order, and separate SQL-loss
consent before admission. One unmodified E2 Authority owns the first exact edge
request. An immutable whole-operation manifest binds every child request and
configuration digest to the original owner/generation. Only the current ordered
child may use this live invocation, after durable verification of preceding
stages. No child acquires/releases E2 or nominates an owner.

TARGET source ownership derives the boundaries: edge API/VPC Link uses global
networking; apps use global subnet/ALB inputs, SQL and platform cluster; platform
owns the cluster, data SQL, global NAT/ASGs/EIPs/VPC/ALB. No ordinary dev
Terragrunt wrapper remains. Shared, secrets and neutral security are retained.
Both domain guards must pass before destruction; NAT settlement must remain valid
through every stage. Capture ECS terminal evidence after apps and immediately
before platform deletion, then consume it at later stages.

[Internal runtime.execute_down](../../scripts/lifecycle/runtime.py) verifies
current admin-owned configuration, exact bootstrap package and fixed E15-D
adapters. It accepts no event-selected adapter/identity/executable or installation
Boolean. It is not connected to the handler, gateway or local down-execute.
The installed NAT factory and authentic ECS closure remain absent; an admitted
invocation persists UNKNOWN and holds its original owner before any Terraform
destruction. This is operational ownership/dispatch composition, not enabled DOWN.
Existing per-layer runtime and ordinary delivery remain unchanged.

## ECS drain and terminal handoff

[E15-E](../../scripts/lifecycle/ecs_quiescence.py) adds `drain_until_quiet`: one
durable attempt per exact service, then at most sixteen fresh samples. Only valid
nonterminal evidence permits another sample. Missing tasks, errors, corrupt
records, lost mutation response, owner drift or exhaustion stop. No sleeps,
mutation retries or successful update response establish quietness. Tasks must
actually be STOPPED; PENDING tasks are enumerated using desiredStatus RUNNING.

E2 inhibits new WP4 delivery/rollback/emergency/cleanup and conflicting WP5 writes;
generation-bound cleanup admission rejects late old schedules. Native ECS REPLICA
reconciliation at zero differs from these custom controllers. Actual installed
native/external scheduling and prior-effect closure still require E15-E's trusted
ProtectedBoundary. No autoscaling service or installation evidence is invented.

Immediately before platform deletion, `require_predelete_seal` refreshes quietness
and conditionally publishes immutable terminal-seal.json in the existing journal,
binding cohort/resources/source, original request, owner/generation, platform stage
and original 300-second intent expiry. Repeated pre-dispatch gates refresh the
same cohort without replacing the seal. After deletion, terminal handoff consumes
the exact retained STOPPED sample, fresh continuous closure and exact cluster
MISSING readback; it never redescribes former tasks from a deleted cluster.
Contradictory/missing readback publishes immutable terminal-invalid UNKNOWN.
A later quiet snapshot cannot erase it. The window is not executor termination
proof and cannot authorize interrupted-owner recovery.

## Approval, dispatch, repetition and uncertainty

E15-C preserves binary/JSON/version/state/configuration checks, authenticated admin,
separate destruction/SQL-loss confirmations, approval expiry and single-use
claim/attempt slots. It additionally checks the internal current child against
the original E2 owner and expected generation. No new plan, auto-approve, direct
Terraform or weaker consent exists. WP5 uses its existing saved-plan execution
and independent readback. Each verified stage is durable. Only final residual
verification and whole terminal publication permit E2 terminal-before-release.

Repeated whole UUIDs read the exact manifest; changed children/configuration
reject. An old per-layer SUCCESS cannot become whole SUCCESS. Used child UUIDs
cannot substitute prior layer results. Final verification without confirmed
original E2 terminal/released head does not acknowledge completed DOWN.

An additional installation gap is exposed: `Handoff.publish_prepared` requires a
distinct per-request preparation owner and sets expected generation to preparation
+ 1. Five independent preparations cannot all predict the same DOWN generation.
A reviewed same-owner preparation/publication route is required. This increment
preserves the rejection rather than changing E15-C/D provenance or manufacturing
compatible receipts. No complete installed plan-production route is claimed.

Crash before/during closure/inhibition, after AWS/provider dispatch, after claim,
between layers or after final destruction before ACK retains durable UNKNOWN and
ACTIVE original ownership. Lost AWS/Terraform response, partial readback,
expired/corrupt evidence and E4 UNCERTAIN never become SUCCESS. No blind resend,
timeout takeover, finally-release, diagnostic deletion or automatic recovery.

## NAT protected decision boundary

E15-F can correlate its exact global child with the current durable whole-operation
context, original E2 owner, installed slots and configuration. E13 attempts/ACKs /
readbacks and executor/issued-effect-settlement denial remain intact. Per-layer
construction is unchanged; all-version handler fencing remains dormant.

There is no exhaustive authenticated closure mechanism for old callable versions,
checked-but-unsent executors, dispatched calls, async retries and native ASG work.
Disabled EventBridge, zero concurrency/capacity, approximate empty queues, elapsed
time, changed E2 generations, snapshots and narrow E13 SUCCESS cannot establish it.
No ledger is added that pretends to solve that process boundary.

Smallest alternatives requiring explicit owner/security approval:

| Alternative | Changes / authority | Assessment |
| --- | --- | --- |
| Cooperative all-version fencing, pre-admission/dispatch evidence, authenticated executor closure and E13 reconciliation | Narrow DEV E2 reads on three handlers, install every callable version, correlate exact executor/attempt evidence, approved rule/ASG inhibition and independent issued-effect settlement | Recommended bounded direction for this lab; executor-closure mechanism remains unselected, a ledger alone is insufficient |
| Central protected dispatch broker | New approved runtime, narrower handler authority, installation/migration and provider-effect reconciliation | Larger security expansion, not selected |
| Administrative neutralization of all old authority | Approved executor/credential/service neutralization and exhaustive effect reconciliation | No existing termination/finality proof; never force-unlock E2 |

Safe ECS draining/sealing, whole-owner composition and residual validation are
implemented without selecting those authorities. Installed NAT stops at its
existing protected boundary; no IAM or compute is installed/activated.

## IAM and installation prerequisites

No IAM/trust/PassRole expansion occurs. Existing lifecycle authority is the
[WP5 action inventory](../../scripts/tests/security_root/wp5_iam.py). Every new
capability requires exact DEV operation and independently approved installation.

| API family | Trusted principal / resource scope | Required approval and live evidence |
| --- | --- | --- |
| Existing WP5 lifecycle, layer-state/lock and journal inventory | e1-controller-infra-high-risk-dev-exec; exact installed DEV IDs/backends and own operation prefix | WP5 security-root/package/membership installation and E15-C/D exact plans; no PROD/shared/security deletion |
| ecs:UpdateService, DescribeServices, DescribeClusters, ListTasks, DescribeTasks | Reviewed protected ECS principal; exact two DEV services, cluster and task ARN pattern, supported cluster/region conditions | Existing scoped WP4D stopping duty does not approve new drain/closure; missing DescribeTasks scope and approved runtime binding; genuine tasks STOPPED |
| events:DisableRule, DescribeRule, ListTargetsByRule | Existing separate security admin; exact e1-wp4-dev-nat-launch rule ARN | Explicit inhibition approval and all target/version readbacks; prior events unsettled |
| lambda:PutFunctionConcurrency, GetFunctionConcurrency, GetFunctionConfiguration, GetFunctionEventInvokeConfig, ListVersionsByFunction | Same admin; exact three e1-nat-recovery-nat-dev-{assign_eip,change_rt,sdc} functions/numeric versions | All-callable-version coverage and approved inhibition; zero concurrency is not invocation termination |
| autoscaling:SuspendProcesses, UpdateAutoScalingGroup, DescribeAutoScalingGroups, DescribeScalingActivities | Same admin; exact two installed DEV ASG ARNs, DEV tags/region where supported | Approve selected process/capacity transition, activity/member/termination reads and provider-state reconciliation; no blind Terminate suspension |
| s3:GetObject on arbitration/dev/application.json | Three exact DEV handler principals; exact e1-wp4-dev-account-region head | New narrow owner/security-approved read grant; no writes/ListBucket/PROD/takeover; install every version |
| Existing E2 CAS and WP5 journal GetObject/GetObjectVersion/conditional PutObject | Original executor; exact DEV application head and own operation/child namespaces | Genuine CAS/version/digest readback and E15-D encrypted private versioned no-delete storage; no new control plane |
| E15-D artifact/approval reads and conditional writes | Separate admin for approval, installed preparation/execution principals on fixed paths | Authentic STS RoleId sessions and existing storage requirements; same-owner preparation route still required |
| Residual EC2/EBS/ENI/EIP/routes, ECS/ASG/ELB/API Gateway/Logs Describe/List; sqs:GetQueueAttributes diagnostics | Independently approved observer; exact DEV IDs/parents, region-constrained wildcard only where Describe requires it; retained resources read-only | Exhaustive observer/action inventory uninstalled; derive exact extra API/resource tuples from its future SDK requests before approval; ownership/pagination/orphan/absence evidence |

Residual is an uninstalled boundary, not an approved broad policy. No generic
IAM/EC2/PassRole, queue purge/redrive, ECR cleanup, shared deletion or new resource.
Activation stays 0/11 external, 0/16 WP4D, 0/8 WP5.

## Residual and operator workflow

The residual gate requires every installed runtime address, NAT instances, SQL
root EBS, service ENIs, tasks, Lambda-owned routes and unexpected DEV resources,
plus retained backend/state/locking, security-root, shared/secrets, journals/evidence,
ECR/provenance and approved persistent resources. ABSENT/RETAINED require independent
evidence digests. PRESENT, UNKNOWN_OWNERSHIP, NOT_QUERIED, READBACK_FAILED and
PARTIAL block completion. Empty Terraform state is not this inventory. The
observer is uninstalled; E15 local notes cannot acknowledge DOWN. Retained
resources can continue billing; no guaranteed zero bill.

Continue E15 local status/preparation/residual review. No usable DOWN command
exists; public/local down-execute denies. Never substitute five direct destroys.
Offline commands:

```text
python -I -B scripts/ephemeral_lab.py --help
python -I -B scripts/tests/operational_teardown/run.py
python -I -B scripts/tests/final_acceptance/gate.py --report-dir <outside-repository-directory>
```

Intended procedure after separately authorized genuine installation: prepare five
exact saved plans through an approved whole-operation preparation route; authenticate
admin review and both DEV confirmations; admit one protected invocation; establish
both controller/effect closure domains; drain and verify tasks; advance five saved
plan stages with platform terminal handoff; verify residuals; acknowledge whole
completion and original E2 release. Activating current maps alone cannot enable it.

| Capability | Classification |
| --- | --- |
| Bounded real ECS SDK drain/readback, sealed cohort, original-owner composition and residual validation | READY_IN_REPOSITORY |
| Complete installed DEV DOWN / full normal five-stage success test | PARTIALLY_READY; not structurally executable end to end |
| NAT closure/settlement, reviewed controller/residual authority, same-owner preparation route | REQUIRES_OWNER_DECISION |
| Authentic sessions/S3/IAM, native ECS/ASG, late Lambda effects, real provider deletion/partial failure and residual absence | REQUIRES_LIVE_AWS_VALIDATION |

Offline tests exercise real ECS requests/responses and original owner/journal /
protected boundaries. Existing E15-C/D, E13 and E1 tests retain exact-plan,
ambiguous provider, in-flight NAT and normal deployment coverage. Complete positive
whole-DOWN validation remains unavailable until those prerequisites can be supplied
without fabricated authority/settlement. No fixture changes the installed denial.

## Bounded self-review repair

The first complete gate passed 983 E1/WP, AC1-AC16 and all 22 checks on the
pre-repair tree. Its report remains at
`C:/Users/PC/AppData/Local/Temp/e15g-final-acceptance-20261012/acceptance.json`;
it is not final-source acceptance. The bounded self-review found that a failed
invalid-marker publication could let the same standalone ECS protocol object
accept a later apparently valid read. Terminal failure is now latched for that
original invocation as well as recorded immutably when storage permits. Losing
the marker write cannot revive the seal or release E2. Two deterministic fault
tests cover both pre-delete and post-delete boundaries. Five additional tests
exercise real E15-C child-plan claim/attempt consumption under the original E2
owner, missing quietness, generation mismatch, replay and installed rejection of
an abstract synthetic channel. They do not claim positive whole-DOWN execution.
Final focused acceptance contains 54 tests; the complete final source gate is
rerun after this repair and package/inventory reconciliation.

## Final IAM clarification and failure boundaries

The current WP5 policy already includes scoped ecs:UpdateService on installed
service membership, DescribeServices/DescribeClusters and cluster-limited
ListTasks. It does not grant ecs:DescribeTasks to this new WP5 drain. WP4D has a
separate scoped DescribeTasks grant, which cannot be borrowed by the WP5 role.
The current WP5 own-operation policy includes GetObject and conditional PutObject;
its GetObjectVersion is scoped to the exact control package, not ECS journal /
E15-D artifact versions. The new ECS journal uses the E15-D Storage version-pinned
read path. These missing version-read/installation tuples require separately
approved scope on exact DEV operation artifact/journal objects; the existing
policy is not silently expanded. Approval/selection reads also remain subject to
E15-D's external protected installation requirements.

Runtime steps use the real production controller and saved-plan boundaries, but
there is no positive complete installed operation test. The present installation
cannot pass NAT closure, ECS installed closure, whole-plan generation and complete
residual readbacks. Those are essential missing capabilities, not mere live-test
uncertainty. The first real lab experiment must separately authorize and validate
their selected solution before DOWN can be enabled. A bounded sixteen-sample /
300-second ECS evidence window may expire during long provider operations; expiry
retains UNKNOWN and ownership, and is not a recovery permission.

## Changed source paths

- `ci/authority/source-inventory.json`
- `scripts/lifecycle/ecs_quiescence.py`
- `scripts/lifecycle/exact_destroy.py`
- `scripts/lifecycle/operational.py`
- `scripts/lifecycle/packages.py`
- `scripts/lifecycle/runtime.py`
- `scripts/nat/quiescence.py`
- `scripts/tests/final_acceptance/check_knowledge.py`
- `scripts/tests/final_acceptance/gate.py`
- `scripts/tests/operational_teardown/run.py`
- `scripts/tests/operational_teardown/test_operational.py`
- `scripts/tests/security_root/wp5.py`
- `terraform/docs/architecture.md`
- `terraform/docs/bootstrap.md`
- `terraform/docs/decisions-and-limitations.md`
- `terraform/docs/deployment.md`
- `terraform/docs/e1-protected-environment-lifecycle.md`
- `terraform/docs/e15-ephemeral-lifecycle.md`
- `terraform/docs/e15ef-combined-quiescence.md`
- `terraform/docs/e15g-operational-teardown.md`
- `terraform/docs/secrets-strategy.md`
- `terraform/docs/validation.md`
- `terraform/infra/security/authority.json`

## Final provider-free acceptance and delivery

The post-repair foreground gate was interrupted before report publication at
`C:/Users/PC/AppData/Local/Temp/e15g-completed-source-acceptance-20261012`.
It is not PASS evidence. The unchanged final executable source then completed the
entire original gate in a hidden persistent local process. Authoritative report:
`C:/Users/PC/AppData/Local/Temp/e15g-persistent-final-acceptance-20261012/acceptance.json`.
Result: **E1_REPOSITORY_ACCEPTANCE_PASS**, **959 regressions + 24 WP7 = 983**,
**AC1-AC16 all PASS**, 18 required suites and 22 sequential checks all PASS;
no admission errors, failures, errors or skips. Evaluated precommit content digest:
`eba7c1ca44400db277b01b05126d75f33910e23d8135c7699c0e4684ba0e08b0`.

| Executed suite | Tests | Result |
| --- | ---: | --- |
| E2 | 41 | PASS |
| E2-R | 23 | PASS |
| E4 | 28 | PASS |
| E7 | 8 | PASS, independent final runner |
| E8 | 18 | PASS |
| E11 | 33 | PASS, independent final runner |
| E13 | 40 | PASS |
| E14-B | 19 | PASS, independent final runner |
| E15 | 30 | PASS |
| E15-B | 42 | PASS |
| E15-C | 46 | PASS |
| E15-D | 50 | PASS |
| E15-E | 49 | PASS |
| E15-F | 51 | PASS |
| E15-E/F combined | 39 | PASS |
| E15-G | 54 | PASS |

Parsing passed **179 Python, 50 JSON and 22 generated JSON-subset YAML** sources.
All eight final WP5 packages independently imported runtime, ECS/NAT and the new
operation module from their extracted bytes under hermetic protection.
Inventory, package/source byte identity, security-root/workflow generation,
provider-free IAM/trust/PassRole and installation gates, approved E1 contract
hashes, KDD links, Terraform fmt and whitespace passed. Activation remains
0/11, 0/16, 0/8. Terraform/Terragrunt generation remains unchanged except the eight
WP5 package SHA-256 identities in authority.json; all other authority fields match
baseline. No policy/trust/PassRole or compute activation changed.

Fresh TFLint/tfsec comparison against accepted E15-E/F logs matched rule/severity/
path/line-range/message-or-resource identity AND multiplicity exactly:
**24 TFLint warnings, 46 tfsec findings**, no added/removed findings or suppressions.
Evidence: `C:/Users/PC/AppData/Local/Temp/e15g-static-comparison.json`.
Terraform/HCL/JSON source comparison checked 177 baseline files; only authority.json
changed, solely eight package digests. Terragrunt HCL check-only format and 33 Bash
syntax checks passed. ShellCheck/actionlint/native YAML parser were unavailable;
WSL returned E_ACCESSDENIED. No new native Linux E3, full YAML lint, application /
container or provider-backed schema/live result is claimed. No tool was installed.

The bounded self-review and its reproducible invalid-marker repair are recorded
above. All 54 focused tests pass after that repair; real E15-C child binary-plan
consumption, missing quietness and generation/replay failures are covered without
a fabricated positive full DOWN. Runtime/test/package/inventory hashes were
verified unchanged after the successful gate. This results append changes only
documentation and is checked separately for links/whitespace before commit.

Initial HEAD: `f1bfa6e738c77d597e8c3f29316d447e2d2c820b`. Delivery is one local
commit on `codex/e15g-operational-teardown`, with final revision reported after
commit and clean index/worktree verification. Main is not integrated, and no new
worktree, clone, remote operation or unrelated-project change is performed.
All operations are local/provider-free; **zero AWS operations**, including reads,
provider initialization, installation, deployment or teardown. Complete normal DEV
DOWN remains **PARTIALLY_READY**, not structurally executable end to end and not
proven in AWS. The independently safe components are ready for repository
integration while the exact controller/authority/preparation/residual boundaries
remain blocked as documented. Any first AWS teardown experiment requires separate
owner authorization and genuine installation/closure/readback validation.
