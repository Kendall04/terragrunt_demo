# E15-E — DEV ECS workload and controller quiescence

CURRENT CONTRACT, 2026-10-12. Baseline `ace06da4434b873b9fc1602f2befb4fa7d45cf44`,
branch `codex/e15e-ecs-quiescence`, existing `C:\proyectos\terragrunt_demo` checkout.
**PARTIALLY_READY overall. Complete DOWN/EXECUTE remains denied.** All inspection,
implementation and tests are offline. No AWS, provider initialization, installation,
remote state, deployment, Git remote operation, NAT change or other checkout is used.

[Adapter and protocol](../../scripts/lifecycle/ecs_quiescence.py) and
[focused tests](../../scripts/tests/ecs_quiescence/run.py) are separate from current
runtime wiring. This document is the integration contract for this increment.
The [architecture](architecture.md), [delivery](deployment.md), [security](secrets-strategy.md),
[WP5](e1-protected-environment-lifecycle.md), [E15-B](e15b-dev-down.md),
[E15-C](e15c-exact-destroy-approval.md) and [E15-D](e15d-administrative-handoff.md)
retain their current contracts. No global inventory, package hashes, authority,
acceptance gate, workflow, IAM or Terraform source is changed.

## Actual ECS mutation and scheduling sources

These are active source paths, not evidence of installed resources. The repository
has no live installation and no public mutation identity is active. Inert WP7 text
under `ci/authority/retired` and shell library regression functions are provenance,
not authorized runtime paths.

| Source and actor | Exact scope / mutation / asynchronous behavior | Inhibition and readback needed |
| --- | --- | --- |
| [WP3 build/finalizer](../../scripts/internal_release/runtime.py), qualification/eligibility | Shared neutral digest-qualified ECR content and manifests; no ECS launch/count/service mutation | Qualification can continue independently; an eligible release cannot deploy without WP4 E2 ownership. Preserve digest delivery and retained ECR/evidence |
| [WP4 normal delivery](../../scripts/normal_delivery/delivery.py), [authorization](../../scripts/normal_delivery/authorization.py), [SDK adapter](../../scripts/wp4d/aws_runtime.py) | Separate `normal-delivery/deploy-dev` / `promote-prod` execution roles. Register exact color task families, drain/attach/start exact color services, switch ALB, schedule inactive cleanup. ECS UpdateService settles asynchronously; registration alone does not start tasks | [Runtime](../../scripts/wp4d/runtime.py) acquires environment application E2 owner; mutation clients check that owner and deadline at dispatch. Hold DEV E2 throughout guarded destruction; verify every existing deployment/task and outstanding issued effect |
| Normal historical rollback, [workflow](../../.github/workflows/rollback-manifest.yml) | Uses same environment normal delivery gateway, protected history and current qualified eligibility; can start either color and replace revisions | Same E2 domain and readbacks. PROD independent approval remains mandatory; DEV shutdown grants no PROD authority |
| [Emergency recovery](../../scripts/recovery/application.py), SDK `Application` | Exact existing-content DEV/PROD services, count increases, ALB switch, cleanup scheduling. No task registration/publication | Separate emergency role but same environment application E2 domain. UNCERTAIN owner blocks shutdown; never infer settlement from invocation exit |
| Scheduled `cleanup-recovery/cleanup-dev` / prod, same recovery code | Dynamic EventBridge rule, target id `scale-down`, exact protected cleanup Lambda. Scales only freshly identified inactive color to zero; removes target/rule. Cannot create content or scale the active color up | E2 attaches native event envelope plus environment/operation/generation schedule identity. Lifecycle acquisition clears schedule in the new head; queued cleanup cannot acquire across ACTIVE ownership or stale generation. Already checked/dispatched cleanup must still settle. No need to grant WP5 generic EventBridge administration |
| [WP5 high-risk lifecycle](../../scripts/lifecycle/runtime.py), [plan boundary](../../scripts/lifecycle/contract.py), [IAM inventory](../../scripts/tests/security_root/wp5_iam.py) | Exact installed environment resources; service creation/deletion/config reconciliation and bootstrap task registration/deregistration through fixed Terraform. Skeleton counts initially zero; task/count changes ignored. No ECS task/execution PassRole or RunTask/StartTask | Existing application E2 domain, exact package/image/source/configuration, membership and approval gates. A saved Terraform plan cannot supply controller closure. New adapter supplies no Terraform invocation or bypass |
| [Native ECS service scheduler](../modules/target/dev/apps/modules/ecs_service/service.tf) | Two independent `demo-dev-app-api-{blue,green}-svc` services in `demo-dev-platform-main-cluster`; FARGATE, REPLICA, min healthy 100/max 200. Default ECS rolling controller, not ECS-native blue/green/CodeDeploy. Can replace unhealthy/deploying tasks while desired count is positive | E2 does not fence ECS. Both colors must be zero with a single PRIMARY COMPLETED deployment at zero; no running/pending or remembered nonterminal tasks. Unsupported EXTERNAL/CodeDeploy/DAEMON/task-set controllers block |
| [Fargate capacity providers](../modules/target/dev/platform/modules/ecs_cluster/main.tf) and container health | Cluster declares FARGATE/FARGATE_SPOT, but services explicitly use FARGATE. Capacity-provider declarations do not independently request tasks. Essential app/task termination differs from non-essential one-shot readiness-probe termination | Observe task `lastStatus` and `desiredStatus`, not a stopped probe container. Preserve the exact service launch/controller contract |
| Separately held human security administration / external AWS-native configurations | Human can install/change protected control or service-linked/IAM dependencies. No ordinary application role has ECS infrastructure control. No ECS Application Auto Scaling resource, ECS scheduled RunTask, Step Functions task launcher or GitHub scheduled deploy is present | Future installation must verify the absence of additional writers/scaling/start schedulers, constrain changes while guarded, and establish settlement. Repository absence and E2 alone cannot authenticate live controller inventory or restrict separately privileged humans |

