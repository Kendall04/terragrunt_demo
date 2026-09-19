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
against that spec. This bootstrap stops at durable knowledge and agent guidance.
Before selecting an improvement, review its current contract, constraints and
open questions together. Later specs should state outcomes, non-goals and
acceptance evidence independently of a technical plan. Update current-contract
docs only when implementation/evidence warrants it; retain superseded rationale
with explicit status. No first implementation spec has been created.

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
| B2 High delivery | Distinct deploy/rollback concurrency groups; cleanup not bound to release generation | Medium; mutation ownership; medium-high outage risk | Narrow concurrency contract may fit |
| B3 High readiness | ALB liveness gate; optional dependency readiness after switch | Medium; outage semantics; medium release-blocking risk | Good bounded candidate |
| B4 High recovery | Separate listener/rule/schedule/record operations permit partial success | Medium-large; rollback/concurrency contract; high risk | Isolate one failure scenario first |
| B5 High data durability | Termination-deleted root disk; no repository backup/restore; startup migrations under db_owner | Large overall; D4/D5 and recovery objectives; high data/schema risk | IMPORTANT, DEFERRED until deployed AWS near program end; no deep design now |
| B6 High conditional API security | Public writes and plaintext reads | Medium; domain/data policy first; high compatibility risk | Auth follows backend expansion |
| B7 High observability | ECS task-count namespace mismatch; NAT metrics not enabled; missing data non-breaching | Small-medium; metric/missing-data contract; low-medium noise risk | Strong first candidate: one alarm family |
| B8 Medium artifacts | Overwriteable S3 manifests; ECR retains only 15 images regardless of tag | Medium; identity/idempotency/rollback horizon; medium publishing/cost risk | Narrow publication contract may fit |
| B9 Medium provenance | Renderer defaults tests/build to passed without exact test-result binding | Medium; qualifying evidence; medium release-blocking risk | Good bounded candidate |
| B10 Medium backend | KMS input-size gap, pagination overflow/ties, error behavior | Small; input/error policy; low-medium compatibility risk | Strong candidate: text-size boundary |
| B11 Medium testing | CD fixture tests not run by workflows; shell checks omit CD helpers; no Lambda unit tests | Small for wiring tests; trigger policy; low risk | Strong first candidate |
| B12 Medium IaC CI | PR plans target dev; prod high-risk CD unsupported; reviewed plan not saved for apply | Medium; prod/governance model; medium-high risk | One routing contract may fit |
| B13 Medium NAT | Independent recovery, no DLQ/forwarding probe; ignored AMI updates | Medium; NAT/patch policy; medium-high egress risk | Offline Lambda behavior first; live recovery later |
| B14 Medium reproducibility/DX | Partial locks, moving image/tool/action inputs, no explicit container user | Medium; update/toolchain policy; medium compatibility risk | Narrow one contract |
| B15 Medium operations/cost | No verified alerts, restore drills, SLOs, business probes, tracing or budgets | Medium; explicit expectations; variable runtime/cost risk | Define useful evidence before tooling |
| B16 Medium knowledge | Historical docs/code comments remain non-authoritative; maintain current docs as behavior evolves | Small ongoing; low risk | Continuing maintenance |

Evidence: [IAM](../infra/shared/modules/iam_github),
[deploy script](../../scripts/ecs-blue-green-deploy.sh),
[cleanup](../infra/apps/fargate/lambda/scale_down_old_color.py),
[ECS alarm](../infra/apps/fargate/modules/ecs_service/alarm_ecs_service.tf),
[NAT ASGs](../infra/global/modules/nat/autoscaling_group.tf),
[ECR](../infra/shared/modules/ecr/main.tf),
[manifest renderer](../../scripts/render-release-manifest.sh),
[CI](../../.github/workflows/ci.yml), [fixtures](../../.github/scripts/cd/tests).

Managed NAT, canaries and more services are alternatives, not approved requirements.
Historical RDS recommendations are superseded by D4. No first spec is selected.
