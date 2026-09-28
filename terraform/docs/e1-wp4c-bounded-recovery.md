# E1 WP4C — bounded recovery contracts

## CURRENT CONTRACT — provider-free, not integrated

WP4C supplies protected domain controllers and closed adapter contracts only.
There are no SDK clients, deployed endpoints, IAM grants, service trusts,
invocation permissions, new compute resources or request activation. Existing
AWS-facing scripts are unchanged and are **not** claimed to implement these
protected boundaries yet. WP4D owns packaging, authenticated wiring, exact IAM
and selective materialization. WP4 is not complete.

Implementation: [application](../../scripts/recovery/application.py),
[NAT](../../scripts/recovery/nat.py), [journal](../../scripts/recovery/journal.py),
[ports](../../scripts/recovery/ports.py).
These consume [WP4B evidence](e1-wp4b-normal-delivery.md) and current WP4A
authorization. The accepted [plan](../../specs/iam-hardening/plan.md) defines the
recovery responsibilities. The owner's current decision is unambiguous:
**CURRENT REVOKED eligibility forbids emergency recovery. No break-glass exists.**

## Request and trust boundary

Each installed controller accepts a UUID operation identity and exactly `{}` as
canonical request bytes. Environment, handler and resource selections come from
installed protected configuration. No caller may supply release, image, task
revision, roles, services, colors, listener, targets, network, readiness, health,
AWS request documents or authorization flags. Independent dev/prod namespaces
are `environment/recovery/kind/operation`; these are not public routing inputs.

The abstract ports document required authenticated sources. Implementing an ABC
is not authentication. WP4D must restrict writers/readers and bind configuration
to the installed endpoint, with one protected runner owning each operation.
Passing caller dictionaries as protected observations is forbidden. No AWS
transaction or compare-and-swap across reads and writes is claimed; the existing
final-read-to-mutation race remains.

## Emergency application recovery

The current single-target listener and candidate-rule mapping select the inactive
color. Protected configuration references a WP4B operation for each color. The
read-only history validator loads its actual successful receipt, immutable intent,
all seven authoritative mutation effects, exact activation hash selected by the
switch plan, registration, persisted E3 evidence and final activation state.
Missing, failed, uncertain, preparation-only, registration-only or E3-only history
does not establish recoverability. A caller cannot supply historical evidence.

Current WP4A authorization must authorize the same release/source/digest, task,
replica count, service/color, routing and qualification. The current binding must
match protected environment membership. Historical eligibility alone is never
sufficient. The exact previously activated revision must still be selected by the
observed service; its authoritative task readback must validate against WP4A.
There is no task registration or service task-definition update in this path.
An older revision no longer selected must use normal WP4B history rollback with
current authorization and E3, not emergency recovery.

The immutable operation retains the selected evidence and initial state. Each
mutation has an immutable plan and attempt marker. After persistence, fresh
authorization and exact topology/state guards precede the external call:

1. If desired capacity is zero, restore the historical bounded replica count
   using only cluster, service and desiredCount. Otherwise it must already equal
   that count; no unnecessary restart or registration occurs.
2. Observe the exact revision stable, desired=running=historical count, pending=0,
   and one healthy target per required running task. Targets bind service,
   revision, target group, operation and environment. Target IDs must be exact,
   nonblank, unpadded strings; duplicate, foreign, missing, stale or unhealthy
   evidence rejects. This provider-free check does not prove AWS task membership:
   the WP4D/live adapter must prove each target belongs to the exact running tasks
   and target group, and establish a completed unmixed ECS deployment rather than
   return a `stable` caller flag.
3. Freshly reauthorize and reobserve health/topology immediately before normal
   listener flip. Flip only to that protected candidate target.
4. Swap the exact candidate rule to the formerly active target, then schedule the
   existing environment cleanup function with fixed target ID `scale-down` and
   installed bounded delay. No caller-selected function/schedule is accepted.
5. Reobserve final mapping, exact healthy revision and current authorization;
   close the receipt with validated effects and a deliberate observation
   projection. No fresh E3 runs in emergency recovery.

Zero capacity and already-running dev/prod traces use actual WP4B-generated
offline success evidence. They do not claim any deployed AWS resource exists.

## Cleanup boundary

The controller protects the algorithm in
[scale_down_old_color.py](../infra/apps/fargate/lambda/scale_down_old_color.py).
It derives both services from current protected mapping and rejects ambiguous,
weighted, foreign or contradictory routing. Active desired and running capacity
must both remain positive, including the already-zero inactive path. Fresh guards
after plan/attempt persistence prevent stale topology from selecting active
service for scale-down.

