# Durable Spec — E1 IAM / Effective Authority Hardening

Status: Approved for technical planning

Owner intent: Human-approved decisions captured below

Implementation status: Not implemented

Discovery baseline: `main` at `305e3a7e4e486836baa3889746affa97b9f22733`

## 1. Problem and evidence

The completed read-only authority audit established that the repository's named
roles do not reliably bound their effective authority. Infrastructure CD can
combine workload-policy mutation with mutable compute; ordinary GitHub roles
share environment-shaped OIDC subjects; deploy/promote can register runtime
definitions, pass application or execution roles and activate those definitions.
Routing mutations are independently available, and legacy app-CD combines
publication, deployment and cross-environment record writes.

These are repository-defined capabilities, not evidence of deployed resources or
an executed exploit. The audit also found that manifest rollback uses deployment
roles and registers a revision, whereas emergency rollback uses an existing-color
flip. The remaining app-CD fallback in the infrastructure readiness job must be
accounted for; a role cannot be assumed unused from its legacy label.

Evidence anchors:

- [IAM scopes and trust subjects](../../terraform/infra/shared/modules/iam_github/locals.tf),
  [infrastructure CD](../../terraform/infra/shared/modules/iam_github/github_terragrunt_cd.tf),
  [delivery roles](../../terraform/infra/shared/modules/iam_github/github_delivery_split.tf),
  [legacy/rollback roles](../../terraform/infra/shared/modules/iam_github/github_ecs_blue_green.tf).
- [Deployment sequence](../../scripts/ecs-blue-green-deploy.sh),
  [runtime template](../../demo-api/deploy/task-definition.template.json),
  [runtime permissions](../../terraform/infra/apps/fargate/demo.tf),
  [ECS role trusts](../../terraform/infra/apps/fargate/modules/ecs_service/iam.tf).
- [Manifest rollback](../../.github/workflows/rollback-manifest.yml),
  [emergency flip](../../.github/actions/ecs-blue-green/action.yml),
  [infrastructure readiness fallback](../../.github/workflows/cd.yml),
  [cleanup identity](../../terraform/infra/apps/fargate/iam_lambda_scale_down.tf).
- [Architecture](../../terraform/docs/architecture.md),
  [delivery](../../terraform/docs/deployment.md),
  [security](../../terraform/docs/secrets-strategy.md),
  [owner constraints](../../terraform/docs/decisions-and-limitations.md).

Implementation determines the baseline behavior where older narrative or policy
comments disagree. This specification defines the desired E1 contract; it does
not assert that the baseline already satisfies it.

## 2. Desired outcome and threat boundary

E1 must bound what each responsibility can accomplish both directly and by
composing allowed actions. Narrower individual policies are insufficient if an
equivalent prohibited path remains through another identity, API, workflow,
artifact, runtime definition or recovery mechanism.

Evaluate a caller that controls the inputs and code executed with one
responsibility's credentials, including the OIDC token obtainable by its job.
The caller may bypass ordinary helper scripts and invoke any authorized API.
It must not gain unrelated responsibility or environment authority. Controls
protecting qualification, execution or authority must not be replaceable,
disabled or reconfigured through that caller's own grants.

Separate, explicitly authorized security administration may change the security
contract. E1 does not defend against an administrator deliberately changing the
protected contract or repository governance through separately held authority.
Merely labeling an ordinary job or mutable helper "trusted" does not create
this separation.

## 3. Security invariants

1. **Responsibility-specific authority:** permission to perform one responsibility
   does not confer acquisition or exercise of another responsibility's authority.
2. **Environment isolation:** dev authority cannot mutate prod resources, prod
   control/evidence or acquire prod authority, directly or through shared resources.
3. **No privilege creation:** ordinary infrastructure lifecycle cannot manufacture
   broader workload authority and execute or arrange execution under it.
4. **No arbitrary runtime substitution:** deployment/promotion cannot execute
   unrelated content under application, execution or other workload identities.
