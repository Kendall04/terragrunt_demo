# E15-F — DEV NAT quiescence and dispatched-effect settlement

CURRENT repository candidate at baseline `ace06da4434b873b9fc1602f2befb4fa7d45cf44`,
2026-10-12, branch `codex/e15f-nat-quiescence`. No AWS operations, provider init,
installation, cleanup, remote Git or other-worktree modifications are authorized.
**PARTIALLY_READY. Networking teardown remains BLOCKED.** No live resources existed
at owner reconciliation; protected activation maps remain empty.

The independent [adapter](../../scripts/nat/quiescence.py) and
[adversarial tests](../../scripts/tests/nat_quiescence/test_quiescence.py) implement
bounded admission fencing and durable UNKNOWN diagnostics. They do not install a
controller, inhibit AWS services, settle remote calls or enable DOWN/EXECUTE.
[Architecture](architecture.md), [E13](e13-nat-reliability.md),
[E2](e2-environment-mutation.md), [E2-R](e2r-owner-recovery.md),
[E4](e4-post-switch-recovery.md), [WP5](e1-protected-environment-lifecycle.md),
[E15](e15-ephemeral-lifecycle.md), [E15-B](e15b-dev-down.md),
[E15-C](e15c-exact-destroy-approval.md) and
[E15-D](e15d-administrative-handoff.md) retain their authority and blockers.

## Recovered ownership and mutation inventory

Active authority is the neutral security root and fixed TARGET modules, generated
by `scripts/tests/security_root/wp4d.py`, `wp5.py` and `wp5_iam.py`. The old
`terraform/infra/global/modules/nat/lambda/*.py` source still exists, but it is not
in active TARGET resources or installed WP4D package sources; it is not an
additional current controller. Retired WP7 text is provenance only.

DEV global owns its VPC, two public/two private subnets, IGW/public default route,
route tables/associations, two EIPs and two conditional NAT ASGs. Each ASG has
min/max/desired 1, a single public subnet, and exact administrator-published
launch-template ID/numeric version. Instances are t3.micro; service-created ENIs
and root disks belong to those DEV members. Private `0.0.0.0/0` routes are
Lambda-managed, not Terraform default-route declarations. There is no cross-AZ
failover coordinator. Three independent handlers execute for each launch.

Security owns separate DEV/PROD launch templates, NAT roles/profiles, three
handler roles/functions per environment, event rules/targets/permissions, failure
queues and protected journals. The security root is neutral shared authority;
that does not make its PROD or retained resources DEV teardown targets. DEV
`shared` is its alerts layer and is retained with `secrets`, security, ECR,
evidence/backends and state. PROD has separate global networks/ASGs/EIPs/handlers/
rules/queues. Overlapping CIDRs are not resource membership. Broader production
operational independence remains an owner target, not a new guarantee here.

