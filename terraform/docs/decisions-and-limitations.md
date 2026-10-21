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
| B5 High durability - PARTIALLY_RESOLVED | Native and real S3/KMS component restore plus October 21 EC2-role manual/two-hourly backups passed; runtime and residual network retired. Cross-AZ SQL/API recovery and measured RPO/RTO remain unproven | D4 remains: SQL stays EC2, its root disk is disposable and migrations use db_owner; preserve original keys, secrets and backups. The [isolated recovery packet](../../operations/sql-backup/recovery/RUNBOOK.md) is local preparation only, not an AWS authorization | Fresh synthetic marker/backup, different-AZ restore/CHECKDB, real KMS decrypt and isolated API read/write remain the next bounded proof; warm-target/component timing is distinct from full ECS recovery |
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

## E15-D — administrative handoff (partial)

[E15-D](e15d-administrative-handoff.md) adds concrete SDK session verification,
private exact-version artifact publication/readback and immutable operation-scoped
approval selection, wired to WP5/E15-C. Missing pinned administrative installation
blocks; no self-declared identity or fixture activates authority. Required narrow
storage reads/denies and the existing-role/preparation route need accepted protected
installation; no IAM/trust/PassRole or compute activation is added. ECS/NAT
settlement and E2-R/E4 uncertainty still deny complete DOWN. Live identity/S3/IAM/
Terraform proof remains unverified; budget/alert decisions remain pending.

## E15-F — NAT quiescence (partial)

[E15-F](e15f-nat-quiescence.md) implements a dormant exact-DEV EC2 admission fence
and durable original-WP5/E2 UNKNOWN diagnostics. Checked or dispatched EC2 calls,
independent ASG service actions and async retries lack exhaustive finality evidence.
Networking teardown stays blocked pending an owner-approved settlement mechanism,
protected installation and live validation; no new IAM/activation or force unlock.

## E15-E/F combined DEV quiescence boundary

[Combined contract and remaining decisions](e15ef-combined-quiescence.md) wires
separate ECS/NAT guards into protected WP5/E15-D, with immutable UNKNOWN evidence
and the original E2 hold. Whole-operation ownership/stage order, terminal ECS
cluster handoff, installed authenticated adapters and issued-effect settlement
remain unavailable. Complete DOWN stays denied; no IAM or activation is added.

## E15-G operational component follow-up

[E15-G](e15g-operational-teardown.md) adds original-E2-owner composition, bounded
ECS drain, sealed terminal cohort handoff and residual completion checks.
Complete installed DOWN remains PARTIALLY_READY and denied: NAT executor/effect
closure, authentic ECS closure, whole-operation preparation and exhaustive
residual installation remain required. No IAM/activation or live AWS evidence.


## E15-H trusted NAT source increment

[E15-H](e15h-nat-trusted-closure.md) selects one bounded CAS admission coordinator,
adds cooperative E13 dispatch/seal accounting and native ASG read contracts under
the original E15-G owner. Installed authentication, callable-version coverage and
remote finality remain unproved; networking and complete DOWN still fail closed.
No IAM policy, active binding or AWS resource is installed by this increment.

## Original complete DEV lifecycle (2026-10-13)

The owner restored the original full architecture. E15-S was explicitly reverted;
E15-S2 is not integrated. The [first-session procedure](original-full-lifecycle.md)
records the complete resource/state graph, existing WP5/WP6 commands, thin DEV
entry and separate UP installation versus DOWN finality blockers. No reduced
lab, authority bypass, activation or AWS operation is introduced.

## E16 supervised original DEV mode (2026-10-13)

The [E16 current operator contract](e16-practical-dev-lifecycle.md) implements
per-layer original DEV saved-plan review/apply and observed shutdown under an
explicitly authorized, exclusive existing-human state-writer transfer. Default
mode remains inert; PROD/shared/security-root ownership is retained. Existing
WP3/WP4 delivery and E13 recovery remain. E15-G/H advanced finality contracts are
not weakened or activated. Source readiness is distinct from genuine installation
and live AWS validation; no AWS operations occurred.


## Second full DEV cycle (2026-10-14 local)

The owner authorized the second complete original DEV UP after reviewing its
scope and estimated running costs. The [live record](second-real-dev-cycle.md)
separates verified reconstruction/SQL/KMS functionality from future CI/CD,
blue/green and NAT failover experiments. Leave this successful deployment running
for those exercises; further DOWN still needs teardown and independent SQL-loss
consent. No new architecture, PROD/shared authority or automatic cleanup is added.