5. **No role-field substitution:** allowed role passing cannot be repurposed to
   exchange task/execution roles or obtain equivalent unauthorized privileges.
6. **Qualified artifact selection:** deployment and promotion consume independently
   qualified, eligible release identities; pullability is not qualification.
7. **Fail closed:** missing, contradictory or unverifiable authority, contract or
   release evidence cannot authorize the privileged operation or broader fallback.
8. **Operational preservation:** legitimate lifecycle, delivery, runtime and bounded
   recovery remain usable; denying every operation is not successful hardening.

## 4. Required responsibility boundaries

These are responsibilities, not prescribed role names or a required role count.
One operator may deliberately perform multiple responsibilities through their
distinct authorization boundaries.

| Responsibility | Authorized outcome | Excluded authority |
| --- | --- | --- |
| Infrastructure planning | Read relevant environment configuration/state and produce plans | Infrastructure mutation, publication, activation, secret-value access or acquisition of apply/admin authority |
| Ordinary infrastructure lifecycle | Reconcile authorized environment infrastructure and its bounded operational configuration | Manufacture broader workload privilege; administer protected trust/security controls; mutate unrelated environments |
| Sensitive/bootstrap/security administration | Explicitly establish or change protected identities, trusts, security policies and bootstrap resources | Implicit acquisition by ordinary CI, build, lifecycle, deployment or recovery jobs |
| Release build/publication | Build and publish release content and identity through the release contract | Activate services/traffic, claim unperformed deployments, or acquire deployment/admin authority |
| Application deployment | Introduce and activate an eligible qualified application revision within the approved runtime contract; record its outcome | Arbitrary executable selection, contract redefinition, privilege or role-field substitution |
| Production promotion | Activate an eligible, already qualified release in prod without rebuilding or substituting it | Dev authority acquisition, unrelated runtime content, security administration |
| Manifest/history rollback | Redeploy a historical release still eligible under the applicable deployment contract | Eligibility bypass based solely on historical presence; weaker runtime authorization |
| Emergency color flip | Restore traffic to an already deployed color, including necessary capacity restoration and bounded health checks | New revision/content introduction, role replacement, publication or security administration |
| Application runtime | Preserve required application DB access and KMS encryption/decryption | Delivery/control-plane administration or unrelated workload authority |
| ECS execution | Pull authorized images, deliver logs and bootstrap authorized secrets | Deployment-selected use as general application credentials |
| Bounded cleanup/recovery | Perform necessary cleanup or recovery on owned resources | Arbitrary revision/content introduction, IAM escalation, unrelated service mutation or cross-environment control |

Infrastructure and deployment ownership must remain explicit: Terraform owns
skeletons; deployment owns task revisions/counts and ALB forwarding. Any authority
reallocation needed for E1 must preserve the operational responsibility without
creating competing owners or requiring ordinary automation to retain admin power.

## 5. Required security behavior

### 5.1 Infrastructure lifecycle and sensitive administration

Ordinary infrastructure CD is not administrator-equivalent. It must not combine
workload IAM policy/trust mutation, editable policy versions, role passing,
compute creation/modification or invocation into authority beyond its approved
responsibility. Protecting only the initiating principal is insufficient; the
effective permissions of every reachable workload principal matter.

OIDC provider administration, workload IAM policy/trust administration, KMS
policy/grant administration, secret resource-policy administration and protected
artifact/storage administration belong to a separately authorized sensitive
responsibility. Ordinary lifecycle must not retain unrestricted administration
of these controls. Necessary bounded lifecycle operations must remain possible
within a security contract ordinary lifecycle cannot broaden.

A retained high-risk/admin path must have a materially distinct responsibility
and trust boundary. An approval label or another role with interchangeable
acquisition and equivalent broad authority is insufficient. Legitimate bootstrap
and later authorized security changes must have an explicit operational path.

### 5.2 Acquisition and environment boundaries