| Actual source / trusted actor | Existing permission and exact scope | New effects, outstanding effects, retries | Current fence and required shutdown/readback |
| --- | --- | --- | --- |
| ASG service, two DEV global groups | Auto Scaling service-linked authority; WP5 has bounded Create/Update/DeleteAutoScalingGroup and metric/tag reconciliation on installed DEV groups | Launch/replace/terminate members independently; activity/termination can outlive a request | No E2 check in AWS service. Protected inhibition and complete group/activity/member/EC2/ENI readbacks needed; desired zero alone is insufficient |
| DEV `assign_eip` installed Lambda role | ec2:AssociateAddress on exact protected EIPs plus ENIs constrained to each protected subnet | AllowReassociation=True; SDK call can complete late; async native retries can invoke again | Exact fresh Resolver membership and immutable attempt/ACK/readback journal; currently no E2. All callable versions need a boundary fence; retain ambiguous attempts |
| DEV `change_rt` installed Lambda role | ec2:CreateRoute/ReplaceRoute on the two exact protected route tables | Default route can change late or succeed without durable ACK | Same journal/membership, no current E2; exact table/VPC/default next hop/state readback, never infer completion from ACK |
| DEV `disable_sdc` installed Lambda role | ec2:ModifyInstanceAttribute with sourceDestCheck and own Environment/Role tags; tagged GetConsoleOutput | Attribute call can complete late; independent action order | Same journal/membership, no current E2; exact instance/ENI/launch and SDC readback, E13 bootstrap evidence retained |
| EventBridge default-bus DEV launch rule | Exact account/region, aws.autoscaling launch-success type and two protected ASGs; invoke permissions bind exact rule/account and published numeric versions | Separate target deliveries, delayed/duplicate/out-of-order events, up to 3 retries/900s age; already-dispatched delivery survives rule change | No event E2 enrollment. Disable/read exact rule and enumerate exact targets; disabling cannot recall deliveries |
| Lambda async execution (three independent functions) | Service invocation + action-specific execution IAM; reserved concurrency 1 per function; 600s timeout | Function-error retry 1, async age 900s; service/throttle retry; checked or dispatched EC2 call can survive inhibition | Read exact versions/configuration/concurrency; concurrency zero is admission inhibition, not termination/queue-drain/effect proof |
| E13 delivery and execution SQS failure destinations | Rule SourceArn/SourceAccount SendMessage; each handler SendMessage to DEV execution queue; admin-only read/drain, TLS, prevent_destroy | Messages are retained evidence for 14 days; no consumer, event-source mapping, redrive or automatic replay exists | Keep both queues/alarms. Visible/invisible/delayed approximate counts are diagnostic; zero is not proof of no pending Lambda/EventBridge work. Pending evidence blocks/needs diagnosis; never purge to pass |
| Instance fixed bootstrap | NAT workload profile has no represented networking mutation grant; fixed user_data.sh changes guest sysctl/iptables/service, uses IMDSv2 locally | Bootstrap/install can run during launch; guest forwarding persists until termination | No AWS E2 boundary; does not reassign EIP or routes. E13 marker is launch-time configuration, not present forwarding or instance termination proof |
| Protected WP5 Terraform global executor | Exact installed DEV network resource IAM, native state lock, current E2 application owner, closed plan/execution-binding checks | Creates/updates/deletes ASGs, EIPs, tables/public routes/associations/network; provider requests may remain outstanding | Preserve exact saved plan, E15-C single-use approval/E15-D handoff and E2; no Terraform bypass or arbitrary target. Must gate before networking apply and through completion |
| Separate human security administrator, exceptional E13 replacement procedure | Existing separately authenticated external admin; exact old/candidate template/AMI/member approval port, no ordinary handler refresh/terminate/PassRole authority | Can publish launch versions, pause delivery, perform approved ASG replacement; no live replacement adapter exists | Must participate in the quiet hold; retain approved operation identities and readbacks. Not automatic recovery or authority for a force unlock |

No ASG lifecycle hook, scaling policy, automatic instance refresh configuration,
termination-success handler, SQS consumer/redrive automation, SSM/SSH repair or
continuous NAT-health replacement controller is configured. ASG health-driven
replacement is distinct from the three launch callbacks. SNS/CloudWatch alerting
does not mutate NAT; it remains enabled. The known E13/shared SNS topic mismatch
is neither remedied nor accepted as notification proof by E15-F.

## Implemented fence and WP5 seam

`FencedEC2(client, store, config, action, context)` is a dormant wrapper for the
EC2 client passed to the actual `scripts/wp4d/aws_runtime.Nat` transport.
`context` must be the existing `scripts/recovery/nat.Nat.context`, backed by the
protected Resolver. It validates exact current ASG/EC2/launch membership; events
cannot nominate members. The wrapper admits only that duty's exact SDK verbs and
request, plus fixed read APIs. It rejects generic EC2 administration.

Admission captures a RELEASED canonical E2 application head at the exact
`e1-wp4-dev-<account>-<region>/arbitration/dev/application.json` through existing
Store validation. Each mutation reads that head before membership validation and
again immediately before the EC2 call. Any ACTIVE owner, changed generation/head,
wrong environment/binding/member/request, unavailable read or missing permission
rejects. This is conservative read fencing, not E2 ownership for NAT: independent
duties remain concurrent outside teardown, and this adapter does not serialize
NAT controllers. A new invocation during ACTIVE cannot even capture admission.
No check exists at AWS itself. Unwrapped/old versions remain uncovered.

`Quiescence(authority, request, protected, nat_config, records, observation)` is
the later WP5 integration seam, only for DEV high-risk **global teardown**. It
reuses E15-B exact scope/backend/revision/request/operation identity, requires the
original ACTIVE E2 Authority and exact owner/generation, and cross-checks both
protected NAT slots' VPC/subnet/ASG/EIP/table IDs with WP5 installed membership.
Configuration must originate from authenticated protected installation, not
caller JSON. `records` is existing WP5 Records at the exact lifecycle bucket and
`operations/environment-lifecycle/infra-high-risk-dev/` prefix.