## V2 owner decision and local .NET 10 milestone (2026-10-16)

The owner requires .NET 10 LTS and the original two-AZ architecture, with simple
single-operator execution rather than a reduced one-AZ/public-IP lab. The
[local migration](validation.md#net-10-lts-local-migration---2026-10-16) updates
SDK/targets/Microsoft dependencies and immutable container bases, preserving
behavior and SQL schema. V1 AWS evidence remains historical; this source has not
been deployed. Terraform/Terragrunt selections, providers, IAM/OIDC and cloud
authority are unchanged. No new clone/worktree was created; the existing linked
worktree moved to CodexDrop. Backups/restore, PKI and Sentinel remain subsequent
increments, not implemented by this runtime milestone. Reviews should close on
material correctness/security/behavior evidence without reopening accepted
observational boundaries for minor refinements.

## V2 first local SQL backup/restore milestone (2026-10-16)

The owner authorized local design/implementation and subsequently accepted the
Microsoft SQL Server 2022 Express EULA for an isolated synthetic Docker test.
This reopens the earlier D5 deferral only for this bounded increment; it does not
authorize AWS/IAM changes, deployment, data loss, publication or an automatic DOWN.
[The runbook](../../operations/sql-backup/README.md) defines finite acceptance and
[validation](validation.md#sql-backuprestore-local-increment---2026-10-16) records
native SQL versus mocked storage. Two AZ, SQL on EC2, E2/E13 and lifecycle remain.
The proposed hourly/two-day-current/two-day-noncurrent/two-hour-stale defaults are
uninstalled and unaccepted. RPO/RTO are undecided/unmeasured. Restored ciphertext
still needs the original text KMS key and a genuine application/decryption trial.
PKI, Sentinel, UI and unrelated hardening remain later increments.

## Bounded S3/KMS component session authorization - 2026-10-16

The owner authorized the minimal synthetic component drill (one backup bucket,
one dedicated CMK, two scoped temporary roles, local Express) under the four-hour
window and subsequently confirmed USD 10 total including the first month of
retained resources; the minimum-session estimate remains approximately USD 1.26.
This does not authorize full
DEV activation, changes to existing permissions/text-key policy, or unattended
scheduling. Additional infrastructure needs its concrete impact reported first.
The first Linux STS preflight was BLOCKED_BEFORE_CREATION because cnp-cert-dev
does not exist on codex-vm; no AWS resource was created. See the
[preflight evidence and resume condition](validation.md#approved-s3kms-component-drill-preflight---2026-10-16).
The existing cross-AZ/full-application drill proposal remains a separate scope.

## Bounded cloud component accepted - 2026-10-16

The approved USD-10/four-hour synthetic session passed real S3/SSE-KMS/versioned
download/native restore/text-key decrypt and minimum-role negative cases via
Windows AWS plus Linux SQL. The earlier missing-Linux-profile blocker was
resolved by that supported execution split without credential handoff. The
[qualification and retained inventory](validation.md#sql-s3kms-component-qualification---2026-10-16)
distinguish actual checks, authored freshness fixtures and untested deployment.
One private versioned bucket and one backup CMK remain; temporary roles, key-use
bindings and local runtime/data were retired. No existing text-key policy changed.
Hourly/2+2-day/two-hour lab settings are accepted; RPO/RTO remain unmeasured,
no scheduler is installed and cross-AZ/full-app qualification remains separate.

## V2 local SQL service increment (2026-10-16)

The owner authorized implementation, KDD, a local commit and isolated codex-vm SSH
fixtures for the backup service. This scope includes hourly inert units,
self-contained packaging, fresh-remote-proof deletion of owned older .bak only,
and local inhibit/wait/resume. It authorizes no AWS call/deployment, publication,
permanent service/credential/security installation or change to existing resources.
The [runbook](../../operations/sql-backup/README.md#local-service-increment---2026-10-16)
states the exact install impact and the limits of local fencing. SQL minimum
verifier CREATE DATABASE in master was proven in disposable Express without
sysadmin/dbcreator/source SELECT; restore permissions remain a separate boundary.

Finite acceptance closed with local component/native tests, actual package smoke
and static units; two accelerated wrapper activations do not claim a running
systemd timer or co-located EC2/AWS integration. Failure files remain until operator
review; disk reserve can stop further backups. No additional HA/production stack,
Cognito, Daybreak review dependency or cosmetic review loop is introduced. EC2
installation and full-app/cross-AZ recovery are subsequent explicitly scoped work.

## V2 EC2 backup installation preparation (2026-10-16)

Following b036141, the owner asked to continue the ECS track. Authorization covers
implementable scripts/docs, offline validation and read-only AWS account
341936017254/us-east-1 through cnp-cert-dev. Security/network/SQL credential/host
installation and runtime apply remain pending a concrete grouped approval.
[The review packet](../../operations/sql-backup/EC2-INSTALL-REVIEW.md) reuses the
retained bucket/CMK/SQL role with a new operational prefix and private root-only
credentials on encrypted EBS, avoiding new paid secrets or broad permissions.
This is a proposed lab credential-storage decision, not an installed policy.

Readbacks found no original DEV VPC/runtime/SSM host or endpoint; default VPC is
not a substitute. Original global/data saved plans, separately administered
NAT/E13 setup and actual network/host IDs are prerequisites, preserving the two-AZ
architecture. No ordinary/protected Terraform source grammar is extended by a
generated review candidate. Finite next acceptance is one complete manual EC2-role
backup plus two real hourly timer fires and safe inhibition/retirement within four
hours; no final ceremonial backup for disposable synthetic data. The prior USD-10
ECS envelope is shared, not renewed; planned first-month baseline plus retained
component plus session is approximately USD 4.31 before tax, rounded USD 5 with
stated assumptions, not a remaining-balance or automatic-spending-cap claim.

## EC2 grouped approval and execution pause (2026-10-16)

The owner approved the exact EC2 backup installation, one manual plus two hourly
runs, and disposable runtime/data retirement within four hours, using the prior
shared USD-10 budget. The [execution preflight](validation.md#approved-ec2-backup-execution-preflight---2026-10-16)
initialized E16 but stopped before runtime creation: the fresh network plan could
not read native Terraform state, and existing E16 DOWN requires a new owner
disposition for the preserved historical SDC UNKNOWN. The previous final-DOWN-only
exception is not reusable. No evidence, control or IAM permission was weakened;
approval did not silently include this previously undisclosed risk disposition.
An attempted sensitive diagnostic was rejected by automatic review and not run.
Human sanitized diagnosis or explicit bounded diagnostic approval is needed.
The four-hour billable-runtime window has not started; there is nothing new to
retire. Preserve the installation approval and pause only for these material
boundaries, without a cosmetic review loop or ceremonial synthetic final backup.

## New bounded historical-risk disposition and local privacy review (2026-10-17)

Following the explanation of both ECS blockers, the owner requested continuing,
and the delegation explicitly instructed recording a new disposition for the
current backup session. The preserved SDC result remains UNKNOWN; the new local
record accepts only that historical-risk boundary, never deletion or apply.
It does not copy the prior final-DOWN permission or weaken any other E16 guard.
Actual execution/configuration needs exact technical binding and live checks.

The second tool rejection remains a separate boundary. Only local code changes
were prepared to discard diagnostics end-to-end and expose metadata-only plan
output on the same E16 route. [Human review of the concrete diff](../../operations/sql-backup/LOCAL-PLAN-REVIEW.md)
is required before any further init/plan attempt. No runtime, new authentication,
cloud mutation or full installation reapproval is introduced by this local step.


## EC2 role backup acceptance and partial retirement (2026-10-21)

A new USD-3/four-hour owner-approved trial passed one manual and two real hourly
EC2-role backups. Normal data retirement completed; global retirement stopped on
missing VPC/subnet companion-resource IAM authorization, leaving 13 network objects.
No denied operation was retried or bypassed. The owner deferred the new grant;
the trial was aborted with runtime absent, original bindings restored, temporary
permissions removed, controls inhibited and workflows disabled. Retained storage,
keys, secrets and backend still cost money. [The dated record](e16-ec2-backup-trial-20261021.md)
preserves source, actual timings, bootstrap recovery, state, residues and limits.
The old USD-10 budget and failed plans are not reusable. Only local offline
preflight regression work was authorized afterward, without policy application,
new expenses or changes to E16 controls/limits.
