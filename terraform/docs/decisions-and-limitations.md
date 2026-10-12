# Decisions, limitations and improvement register

Authoritative owner reconciliation: 2026-09-18. Implementation evidence lives in
[architecture](architecture.md), [delivery](deployment.md),
[operations](bootstrap.md) and [security](secrets-strategy.md).
This register is not an implementation plan or first improvement spec.

## Knowledge rules

- **CURRENT CONTRACT:** demonstrable checked-in behavior, with implementation evidence.
- **ACCEPTED DECISION / LIMITATION:** explicit owner constraint or deliberate tradeoff.
- **TARGET / INTENDED EVOLUTION:** desired, not yet implemented.
- **UNRESOLVED:** further design, experiment or owner choice required.
- **HISTORICAL / SUPERSEDED:** retained reasoning, not current instructions.

Implementation determines present behavior; owner decisions determine constraints
and intent. Record both when they differ. A configured workflow, an intended
control and verified external enforcement are distinct evidence.

## Knowledge-driven change workflow

Baseline → owner reconciliation → durable knowledge → agent map → selection of
one improvement → durable spec → technical planning → implementation → review
against that spec → selective post-review knowledge capture.
Before selecting an improvement, review its current contract, constraints and
open questions together. Later specs should state outcomes, non-goals and
acceptance evidence independently of a technical plan. Update current-contract
docs only when implementation/evidence warrants it; retain superseded rationale
with explicit status. The first improvement, [CD safety test enforcement](../../specs/cd-test-enforcement/spec.md),
has passed independent review of all 12 acceptance criteria. Its
[review identities and evidence](validation.md#review-and-evidence-boundary)
close the repository-side CD fixture enforcement gap, not external governance.

## Accepted decisions and constraints

| ID | Decision | Consequence |
| --- | --- | --- |
| D1 | Cost awareness is first-class | Choose the least expensive architecture meeting explicit requirements; document cost, availability, reliability, security, complexity and operational burden |
| D2 | Secret values MUST NOT enter Terraform state | Retain metadata/value separation; next deployment must verify it with evidence |
| D3 | Single-operator system | Use operator/repository owner terminology and useful automation; no fictional teams |
| D4 | SQL Server stays on EC2 for cost reasons | RDS is not the default solution; durability is unresolved, not permanently waived |
| D5 | Durability learning requires real infrastructure | Defer implementation and deep design until near program end after redeployment; safely test persistence, replacement/destruction, backup/restore and accidental deletion |
| D6 | Meaningful backend/domain precedes auth design | Do not bolt on identity for appearance; reconsider auth with meaningful domain semantics |

Owner-confirmed status: no AWS infrastructure currently exists. Earlier resources
were destroyed to avoid unused costs. Historical state likely contained secrets,
but that state was destroyed; no forensics/cleanup is required for deleted state.
Future deployment is reconstruction. Treat live state as ephemeral unless captured
later through verified evidence. This is dated owner evidence, not an AWS audit.

## Targets — not current guarantees

- **Production MUST NOT depend operationally on development-owned resources.**
  Existing dev/shared ownership violates this target; migration mechanism is open.
- Serious least-privilege IAM and real environment authority boundaries.
- Protected main, PR flow, required checks and appropriate deployment approvals.
  Actual GitHub settings remain unverified.
- Robust production blue/green; development may use a simpler cheaper model.
- Backend expansion beyond the trivial text demo.
- Reliable, experimentally verified rollback covering retention, history, DB
  compatibility, traffic switching and evidence.
- Strict provenance: claimed tests/builds/validation/deployment verification bind
  to actual evidence for the exact source/artifact, not optimistic defaults.
- Safe operation by one engineer through automation and observable outcomes.

## Unresolved decisions

| Area | Open choice |
| --- | --- |
| Environments | Isolation in one account vs separate accounts/AWS Organizations; ownership mechanism |
| Backend/auth | Domain, public data semantics, identity and authorization after expansion |
| Rollback | Success/failure contract, retention horizon, history, concurrency, schema compatibility and proof |
| Network security | Egress hardening and internal TLS value; HTTP is not required for blue/green |
| SQL security | Certificate validation and runtime/migration privilege separation |
| Durability | Persistence, backup/restore, deletion safeguards and recovery objectives under D4/D5 |
| Operations | Capacity, recovery time/data loss, alerts, patching and cost targets |
| Governance | External branch/environment protections and required checks |

## Candidate backlog

Priority describes engineering impact; sequencing is separate. Deferred does not
mean low importance. Scope/dependencies below do not authorize implementation.

| ID / priority / domain | Problem/evidence | Scope, dependencies and change risk | Sequencing / first-spec fit |
| --- | --- | --- | --- |
| B1 High IAM | Broad infrastructure APIs; shared normal/high-risk policy; prod-created high-risk role trusts dev-infra-approval | Medium-large; environment authority decision; high lockout/apply risk | Clarify boundary first |
| B2 / E2 High delivery — repository implementation; E2-R partial | [Environment mutation arbitration](e2-environment-mutation.md) coordinates protected delivery/recovery/lifecycle and generation-bound cleanup; [E2-R](e2r-owner-recovery.md) adds read-only interrupted-owner diagnosis | No timeout takeover; head CAS cannot cancel checked/in-flight calls; exact executor termination and remote quiescence cannot currently be verified, so administrative recovery stays BLOCKED | Provider-free repository evidence; live installation/termination/effect settlement remain unverified; E4 compensation remains deferred |
| B3 High readiness — completed | Per-task one-shot readiness gate precedes promotion; the bounded ECS/ALB observation model and historical rather than continuous readiness are explicit | Preserve exact cohort/digest/target evidence, bounded failure, unchanged `/health`, fail-closed external evidence handling and immediate final revalidation | [Durable spec](../../specs/deployment-readiness-promotion/spec.md), [plan](../../specs/deployment-readiness-promotion/plan.md) and [reviewed evidence](validation.md#deployment-readiness-promotion--reviewed-evidence) complete the feature; optional hardening below is separate |
| B4 / E4 High recovery — PARTIALLY_RESOLVED | [Bounded same-invocation continuation](e4-post-switch-recovery.md) reconciles switch evidence-persistence failure with current readbacks and original E2 grant | No attempted-stage resend, compensation, interrupted-owner takeover or new approval model; schedule/index/orphan failures remain | Deterministic repository evidence; live recovery remains unverified |
| B5 High data durability | Termination-deleted root disk; no repository backup/restore; startup migrations under db_owner | Large overall; D4/D5 and recovery objectives; high data/schema risk | IMPORTANT, DEFERRED until deployed AWS near program end; no deep design now |
| B6 High conditional API security | Public writes and plaintext reads | Medium; domain/data policy first; high compatibility risk | Auth follows backend expansion |
| B7 High observability — configuration corrected | [E7](e7-cloudwatch-alarms.md) fixes active dev/prod ECS namespace, NAT collection and gauge missing-data behavior; real metric/notification delivery remains unverified | Preserve bounded dimensions, protected ownership and sparse-error policy; no observability redesign | Provider-free repository evidence; live AWS validation remains separate |
| B8 / E8 Medium artifacts — PARTIALLY_RESOLVED | E1 already protects exact immutable manifest evidence; [E8](e8-rollback-image-retention.md) removes automatic expiration from three protected application repositories and checks exact image availability | WP3 publishes untagged images, so untagged/count cleanup is unsafe; retained ECR storage is unbounded and no cleanup authority is added | Owner horizon/budget and evidence-driven cleanup remain unresolved; live retention/rollback is unverified |
| B9 Medium provenance | Renderer defaults tests/build to passed without exact test-result binding | Medium; qualifying evidence; medium release-blocking risk | Good bounded candidate |
| B10 Medium backend — partially completed | Direct-KMS plaintext-size boundary completed with REVIEW_PASS; pagination offset overflow/ties corrected with local provider/query and HTTP tests; dependency error behavior remains unresolved | Preserve the reviewed [application/data contract](architecture.md#current-contract--application-and-data) and [validation coverage](validation.md#existing-test-meaning-and-gaps); larger-payload support remains a separate future design decision | [Text-size boundary](../../specs/kms-text-boundary/spec.md) complete; pagination does not snapshot concurrent writes; dependency errors remain separate work |
| B11 Medium testing — repository CI selection completed | CD fixture enforcement and E1 acceptance selection cover protected implementation/contracts/TARGET wiring; CD shell helpers now receive syntax/hygiene checks | Preserve [E11 selection/result boundaries](validation.md#current-contract--e11-ci-selection-and-enforcement) and existing app/readiness/CD Safety suites; live behavior remains separate | Required-status-check enforcement remains external and unconfigured/unverified |
| B12 Medium IaC CI | PR plans target dev; prod high-risk CD unsupported; reviewed plan not saved for apply | Medium; prod/governance model; medium-high risk | One routing contract may fit |
| B13 Medium NAT — bounded implementation | [E13](e13-nat-reliability.md) adds separate delivery/execution failure queues, bounded retries, exact bootstrap/network evidence and administrator AMI replacement approval; live forwarding remains unverified | Preserve three protected duties, pinned launch identity and single-AZ maintenance ownership; no new failover system | Offline controller/Terraform evidence; genuine AMI rollout, forwarding and notification proof deferred |
| B14 Medium reproducibility/DX - PARTIALLY_RESOLVED | [E14-A](e14-container-hardening.md) retains verified .NET 8 image bases/non-root UID 1654. [E14-B](e14b-toolchain-reproducibility.md) verifies standalone CI tool hashes, pins CI action commits/host SDK and closes security-root lock coverage; all 14 TARGET locks remain unchanged. Runner/jq, BuildKit, NuGet, protected scope action and live installation evidence remain | Medium; deliberate reviewed pin/provider/base update procedure; medium compatibility risk | Bounded application and infrastructure/CI inputs; overall reproducibility remains partial |
| B15 Medium operations/cost | No verified alerts, restore drills, SLOs, business probes, tracing or budgets | Medium; explicit expectations; variable runtime/cost risk | Define useful evidence before tooling |
| B16 Medium knowledge | Historical docs/code comments remain non-authoritative; maintain current docs as behavior evolves | Small ongoing; low risk | Continuing maintenance |

### Optional readiness hardening — outside completed B3

These non-blocking improvements do not reopen the completed readiness feature:

- Canonicalize container ordering in task fingerprints so semantically equivalent
  reordered observations do not cause a false rejection.
- Expand post-switch fault-injection coverage for scheduling and deployment
  output/history failure paths.

Evidence: [IAM](../infra/security/modules/request_identities),
[deploy script](../../scripts/ecs-blue-green-deploy.sh),
[cleanup](../infra/apps/fargate/lambda/scale_down_old_color.py),
[ECS alarm](../modules/target/dev/apps/modules/ecs_service/alarm_ecs_service.tf),
[NAT ASGs](../modules/target/dev/global/wp5-nat.tf.json),
[ECR](../../ci/authority/retired/terraform/infra/shared/modules/ecr/main.tf.txt),
[manifest renderer](../../scripts/render-release-manifest.sh),
[CI](../../.github/workflows/ci.yml), [fixtures](../../.github/scripts/cd/tests).

Managed NAT, canaries and more services are alternatives, not approved requirements.
Historical RDS recommendations are superseded by D4. Remaining backlog items are
not selected or authorized by completion of the CD safety spec.

## E1 WP7 repository disposition

[Final E1 acceptance](e1-final-acceptance.md) retires broad legacy GitHub roles,
default-sub trust/PassRole/fallback paths and old roots/actions/wrappers. Neutral
protected authority replaces dev-owned security dependencies; the wider production
operational-independence target is still distinct. All external identities and
WP4D/WP5 compute stay inactive. No deployment, installation, migration or external
governance is claimed. Existing durability, concurrency, compensation, observability
and reproducibility backlog remains outside E1; no further E1 work package is added.

## E15 — ephemeral DEV lifecycle (partial repository readiness)

The owner requests an on-demand DEV lab with controlled teardown and minimal
residual cost. [E15](e15-ephemeral-lifecycle.md) recovers existing WP5 per-layer
teardown, adds an offline preparation/residual interface and budget draft, and
requires complete empty managed-state plus exact ECS quiescence readback before
teardown SUCCESS. No AWS operation or activation occurred. Shared/secrets,
security-root, backend/state/evidence/ECR remain retained; storage is not bounded
and DOWN is not promised to cost zero.

Owner decisions remain: monthly budget/alerts, log preservation,
active-color quiescence authority, exact destroy-preview approval binding, bounded
admin NAT/executor settlement and the existing E13/shared SNS identity mismatch.
Interrupted E2/E4 owners cannot be taken over. E5 durability is not selected here;
no automatic data/image cleanup or budget-driven shutdown is authorized.

## E15-B — explicit disposable DEV data; DOWN still partial

The owner approves permanent loss of SQL Server data exclusively belonging to
terragrunt_demo DEV during DOWN, with distinct current resource-destruction and
SQL-loss confirmations. No backup or snapshot is required. This excludes PROD,
shared data, other projects, state and protected reconstruction/audit evidence.
[The E15-B contract](e15b-dev-down.md) implements additional DEV data-layer WP5
consent, exact same-invocation saved-plan integrity and fresh ECS observations,
and local review/drafting without new IAM or execution authority. Full DOWN stays
denied pending ECS mutation-source closure, NAT executor/issued-effect settlement
and protected exact reviewed-plan approval consumption. E2-R/E4 uncertainty is
never bypassed. Budget/alert values and recipients remain owner decisions.

## E15-C — exact reviewed destroy approval (partial)

[E15-C](e15c-exact-destroy-approval.md) adds exact E15-B evidence/administrative
channel validation, S3 conditional single-use decision and attempted substages in
WP5's journal, and saved-artifact integration/final checks. Generic DEV runtime
destroy now rejects an absent installed exact-plan handoff. No concrete trusted
administrative/artifact/state/quiescence adapter is installed; approval-prefix
access and cross-invocation preparation integration need narrow accepted authority
before activation. No IAM/PassRole or new CLI authority is granted. ECS/NAT closure,
E2-R/E4 uncertainty and genuine live proof remain independent DOWN blockers.