`request()` immutably records UNKNOWN under `<operation>/nat-quiescence/intent.json`
and requires exact durable readback before observing. Repetition is identical
only for the same request, owner, generation, slot digest and protected NAT
configuration digest. No quiet Boolean,
release, timeout takeover or force unlock exists. `inspect()` appends immutable
content-addressed UNKNOWN observations, retaining unresolved effects/queue backlog
and readback failure. Its port is read-only, abstract and uninstalled. No SDK
clients or remote operations are created by this module.

`require_network_teardown()` is the explicit future pre-apply gate: it persists
those diagnostics and unconditionally rejects with
`E15F_NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_REQUIRED`. No supplied observation,
including a synthetic all-quiet snapshot, can replace this denial. No current
WP5/runtime/controller/gate/package integration is changed. ECS quietness remains
independent. Combined integration must retain the E2 owner through the entire
relevant global network operation, recheck at actual execution/readback boundaries,
and invalidate quietness when identity, configuration, owner, generation,
controller versions, resource membership or observations change. Per-layer E2
release is not an invented multi-layer hold.

## Readback and settlement limits

The closed diagnostic requires exact account/region/environment, fresh observation
time bounded by the read call and a 30-second acceptance budget, exact rule, all three numeric qualified functions,
both retained queues and both protected ASG/network slots. It records ASG
min/max/desired, Launch suspension, every remaining member with instance/ENI/state/
SDC, activity identity/status, EIP association and default-route next hop/state.
The Observer receives a fixed deadline and must use bounded read APIs; a late
return is rejected, not evidence of cancellation. It must independently verify
those exact IDs, tags, profile/launch
membership and complete pagination; it must not project an empty collection from
an unavailable call. Raw SDK errors/console output, arbitrary API dictionaries and
secret values are excluded. An uninstalled port is not live evidence.

A conservative drained snapshot has no ASG members/activities, min/desired zero,
Launch suspended, no EIP association and no private default route. This describes
potential observations, not a command to delete routes, detach EIPs, suspend
Terminate or scale groups. During draining, any owned or foreign next hop/
association, blackhole, remaining/terminating member or activity remains blocked.
The port must preserve E13 operation journal references and distinguish missing
ACK/attempt/outcome evidence. APPLIED/ABSENT listed effects do not prove an
exhaustive effect inventory or absence of delayed requests. No snapshot proves
absence of service-queued work; approximate SQS counts and matching routes do
not confer finality. No fixed wait duration is used as proof.

The existing journal proves a narrow APPLIED action only with retained exact
attempt/ACK plus independent operation-attributed resource readback. A durable
attempt without ACK is UNKNOWN; response loss, partial success or failed journal
persistence cannot be blindly retried. Durable terminal SUCCESS is historical
narrow-action evidence, not global executor settlement. ABSENT must meet the
existing authoritative no-resend contract; missing ACK is not ABSENT.

Two deterministic counterexamples use the actual transport/journal and EC2-shaped
boundary: a call passes its last fence read, pauses, DOWN acquires E2, and the old
call sends later; or the call has already dispatched and completes after DOWN.
NAT may retain a narrow SUCCESS after completion while networking teardown still
remains UNKNOWN. E2 head CAS/ownership change cannot revoke that downstream call.
Even observed SDK return/readback is not a guarantee against other queued events,
other duties, an old callable version, ASG activity or exceptional admin work.
The current architecture supplies no exhaustive authenticated executor mapping,
verified neutralization or service-issued-effect finality. Empty effect lists,
Lambda timeouts, concurrency zero, rule disable and waiting out configured retry
ages cannot fill that gap. E2-R interruption and E4 UNCERTAIN retain ACTIVE; a
second teardown cannot acquire, and this adapter never releases or transfers it.

## Protected installation / owner decision prerequisite

No IAM/trust/PassRole/resource/activation change is made. CURRENT NAT policy
lacks E2 read authority; attaching the wrapper under that policy fails closed.
A future reviewed install would need exactly s3:GetObject on the DEV application
head for the three DEV NAT execution principals, with no head write, no PROD
access, no ListBucket/Takeover/PassRole. Update all callable DEV versions and
protected digest-pinned packages/images/configuration coherently; retire old
executable authority only with proven executor and issued-effect settlement.
Source inventories/package admission must be reconciled after combined integration.

