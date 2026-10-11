# E2 environment mutation arbitration

CURRENT repository contract, based on integrated baseline
72141a7f666ce058ce4d18eb3c3adc180e521ca4. AWS remains undeployed. This extends
[accepted E1](e1-final-acceptance.md); its qualification, eligibility, exact roles,
independent prod approval, E3 and immutable effect journals remain authoritative.

## Conflict matrix

Operations sharing a domain need exclusive mutation ownership. Every domain is
inside its own environment bucket; dev and prod never share ownership.

| Operation | Domain | Shared mutation targets / conflicts |
| --- | --- | --- |
| Normal delivery, prod promotion, normal historical rollback | application | Both ECS colors/task families, listener/candidate rule, cleanup rule, protected history indexes; conflict with each other and all rows below using application |
| Existing-content emergency recovery | application | Existing revision capacity, listener/rule and cleanup schedule; no registration/publication authority |
| Scheduled inactive-color cleanup | application | Old service capacity and cleanup target/rule; must match the schedule generation before admission |
| WP5 create/reconcile/approved teardown: global/data/platform/apps/edge | application | Network, SQL, ECS/ALB skeletons and dependent graph configuration; overlap delivery/recovery/cleanup and one another |
| WP5 shared root | shared | SNS/alerts only; conflicts with another shared mutation, independent of application |
| WP5 secrets root | secrets | Fixed metadata-only consumer; independent of application/shared, no secret value or metadata administration |
| Status, retained result, qualification/authorization reads, lifecycle plan | none | Read-only; never gains mutation authority |
| NAT per-slot recovery | existing E1/E13 boundary | Not modified or claimed to be coordinated by this application arbitration; global lifecycle versus NAT needs separately bounded E13 integration |

The lifecycle grouping is driven by actual dependency/resource ownership, not AWS
account identity. There is one application/DB graph per environment. Shared SNS
and metadata-only roots need neither runtime ownership nor application blocking.

## Primitive and ownership

[The adapter](../../scripts/environment_mutation.py) uses existing versioned
protected WP4 storage, not a new service/database. There is one fixed head at
arbitration/environment/domain.json. An administrator initializes canonical
generation-zero RELEASED evidence once, using conditional creation and exact
readback. Workers never initialize missing heads. Installation must prepare and
verify all three heads before enabling admitted E1 compute. No installation or
resource identity is fabricated here.

Acquisition reads the exact protected head and performs one S3 PutObject with
If-Match on its current ETag. Only RELEASED can become ACTIVE. The head binds
environment, domain, monotonic generation, installed binding, exact logical
operation UUID, canonical request digest and a fresh protected invocation UUID.
Two contenders reading the same ETag cannot both acquire. Lost acknowledgements
are reconciled by exact readback; there is no blind write retry.