CI, build, infrastructure deployment, application deployment, production promotion,
recovery and sensitive administration must have meaningful AWS/OIDC authorization
boundaries. A job's qualifying token must not automatically obtain unrelated roles
because those roles accept the same environment subject. Role-secret names,
masked ARNs, workflow conventions and session names are not security boundaries.

Dev authority must not obtain prod roles or mutate prod infrastructure, workload
identities, routing, deployment records or protected dependencies. This includes
indirect authority through shared OIDC, storage, ECR, KMS and recovery resources.
Shared topology may remain; separate accounts are not a prerequisite.

Environment-neutral publication may supply candidates later consumed by prod,
but publication alone must neither qualify a candidate for prod nor alter an
already selected prod release identity. Calling a dev-controlled destructive or
administrative dependency "shared" does not exempt it from this boundary.
Broader operational independence remains a separate target; any shared-resource
authority change necessary to satisfy this section is within E1.

### 5.3 Qualified releases and runtime authorization

Deployment and promotion must consume releases independently qualified according
to the repository release contract. For E1, qualification must bind the selected
immutable image identity to the applicable release eligibility evidence and be
established outside the consuming deployment/promotion authority. A manifest's
existence, a caller-supplied digest, a default "passed" field, or pullability alone
does not prove qualification. The consuming actor must not fabricate or rewrite
the evidence it relies on to authorize unrelated content.

Planning must identify the concrete qualifying evidence and trusted responsibility
using the existing release contract, adding only what is necessary to enforce
this bounded guarantee. Cryptographic attestation and complete provenance/history
redesign are not required. Missing qualification must fail closed rather than
accept the baseline evidence weakness as a permanent exception.

Deployment may introduce a revision, but security-sensitive runtime properties
must remain inside an approved, verifiable application contract. Coverage must
include image identity, task/execution role identity and placement, application
and probe commands/entrypoints, environment and secret injection, mounts/volumes,
additional containers, and equivalent execution or privilege-changing properties.
Permitted changes must be explicit; an unrecognized or unverifiable property
capable of altering this contract cannot silently become authorized.

This authorization must hold **before runtime execution**, including candidate
startup and non-serving tasks. A traffic gate that detects unauthorized content
only after it ran with DB secrets or KMS credentials is insufficient. Exact
revision/content identity must remain bound from authorization through activation;
registering another compatible definition must not bypass the contract.

The confidentiality requirement includes indirect access: a deployment/promotion
actor must not obtain runtime-secret, KMS or database authority by executable
substitution or role misplacement. Approved application code still needs its
existing DB and KMS behavior; E1 does not promise that an intentionally approved
malicious application or separately compromised runtime can never expose data.

### 5.4 Routing, capacity and recovery

Routing/capacity mutation must be confined to the approved deployment and recovery
responsibility, not generally available as an independent bypass. Normal new
revision promotion must preserve the completed readiness contract, including
exact candidate/cohort/digest evidence and failure before traffic switching.
Resource scoping alone is insufficient where the same actor could invoke a direct
mutation to avoid required authorization. Enforce supported restrictions at the
appropriate layers and identify any platform consistency limits explicitly.

Manifest/history rollback may register and deploy a revision only from a historical
release still eligible under the applicable runtime, release and readiness contract.
History membership does not exempt it from those requirements.

Emergency color flip may restore an already deployed color without rerunning the
new deployment-readiness gate. It must retain bounded service-stability and
healthy-target safety checks and introduce no new task revision or runtime
content. This intentional exception is not an alternate arbitrary-deployment path.

Cleanup and recovery must retain legitimate operations within their owned scope.
E1 does not require release-generation-bound scheduling, new concurrency semantics
or a partial-failure recovery redesign. It must still close authority paths through
these identities that violate responsibility or environment isolation.

### 5.5 Legacy authority and failure behavior

Combined app-CD is a migration remnant, not a desired steady-state capability.
Identify every remaining caller/fallback and the exact behavior it requires.
Remove or retire the capability if no required dependency remains. Any retention
must be justified by a demonstrated dependency and satisfy all E1 invariants;
dependency discovery is not permission to preserve broad combined or cross-env
authority indefinitely.