Potential inhibition requires a separately approved protected administrator
procedure, not ordinary WP5/handler privilege expansion:

| Candidate action | Exact DEV scope / trusted principal | Mandatory post-action evidence and limitation |
| --- | --- | --- |
| events:DisableRule; DescribeRule/ListTargetsByRule | Existing authenticated security administrator; exact DEV launch rule ARN | Disabled exact rule + all three targets; no recall of prior deliveries |
| lambda:PutFunctionConcurrency; GetFunctionConcurrency/GetFunctionConfiguration/GetFunctionEventInvokeConfig/ListVersionsByFunction | Same protected admin; exact three DEV function ARNs, numeric version inventory | Zero admission and exact executable/destination configuration; not a running invocation termination or async queue enumeration API |
| autoscaling:SuspendProcesses; UpdateAutoScalingGroup; DescribeAutoScalingGroups/DescribeScalingActivities | Same protected admin; two installed DEV ASG ARNs and DEV tag/region, approved operation under original E2 owner | Exact selected processes/capacity and full activity/membership/termination readback; min=0/desired=0 must be explicitly approved and reconciled with WP5 saved-plan/state. Do not suspend Terminate blindly |
| ec2 existing Describe APIs; sqs:GetQueueAttributes | Same protected diagnostic admin; exact installed resources/queues (Describe actions may require region-limited wildcard) | Current EC2/ENI/EIP/table/SDC and all approximate queue counters; neither establishes request finality |

These are proposed bounds, not installed grants or a chosen complete shutdown
recipe. Launch inhibition is a relevant diagnostic, but the process set and
controlled drain must be decided against real ASG activity; no experiment or
policy activation occurs here. Reuse existing admin queue-read/archive authority;
no Receive/Delete/Purge grant to WP5/NAT, no alert suppression, no generic EC2
termination or new protected generic control plane is introduced.

The owner must select a credible bounded mechanism that establishes BOTH no
remaining authorized issuer (including old callable code, checked-but-unsent
calls, admin actions and ASG service work) AND settlement of every issued or
possibly issued remote effect. It must independently authenticate real execution
identities, preserve attempts and UNKNOWNs, provide an exhaustive reconciliation
basis and maintain inhibition throughout networking destruction. Without such a
mechanism the correct result remains BLOCKED. E15-F does not choose credential
revocation, a mutation broker or executor infrastructure as a presumed solution.

Live AWS evidence still needed under a separate future authorization: real
IAM/resource/queue-policy enforcement, all installed numeric versions and cold/
warm behavior, concurrent async retries/duplicate/delayed delivery, in-flight
EC2 outcomes and response loss, ASG launch/termination/service activity, complete
network membership/readback, protected S3 CAS/journal durability and genuine SNS
notification delivery. No source fixture is live proof. AWS retry semantics cited
in E13 are configuration constraints, not experimentally verified guarantees here.

## Local validation and bounded self-acceptance

Initial checkout/root/branch/HEAD were exact and clean; a temporary local write
probe verified access. Final focused command
`python -I -B scripts/tests/nat_quiescence/run.py` passed **51 tests**, no failures,
errors or skips. These exercise actual protected Nat transport/controller/journal,
E2 Store/Authority, exact WP5 Records and deterministic thread barriers, including
two independent duties dispatching before the hold and completing afterward.
The final test run includes configuration drift and observation-budget invalidation.

Fresh existing suite commands and results:

| Command | Actual outcome |
| --- | --- |
| `python -I -B scripts/tests/nat/run.py` | E13 40 passed |
| `python -I -B scripts/tests/mutation/run.py` (inside attempted gate) | E2 41 passed |
| `python -I -B scripts/tests/owner_recovery/run.py` (inside attempted gate) | E2-R 23 passed |
| `python -I -B scripts/tests/post_switch/run.py` (inside attempted gate) | E4 28 passed |
| `python -I -B scripts/tests/ephemeral/run.py` | E15 30 passed |
| `python -I -B scripts/tests/dev_down/run.py` | E15-B 42 passed |
| `python -I -B scripts/tests/exact_destroy/run.py` | E15-C 46 passed |
| `python -I -B scripts/tests/handoff/run.py` | E15-D 50 passed |
| `python -I -B scripts/tests/retention/run.py` | E8 18 passed |
| `python -I -B -m unittest discover -s .github/scripts/ci/tests -v` | E11 33 passed |
| `python -I -B -m unittest discover -s scripts/tests/reproducibility -v` | E14-B 19 passed |
| `python -I -B scripts/tests/monitoring/run.py` | E7 8 passed |