Only inactive desiredCount can become zero. If already zero with no running
tasks, scaling is skipped. It then removes only `scale-down` from the installed
environment EventBridge cleanup rule and deletes that exact rule. Each step has
separate effect evidence. ECS may still be draining tasks; desired zero is the
existing algorithm's scale-down result, not a claim that every task has stopped.
It does not delete ALB listener rules or deregister arbitrary ALB targets: the
existing cleanup algorithm does neither. No generation scheduler is introduced.

## NAT protected membership and launch specification

The three existing handlers remain the responsibility vocabulary:
[assign_eip](../infra/global/modules/nat/lambda/assign_eip.py),
[change_rt](../infra/global/modules/nat/lambda/change_rt.py),
[disable_sdc](../infra/global/modules/nat/lambda/disable_sdc.py).
Protected approved membership binds environment, VPC, subnet, AZ, ASG, exact
instance, attached ENI, EIP allocation and route table. Independent ASG/EC2 reads
must agree, including InService/Healthy membership, ENI instance attachment,
route-table VPC and EIP environment ownership. Prefix, name, event ASG claims or
`Role=nat` alone cannot enroll an instance or authorize an action.

The approved launch specification pins the resolved AMI, launch-template ID and
numeric version, user-data SHA-256, instance profile/role, one security group,
instance type, metadata token policy, public-IP/delete-on-termination settings
and protected tags. Subnet/AZ/VPC are explicit membership fields. This derives
from the repository's [launch template](../infra/global/modules/nat/launch_template.tf):
`t3.micro`, required metadata tokens, public interface, one SG, and existing NAT
user data. The current Terraform `$Latest`/AMI resolution must be resolved and
pinned by protected publication before this controller accepts an operation.
WP4C invents no actual AMI or version and adds no launch-template mutation.
Fixture IDs and version 7 are synthetic, not deployment selections.

| Handler | Only admitted mutation |
| --- | --- |
| assign_eip | Associate the exact protected AllocationId with its exact attached ENI; AllowReassociation=true |
| change_rt | Create or replace only 0.0.0.0/0 in the exact same-AZ protected route table with that ENI |
| disable_sdc | Set SourceDestCheck.Value=false on the exact protected member instance |

Known route absence chooses create; known presence chooses replace. Ambiguous
acknowledgements never trigger fallback mutation. Final success independently
observes the exact EIP association, default-route ENI or source/destination flag.
No new failover/health algorithm, DLQ, AMI pipeline or orchestration is added.

## Durable evidence and failure semantics

The journal reuses WP4B canonical immutable storage and closed effect validation.
Plans bind namespace/token, exact immutable operation digest and request. Durable
attempt evidence precedes every external mutation; fresh guards follow storage.
Reconciliation of retained attempts precedes current authorization/deadline
checks. APPLIED is retained before a later rejection; ABSENT is terminal known
non-success with no resend; UNKNOWN/malformed effects remain UNCERTAIN.

Observed and reconciled records are independently validated against exact plan
and token. Damaged observations are never overwritten. Receipt construction
revalidates every included effect. Receipts and outcomes are content-addressed,
immutable records; a retry can produce a later authoritative observation without
overwriting earlier evidence.

Corrupt retained intent before any durable attempt is FAILURE. After an attempt,
invalid JSON or structure is UNCERTAIN using only the installed namespace and
validated operation identity to discover attempts. Caller input never reconstructs
protected intent. A plan alone is not an attempt. Known fresh pre-call rejection
is FAILURE; a retry of its durable attempt reconciles absence and never resends.
Once a routing attempt exists, inability to establish final success remains
UNCERTAIN; it must not promise traffic was preserved.

## Validation and remaining work

Run `python -I -B scripts/tests/recovery/run.py` for hermetic production-path
tests, including finite in-memory behavioral mutants. The mutants must be killed
by assertion failures, with unchanged controls passing; import/syntax/setup
errors do not count. Tests cover positive recovery, revocation/history/content,
health, persistence windows, cleanup confinement, NAT membership/runtime and
effect uncertainty. Existing WP1–WP4B suites remain required.

No legacy enrollment, migration, unknown-resource adoption or dual-running
authority exists in this greenfield slice. Any historical migration prose in the
plan is inert/deferred. WP4A-N2's invalid documentation byte is untouched. Fresh
Linux E3 and AWS/provider-backed realization remain unverified, separately from
these provider-free contracts. WP4D remains pending.