Missing dedicated credentials, identity mismatch, unavailable qualification or
ambiguous authorization must stop the affected privileged operation with useful
diagnostics. No silent fallback to legacy, administrative, cross-environment or
otherwise broader authority is acceptable. Secret values must not enter Terraform
state, outputs, logs, tests or committed artifacts.

## 6. Enforcement and planning boundary

E1 may require multiple enforcement layers. IAM must constrain what it can
reliably express: acquisition, actions/services, resource/environment scope,
role passing and supported conditions. Runtime content, role-field pairing,
release eligibility and deployment semantics may require a higher-level contract.
Such a contract must be an effective authorization boundary against the caller
described in section 2, not an optional check alongside unrestricted credentials.

Do not require unsupported IAM predicates. Verify material AWS semantics and
condition availability against authoritative documentation during planning.
Choose final policies, role layout, trust representation, protected enforcement
mechanism, validation schema, Terraform changes and test architecture in the
technical plan. This spec freezes none of those mechanisms.

## 7. Compatibility and non-goals

Preserve infrastructure planning, authorized apply/lifecycle, build/publication,
dev deployment, prod promotion, eligible manifest rollback, emergency color flip,
application DB/KMS behavior, ECS pull/log/secret bootstrap and legitimate bounded
recovery. Reallocated sensitive operations must remain available through their
explicitly authorized path. Do not make required workflows unusable to satisfy
negative security tests.

Preserve [E3 readiness](../deployment-readiness-promotion/spec.md), its current
implementation/knowledge capture, permanent `/health` liveness and the accepted
bounded observation-to-switch consistency model. E1 adds authority protection;
it does not reopen that feature or demand an atomic ECS/ALB transaction.

Unless necessary to close an E1 authority path, excluded work is:

- complete artifact provenance, cryptographic attestation or immutable deployment
  evidence redesign;
- E2 deployment/promotion concurrency, E4 partial-deployment recovery and
  release-bound delayed-cleanup redesign;
- broad NAT recovery redesign or general runtime managed-policy minimization;
- account separation/migration or wholesale environment ownership migration;
- SQL runtime/migration redesign, network/TLS redesign, database durability/restore.

Cost awareness, single-operator operation, SQL Server on EC2 and metadata/value
separation remain constraints. A necessary boundary correction must be justified
against an E1 invariant; it does not authorize the adjacent backlog wholesale.

## 8. Acceptance criteria

Each criterion requires traceable evidence for the resulting repository model.