NAT ASG controllers are different resources and outside this increment. PROD has
its own services/cluster/E2 head and is never selected. Shared alerts, secret
metadata, security root, backend/locks, ECR and retained evidence are never drained
or deleted. DEV SQL disposal and its separate infrastructure/SQL-loss confirmations
remain accepted; no SQL backup/restore or data authority changes are introduced.

## Implemented bounded protocol

`scope(value, protected)` reuses E15-B exact DEV identity and WP5 authorization.
It permits only approved high-risk DEV teardown in edge/apps/platform/data/global,
pins the DEV cluster ARN and requires exactly the two service ARNs in the installed
apps address/type/membership table. Scope carries request, operation UUID, layer,
revision/source/backend/workspace and an additional apps-membership digest. No name
or Environment tag alone authorizes draining. PROD/shared/secrets/foreign membership
are rejected.

`Quiescence` receives the original acquired `environment_mutation.Authority` and
compares its complete ACTIVE head on every boundary: exact environment/application
domain, protected coordination bucket, binding, operation, request hash, invocation
owner and generation. It never acquires, finishes, releases or replaces that owner.
It never returns WP5 SUCCESS. The existing E2 mutex surrounds actual SDK dispatch;
the durable E2 CAS remains the only environment coordination mechanism.

The internal `ProtectedBoundary.require(selected, owner, attempts)` is a necessary
trusted port. Its obligation is authenticated current source/package/session/config
admission, exact operation approval for draining both DEV service ARNs (a per-layer
destroy approval alone does not authorize this additional apps mutation), closure
of authorized writers and native controllers, generation-fenced
cleanup, absence of native scaling/start schedulers, and settlement of every prior
or current attempted asynchronous effect. Its fixed proof binds the scope/owner and
all five source classes; missing any class rejects. Proof labels are output metadata
of this port, not evidence that a caller can self-declare.

The **only concrete boundary**, `HandoffBoundary`, requires the exact E15-D Handoff
class, immutable approved scope and its SDK-authenticated existing executor session.
It then raises BLOCKED unconditionally: E15-D's storage/session installation does
not install this new source, attest live ECS controller inventory or settle old
AWS effects. There is no Boolean installation flag, public adapter selector,
synthetic installation acceptance or alternate installed success path. Positive
tests subclass the internal port as explicitly synthetic domain fixtures.