[AWS conditional-write semantics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
provide this atomic persistence boundary. It is not an ECS/ALB transaction.
Protected synchronous call guards re-read ownership immediately before each
admitted mutation, recheck the E1 deadline after storage reads, and prevent
this invocation from releasing while its own call
runs. Cross-process exclusion comes from S3, independently of GitHub concurrency
or process-local locks.

The installed WP4 entrypoints wrap the existing ECS/ALB/EventBridge mutation
clients; history publication remains inside the same grant. WP5 holds admission
before preparation/plan/quiescence for mutation requests and checks ownership at
the saved-plan apply boundary. Gateways/status/plans do not acquire. The old
retired wrappers still reject. Domain algorithms and current authorization are
unchanged.

## Release, interruption and fencing

There is **no lease expiration and no automatic takeover**. A deadline never
proves a worker stopped. A paused, crashed or interrupted invocation retains
ACTIVE ownership. Failed/UNCERTAIN/UNKNOWN outcomes after a possibly issued
mutation also retain ownership; exceptions cannot release that hold. This
deliberately trades availability for single-operator safety.

SUCCESS, or definitive failure before any mutation call, writes a conditional
immutable binding/operation/request/generation terminal before conditional
release. Retries of terminal operations return historical status without
acquiring or republishing indexes. A still-running owning invocation can reconcile
its same E1 journal under the same grant; it never resends attempted stages.
Another invocation, even with the same operation UUID, cannot borrow ownership.
WP5 retained UNKNOWN remains read-only and cannot apply again.

Old invocation objects reject all later writes/releases after release or ownership
change. Generation/owner/body validation and ETag CAS fence stale requests.
No expiration-based fencing is needed because authority never expires. The
local synchronous guard prevents release during an admitted call; independent
controllers cannot manufacture release of an ACTIVE peer.

After an interrupted/uncertain worker, a separately authenticated operator must
establish termination of the exact invocation and reconcile its immutable
attempt/effect evidence before deliberately releasing the hold. There is no
force-unlock endpoint or automated orphan recovery in E2. Never reset/delete a
head, infer termination from elapsed time, or release while an AWS call/provider
may still run. Administrative repair and general compensation remain separately
authorized operational work, not simulated controller safety.

Missing/corrupt heads, wrong identity, unavailable reads/CAS, unknown effects or
stale schedule evidence fail closed. E2 admission failure reports UNCERTAIN
(WP4) or UNKNOWN (WP5), never SUCCESS. Historical status queries are distinct
from new mutation success.

## Cleanup generation

An owning delivery/emergency operation records the exact schedule generation.
Its EventBridge target uses an InputTransformer preserving native event ID,
account, region and resources, with the protected generation/operation/binding.
Actual target readback must verify that transformer as well as the fixed target.
Cleanup checks the exact originating rule and generation before acquiring;
it preserves that evidence during its grant and consumes it on success.

A newer application-domain acquisition invalidates older cleanup evidence,
even when the new operation later fails before scheduling. Delayed/replayed old
events cannot stop a service or remove/delete a newer schedule. Active cleanup
blocks new activation until it safely completes. Existing fresh topology,
capacity, immutable attempts and no-resend checks still apply.

## Authority, packaging and limits

Only normal/emergency/cleanup execution roles receive own application-head
GetObject and If-Match PutObject; lifecycle execution roles receive only their
environment's three heads. Each binding gets conditional-create/read access
to its own small immutable arbitration terminals. No caller/gateway/NAT role
receives arbitration authority; there is no head deletion permission. Existing
bucket barriers additionally confine lifecycle exceptions to coordination
objects, preserve evidence immutability and enforce conditional updates.

No ECS/ALB/EventBridge/PassRole privilege is added. Existing package admission
includes the exact coordination implementation and refreshed binding digests.
WP5 compares those bootstrap bytes to the verified package. All public identities,
WP4D and WP5 installation/runtime activation maps remain empty.

Potential integration overlaps: WP4D runtime/package source selection, generated
controller_compute Terraform, authority package hashes, source inventory and
current KDD. NAT handler algorithms/events and toolchain/Docker/CI dependency
pins are untouched. Peer branches must regenerate shared derived artifacts from
the combined source; E2 does not merge them.

E4 remains deferred: partial listener/rule/schedule/index effects, compensating
writes, database/schema reversal and general orphan repair are not redesigned.
No live IAM/provider installation/AWS or end-to-end deployment proof is claimed.

## Validation

Focused hermetic command: python -I -B scripts/tests/mutation/run.py.
The accepted E1 gate keeps its 959 regression plus 24 WP7 tests and adds E2
as an independent suite. The actual generated E2 bucket-policy check is
python -I -B scripts/tests/mutation/check_static.py. Both are enforced by the
[existing acceptance gate](../../scripts/tests/final_acceptance/gate.py).

Deterministic barriers exercise simultaneous contenders and an SDK call paused
while other mutation classes try entry. Tests cover real E1 delivery/recovery
journals, installed transport construction, WP5 saved-plan execution, separate
environments/domains, terminal retry, same-owner reconciliation, interrupted
ownership, stale workers, invalid/absent storage, failed/lost CAS acknowledgements,
cleanup generations and narrow positive/negative IAM. Reports are outside the
worktree; provider-free checks never initialize or contact AWS.

### Final local evidence

The stabilized-source gate returned E1_REPOSITORY_ACCEPTANCE_PASS:
959 accepted regressions + 24 WP7 = **983 E1/WP tests**, plus **41 E2 tests**,
with zero failures, errors or skips. All AC1–AC16 and all ten static checks passed:
generated security/workflow wiring, KDD/immutable approved contracts, extracted
packages, actual E2 bucket barriers, provider-free WP4D/WP5/WP6 Terraform,
check-only formatting and Git whitespace. Source inventory and parsing passed
(140 Python, 46 JSON, 22 generated YAML files); installation/activation maps remain
0/11, 0/16 and 0/8.

One bounded acceptance self-check preserved approved E1 hashes, conflict domains,
package closure, journal/authority boundaries and inactive installation gates.
Concrete implementation checks closed terminal retry/index publication, exact
cleanup transformer readback, deadline consumption during ownership reads and
Python bool/float equality in generation evidence. Cleanup compares canonical
generation evidence, so True and 1.0 cannot substitute for integer 1.
The WP6 disposable policy checker includes the new E2 storage local; its existing
positive/negative assertions remain intact. No independent reviewer was used.

The report records exact precommit source hashes and dirty Git identity;
validation documentation was updated afterward and checked separately. No AWS,
provider initialization, Terraform state operation, deployment, dependency
installation, push or PR occurred. No fresh Linux/VM execution is claimed;
accepted E3 was preserved and exercised through the existing hermetic regressions.
Explicit worker termination/reconciliation after interrupted ownership and E4
general compensation remain operational/deferred boundaries.