| ID | Required observable outcome |
| --- | --- |
| AC1 | Starting with ordinary infrastructure authority, attempts to broaden a reachable workload principal and execute/arrange compute under it cannot exceed the approved authority ceiling. Evidence covers policy/trust changes, editable policy content, passing and mutable existing compute, not only self-mutation. |
| AC2 | A job/token authorized for each responsibility cannot acquire unrelated responsibility roles. Negative cases include CI/build to infra/admin and deploy/promote to infra/admin, alongside successful intended acquisitions. |
| AC3 | Dev cannot acquire prod authority or mutate prod resources/control/evidence, including through shared dependencies and recovery identities. The prod high-risk/dev-approval trust path and cross-env artifact writes are closed in the repository model. |
| AC4 | Deploy/promote cannot execute an arbitrary compatible task definition through direct registration/service APIs or alternate paths. Unauthorized runtime content is rejected before any candidate or other task executes it under workload authority. |
| AC5 | Substituting execution roles into task-role fields, exchanging environment/color role assignments contrary to the contract, or using equivalent role-placement abuse is rejected; legitimate role pairing succeeds. |
| AC6 | Eligible independently qualified release identities succeed; unqualified, mismatched, caller-substituted or unverifiable image/release identities fail before execution. Consumer-rewritable claims cannot alone authorize unrelated content. |
| AC7 | Ordinary lifecycle cannot administer protected OIDC, workload IAM/trust, KMS policies/grants, secret resource policies or artifact/storage controls to broaden authority. Necessary sensitive operations have a distinct authorized path. |
| AC8 | Direct and mediated routing/capacity operations are confined to approved deployment/recovery semantics. Normal promotion cannot bypass E3 readiness; unrelated resources, arbitrary routing changes and unauthorized runtime activation are denied. Necessary scale and forwarding transitions succeed. |
| AC9 | Manifest rollback rejects ineligible historical content and preserves applicable deployment/readiness checks. Emergency flip restores only an already deployed color, retains bounded stability/healthy-target checks, and cannot introduce new revision/content. |
| AC10 | Every legacy app-CD dependency/fallback is accounted for. Unneeded capability is retired; any retained dependency has concrete necessity evidence and no exemption from E1 boundaries. Missing dedicated authority never selects a broader fallback. |
| AC11 | Positive deterministic evidence covers every responsibility in section 4 and the required capabilities in section 7, including explicitly authorized administration. No capability is claimed preserved solely because a workflow remains present. |
| AC12 | Missing, malformed, contradictory or unverifiable authority/contract/qualification evidence fails closed before the affected privileged operation; diagnostics do not expose secret values. |
| AC13 | Deterministic tests and static evidence examine composed paths against actual resulting policies, trusts, callers and enforcement, including direct-API bypass attempts. Deliberate reintroduction of representative forbidden edges is detected; positive controls rule out deny-all success. |
| AC14 | Evidence maps each security-sensitive runtime property and equivalent injection path in section 5.3 to an enforced contract or a justified non-applicable case; unsupported/unverifiable security-sensitive content is not accepted by default. |
| AC15 | Readiness behavior, runtime DB/KMS behavior, secret metadata/value separation and ownership boundaries remain intact. Scope changes are limited to what E1 requires. |
| AC16 | Deterministic acceptance runs without AWS credentials or live resources and identifies the exact evaluated revision, checks actually executed and results. No live deployment is required or authorized by this specification. |

## 9. Required evidence and accepted limitations

Supply a responsibility/authority map for the resulting model, permission-to-caller
necessity mapping, and acceptance-to-evidence mapping. For each prohibited chain,
identify its starting principal/token, actions/resources, stopping control and
positive operational counterpart. Cover alternate role acquisition, policy grants,
mutable enforcement/compute, artifact writes, service activation and routing;
tests of helper behavior alone cannot establish AWS authorization isolation.

Use deterministic policy/trust analysis and behavioral evidence with explicitly
stated platform assumptions. Static assertions must not silently treat intended
resource names, tags or workflow conventions as enforced boundaries. Record
unresolved authorization semantics rather than asserting safety from an incomplete
model. A material unresolved bypass prevents the relevant criterion from passing.

Repository acceptance proves the checked-in model, not live deployment. It cannot
prove absence of manually attached policies, out-of-band credentials, external
SCPs or other account controls; nor can IAM prove the semantic truth of every
release claim. Shared accounts may remain. Required external trust/governance
configuration must be explicit and testable as an assumption, never reported as
verified without evidence. The checked-in model must enforce the guarantees when
those declared prerequisites hold; an unknown external control cannot be invented
to excuse a repository-granted bypass.

No live AWS access is required for deterministic acceptance. Any later live
verification needs separate authorization and must be reported separately from
offline evidence. Preserve [validation side-effect rules](../../terraform/docs/validation.md).

## 10. Review and next step

An independent reviewer must assess this specification directly, mapping every
acceptance criterion to evidence and evaluating effective authority rather than
policy appearance. Passing tests alone is insufficient if an allowed alternate
path defeats an invariant. Report repository-model acceptance separately from
unverified external configuration or live operational behavior.

The nine approved human decisions are requirements embodied in sections 3–5,
not open questions. Planning may choose mechanisms and resolve routine technical
details. Escalate only newly discovered contradictions that materially require a
different security or operational contract; do not weaken these guarantees to
fit a convenient policy design. The next deliverable is a separate technical
plan. This checkpoint creates no implementation and no `plan.md`.