After closure admission, `begin()` stores one immutable intent including original
owner, complete baseline deployments/tasks and a 300-second observation window.
It creates a conditional per-color attempt **before** issuing only
`UpdateService(cluster=<exact DEV ARN>, service=<exact member ARN>, desiredCount=0)`.
`ECS.drain()` itself requires the original E2 owner, closure port and deadline at
SDK dispatch. No task definition/configuration override, force deployment, StopTask,
DeleteService, registration, scaling mutation or caller-selected ARN is accepted.
The response is ignored as safety evidence. A crash/lost acknowledgement burns that
service's send; a duplicate request may observe or send an untouched other color
only after renewed closure, but never resends an attempted color.

`check()` performs at most 16 explicitly requested observations, no sleeps or
background polling. Each observation must complete within 30 seconds. It reads the
exact active cluster and both services (or exact service-ARN MISSING), all service
deployments, all cluster tasks with desiredStatus RUNNING using bounded complete
pagination, and DescribeTasks for the union of live and all previously observed
task ARNs. ECS PENDING tasks have desiredStatus RUNNING; querying desiredStatus
PENDING would miss them. Every task must belong to an exact DEV service group;
standalone/foreign tasks block rather than receive shutdown authority.

QUIET requires both service desired/running/pending counts zero and one PRIMARY
COMPLETED ECS deployment at zero with the exact service task definition. Every
remembered task must have both lastStatus and desiredStatus STOPPED; terminal task
absence, an ACK, a stopped container, service counts or an empty listing alone are
insufficient. Old/in-progress deployments, new tasks, PENDING/restarting/stopping
tasks, unsupported controllers, pagination failures and partial/ambiguous responses
fail closed. The baseline and every retained sample contribute to the remembered
cohort. Failed quietness samples remain diagnostic evidence.

Collection timestamps bound the age/duration of the SDK read, not the age of an
eventually consistent ECS server view. Without authentic effect settlement and
accepted live readback semantics, matching responses cannot prove server freshness
or future quietness. The concrete boundary therefore never promotes them to QUIET.

The journal reuses E15-D encrypted/version-pinned conditional storage in the
existing WP5 operation namespace:

```text
e1-lifecycle-dev-<account>-<region>/operations/environment-lifecycle/infra-high-risk-dev/<operation UUID>/ecs-quiescence/
  intent.json
  blue-attempt.json
  green-attempt.json
  sample-0.json ... sample-15.json
```

There is no lease reset/delete/update or new lock object. Fixed stages use exact
version/hash/encryption readback and IfNoneMatch conditional creation. Incomplete
publication, storage errors or ambiguous responses never trigger blind resend.
Raw SDK task definitions, secrets, task environment, Terraform state and SQL data
are excluded; only identifiers/counts/deployment metadata and task statuses persist.

`run()` gives BLOCKED for uninstalled closure before touching mutation, otherwise
UNKNOWN on failure, or a QUIET receipt with `execution_authorized=false` and
`down_state=UNKNOWN`. `begin/check/require_quiet` raise on unproven conditions.
Evidence expiry/readback exhaustion is not E2 expiry and never releases ownership.
E2-R interrupted owners and E4 UNKNOWN/UNCERTAIN remain held and cannot be replaced.
A new E2 generation cannot cancel an old checked/issued call; controlled tests
demonstrate that late completion. Even two apparently quiet snapshots cannot prove
an unbounded pending effect will never complete: the trusted settlement port is
still mandatory and concretely unavailable.

## Exact WP5 integration seam and blockers

These are implemented interfaces; they are **not currently wired**:

1. After existing package/source/image/current-config, exact destroy approval,
   consent and original E2 admission, construct `scope`, `ECS(fixed_ecs_client,
   selected)`, `Journal(Handoff.storage, selected)`, and `Quiescence(value,
   protected, authority, adapter, journal, installed_boundary, trusted_clock)`.
   Clients require fixed region/timeouts and total SDK attempts one, as existing
   WP5 clients do. No event supplies any port, client, clock, principal or object path.