The full command `python -I -B scripts/tests/final_acceptance/gate.py --report-dir
C:\Users\PC\AppData\Local\Temp\e15f-nat-acceptance-20261012` was attempted once.
It was interrupted before completion and produced no `acceptance.json`: **no
983-test or AC1–AC16 PASS is claimed**. Completed E1/WP test runs: security_root
18, control_bundles 22, build_supervision 150, qualification 110, internal_release
33, normal_delivery 20, delivery 98, recovery 53, WP4D 33, lifecycle 49, workflows
61 and final_acceptance 24 all reported unittest OK with no failures/errors/skips.
Four source-admission runners (security_root, control_bundles, build_supervision,
qualification) returned FAIL solely for the three intentionally unregistered new
Python files. Authority, controller_compute and ownership_publication logs are
incomplete; they are not passed evidence. E2/R/E4 completed independently inside
that attempt. No rerun of the complete gate or inventory repair was used to hide
these limitations. An initial guessed `scripts/tests/toolchain/run.py` invocation
failed because that path does not exist; the correct reproducibility command above
subsequently passed all 19 tests.

Remaining focused/static commands were executed independently after interruption,
all exit zero: `python -I -B` with `scripts/tests/ephemeral/check_plan_shape.py`,
`scripts/tests/nat/check_static.py`, `scripts/tests/mutation/check_static.py`,
`scripts/tests/wp4d/check_static.py`, `scripts/tests/lifecycle/check_static.py`,
`scripts/tests/workflows/check_static.py`, `scripts/tests/security_root/render.py`,
`scripts/workflow_requests/render.py`,
`scripts/tests/internal_release/check_packages.py` and
`scripts/tests/final_acceptance/check_knowledge.py`.
These preserve actual generated NAT delivery protections, IAM/trust/PassRole,
DEV/PROD scope, inactive installation and package/generator parity. Static
Terraform evaluation uses disposable provider-free locals/variables, no init.
`terraform fmt -check -recursive terraform/` and `git diff --check` passed.

Final source parsing passed 170 Python, 50 JSON and 22 generated JSON-subset YAML
files; all new KDD local links and immutable approved E1 contracts passed. Actual
source inventory reports exactly three UNMODELED_SOURCE entries:
`scripts/nat/quiescence.py`, `scripts/tests/nat_quiescence/run.py` and
`scripts/tests/nat_quiescence/test_quiescence.py`. It remains unchanged for combined
integration. No source-package hashes or generated authority are modified.

One bounded self-acceptance confirmed exact DEV/global/E2 binding, immutable
UNKNOWN before observation, original hold/no takeover, diagnostic-only readbacks,
no representable quiet SUCCESS, no retry/cleanup/IAM expansion, no AWS clients,
no current runtime wiring, and preserved E13/journal behavior. All Terraform/IAM,
trust/PassRole/generated authority and existing runtime bytes match baseline after
line-ending normalization. TFLint/tfsec were not rerun: there is no Terraform
change, and no fresh lint-count claim replaces the inherited 24/46 findings. No
shared Linux VM, global toolchain, dependency installation or other worktree was
used. Reports are local temporary files outside the repository.

Changed files are the standalone adapter, its runner/tests, this contract, plus
small links/status additions in `e15-ephemeral-lifecycle.md`, `validation.md` and
`decisions-and-limitations.md`. No shared executable integration files changed.
The safe repository parts are READY_IN_REPOSITORY; the full NAT shutdown is
PARTIALLY_READY, REQUIRES_OWNER_DECISION and REQUIRES_LIVE_AWS_VALIDATION.

## Combined integration follow-up

[The E15-E/F contract](e15ef-combined-quiescence.md) supersedes the standalone
unwired/package-admission disposition. Protected runtime composition is now
registered; installed closure, whole-operation stage handoff and remote effect
settlement remain denied. Standalone validation results above retain their dates
and are not combined acceptance evidence.