2. A future accepted boundary must actually implement and independently read back
   source/controller inhibition and issued-effect settlement. Current
   `HandoffBoundary` always blocks. Do not replace it with JSON flags or snapshots.
3. Call `begin()` once, then explicit bounded `check()` observations as tasks drain.
   Persist/resolve the exact returned sample index and digest. QUIET is evidence
   under the same owner, not a SUCCESS return suitable for `E2.execute`/finish.
4. `require_quiet(receipt, stage)` validates retained evidence, original owner and
   freshness and returns a new fully refreshed receipt. Invoke immediately before
   and after edge/apps/platform/data/global destructive boundaries, alongside
   E15-C exact saved-plan/current-state/single-use and fresh E15-B checks. No method
   dispatches Terraform or approves SQL loss. Never start a stage with stale/missing
   evidence; stage mutation remains exclusively in the existing WP5 protected engine.
5. Keep the **same E2 ownership across all dependent stages and their terminal
   readbacks**. Current WP5 is per-layer and finishes successful layer ownership;
   passing a receipt between released/reacquired per-layer owners is rejected.
   Combined lifecycle work must resolve that orchestration gap within E2/WP5 before
   activation. This increment cannot prove whole-DOWN fencing by changing runtime
   early or adding another distributed lock. Within an in-flight stage, quietness
   lasts only if the accepted controller/writer inhibition remains in force; pre/post
   observations alone cannot enforce it. Expiry or invalidation retains UNKNOWN.
6. After service deletion, exact ARN MISSING plus remembered STOPPED tasks is
   supported. After cluster deletion, this adapter deliberately cannot read those
   task identities and blocks; combined lifecycle needs an accepted terminal
   handoff from positively verified termination to authoritative cluster absence,
   while preserving source inhibition/owner through data/global completion. It
   cannot erase the remembered cohort and reinterpret missing tasks as STOPPED.
7. E15-D `require_down_quiescence(value, protected, authority)` remains the existing
   future composition point for ECS and separate NAT proof. Its unconditional
   denial, `exact_destroy.Execution.before_dispatch` and local `down-execute`
   denial are unchanged. Overall DOWN SUCCESS still requires existing complete
   empty managed-state, residual and terminal evidence, not this ECS receipt.

Any owner/generation/scope/config/source change, reenabled writer/scheduler/scaler,
new/unfinished deployment or task, pending late effect, expired/partial/corrupt
evidence, unavailable installation/session/readback invalidates quietness. Retain
intent/attempts/samples and E2 ACTIVE for diagnosis; no force unlock, takeover,
general compensation or arbitrary retry is added.

## Narrow authority and installation requirements

The existing trusted principal is
`arn:aws:iam::<account>:role/e1-controller-infra-high-risk-dev-exec`, CodeBuild
service trust with exact project/account. Existing WP5 generated IAM already allows
ecs:UpdateService on published exact service members and DescribeClusters,
DescribeServices plus cluster-conditioned ListTasks. Draining both colors is a
new protected code path requiring installation approval, not new blanket IAM.
Application, gateway, normal delivery and PROD acquire no new permissions.

Missing readback: **ecs:DescribeTasks** on
`arn:aws:ecs:<region>:<account>:task/demo-dev-platform-main-cluster/*`, constrained
to the selected cluster/region where supported. The wildcard covers generated task
IDs only, never other clusters/accounts/environments. The complete remembered
cohort/resource identity must also be checked in protected code. No ecs:StopTask,
RunTask, StartTask, task PassRole or ECS administrative wildcard is needed or added.

Journal storage needs exact own operation-object GetObject/GetObjectVersion and
conditional PutObject plus the E15-D private/encrypted/versioned/no-delete guards.
Current own journal permissions do not prove those guards or supply version reads.
Live controller inventory/absence and prior-effect settlement need an accepted
administrative/read-only observation contract; their permissions/installation are
not silently invented here. If an unexpected scaler/start scheduler exists, block
and require separate authority design, rather than grant generic suspension APIs.

All additions must go through the existing separate security administrator,
protected installation/package/image/source/configuration and role-ID/session gates.
Combined integration must admit this source/test/doc to the common inventory,
include/compare bootstrap bytes in WP5 packages, reconcile derived hashes, wire
the acceptance suite and approve genuine installation evidence. None is done on
this isolated ECS branch. Authentic AWS IAM, ECS eventual consistency/task
termination, scheduling/controller absence and S3 conditional semantics need
separately authorized live validation. No installed identity or privilege is claimed.

## Offline validation and disposition

Focused entry: `python -I -B scripts/tests/ecs_quiescence/run.py`. It installs the
existing hermetic process/socket/credential guard and uses actual ECS SDK adapter,
conditional encrypted/versioned journal, E2 authorities and E15-D concrete boundary
with synthetic service transports. Tests use barriers/events/fault injection,
never sleeps. Positive domain closure fixtures are not installed/live evidence.

| Capability | Classification |
| --- | --- |
| Exact DEV SDK drain/readback, conditional journal, evidence correlation and fail-closed boundaries | READY_IN_REPOSITORY; uninstalled |
| Whole guarded DOWN source closure and continuous E2 ownership / cluster-absence handoff | PARTIALLY_READY; combined integration required |
| DescribeTasks/version-read permissions, genuine controller/settlement contract and protected source installation | REQUIRES_OWNER_DECISION before installation |
| Authentic IAM/session/storage/controller/readback/late-effect behavior | REQUIRES_LIVE_AWS_VALIDATION |

Final focused **49 tests passed**, no failures/errors/skips. The initial 43-test
run had one overly strict fixture expectation about reobserving a lost ACK after
synthetic settlement; it was corrected without permitting resend. Intermediate
46-test runs passed; the bounded self-check added real SDK datetime normalization,
closed per-deployment/color-family validation and post-publication freshness,
then the final 49 passed. All positive closure remains explicitly synthetic.

Fresh related suites passed: E15-D 50, E15-C 46, E15-B 42, E15 30, E2 41,
E2-R 23, E4 28, E13 40, E8 18, E7 8, E11 33 and E14-B 19. The E1/WP gate
was attempted once; its process was interrupted before final report/additional
checks, and four suites have incomplete logs (WP1 authority, controller compute,
ownership publication, WP7 final acceptance). **983 tests and AC1–AC16 are not
claimed passed.** Eleven completed suite logs record 647 unit tests with OK:
security root 18, control bundles 22, build supervision 150, qualification 110,
internal release 33, normal delivery 20, delivery 98, recovery 53, WP4D 33,
lifecycle 49 and workflows 61. Security-root/control-bundle/build-supervision/
qualification runner results failed source admission despite their unit tests
passing: exactly the three new Python files are UNMODELED_SOURCE. No common file
was changed to suppress this intended combined-integration requirement.

Independently completed checks passed: actual provider-free E2/WP4D/WP5/WP6
IAM/trust/PassRole/installation expressions, E13 retry/destination/queue expressions,
E15 empty Terraform plan shape, generated security and workflow parity, existing
extracted packages, current KDD/immutable approved E1 hashes, final active authority
and workflow boundaries, full parsing (170 Python/50 JSON/22 generated YAML), all
21 local links in this document, Terraform fmt check and diff whitespace. Source
inventory verification reports only those three unmodeled files. Existing packages
remain unchanged and deliberately exclude the uninstalled ECS source. Activation
is still 0/11 external, 0/16 WP4D and 0/8 WP5.

Logs are outside the checkout in this task's visualization output directory.
No Linux/shared-VM, application/container, ShellCheck, TFLint or tfsec rerun is
claimed: shell/app/Terraform/IAM inputs are unchanged. Inherited 24 TFLint warnings
and 46 tfsec findings remain historical baseline findings, not fresh lint results.
One bounded self-acceptance checked scope, original E2 ownership, immutable
attempts, live/remembered STOPPED requirements, controller failure cases,
installation denial, unchanged authority and continued DOWN/EXECUTE denial.
No live quietness, installation or full DOWN success is inferred from these tests.
