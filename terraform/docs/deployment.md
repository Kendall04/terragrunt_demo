# Deployment and release contract

Read [architecture](architecture.md) for ownership and [validation](validation.md)
for command effects. This describes checked-in behavior, not proven deployment
results. The owner reconciliation on 2026-09-18 preceded all AWS resources.
The [first real DEV deployment record](first-real-dev-deployment.md) distinguishes
authenticated runtime evidence from uninstalled protected GitHub/WP3/WP4 delivery.
The [current real CI/CD preflight](final-github-actions-cicd.md) records the public
GitHub/history audit, authentic OIDC-provider installation and the still-pending
publication, protected WP3/WP4 installation and actual Actions execution.

[E4 recovery/runbook](e4-post-switch-recovery.md) adds one bounded same-invocation
continuation after a listener switch with failed evidence persistence. Fresh
operation-linked readback and current authorization are mandatory; blocked
partial deployments remain UNCERTAIN with E2 ownership retained. Later publication
failures and interrupted workers still require separately authorized diagnosis.
[E2-R](e2r-owner-recovery.md) adds read-only ownership diagnostics while retaining
ACTIVE holds. Administrative release remains blocked without verified exact
executor termination and settlement of all potentially issued effects.

## CURRENT CONTRACT — final E1 protected workflows

[E15 preparation/runbook](e15-ephemeral-lifecycle.md) reuses WP5/WP6 per-layer
lifecycle and WP3/WP4 delivery. It adds no direct execution path; complete DEV
shutdown remains partial pending approved quiescence/preview/settlement gates.

[E8 retention](e8-rollback-image-retention.md) removes automatic application-image
expiration and tightens exact account/repository/digest availability reads used
by rollback/restoration. Current eligibility and independent prod approval remain
mandatory; no bounded historical horizon or live retention proof is claimed.

[WP6 protected workflows](e1-protected-workflows.md) connects the accepted
WP2-WP5 contracts through eleven dedicated reusable entries and exact OIDC
request identities. The owner-authorized first Actions trial permits source
approval records only for `release` and `deploy-dev`, account `341936017254`,
region `us-east-1`, exact ref `refs/heads/codex/final-github-actions-cicd`.
Each still requires the existing separately authenticated G1–G9 observation,
source hashes, immutable reusable-workflow SHA and observed numeric gateway
version. The remaining nine entries retain their inactive source contract.
Source approval is distinct from IAM installation, an STS exchange, qualification
and deployment; none of those is proved by a source record alone.

| Entry point | Protected request path |
| --- | --- |
| ci.yml / ci-terragrunt.yml | Static PR/source diagnostics without AWS credentials |
| ci-terragrunt-plan.yml / ci-terragrunt-manual.yml | Approved immutable-source read-only plan-dev / plan-prod |
| cd.yml / cd-scope.yml | Existing conservative classification; ordered lifecycle requests; read-only infra-ready before dev release/delivery |
| cd-terragrunt.yml | Fixed ordinary or approved high-risk dev/prod lifecycle gateway |
| release-build.yml | Approved develop source; finalizer-qualified release ID |
| cd-demo-api.yml / deploy-dev.yml | Dev qualified delivery through deploy-dev |
| promote-prod.yml | Independent manual main promotion of an existing qualified release |
| rollback-manifest.yml | Same environment's normal gateway, protected history UUID |
| cd-rollback.yml | Separate manual existing-content emergency gateway |
| ci-cd-safety.yml | Existing independent no-AWS safety validation/check identity |

All mutation paths use protected endpoint requests. Callers cannot choose an IAM
role, resource ARN, backend, image, task definition, approval override or security
configuration. Dedicated entries hardcode their environment; protected source,
installation and G1-G9 observations gate immutable caller pins. Public operation
inputs and sanitized completion are documented in the WP6 contract. Dev success
never grants prod credentials or substitutes for independent production approval.

The existing scope classifier remains conservative: root/unmapped changes block
application delivery. High-risk lifecycle needs the exact WP5 operation-ID/hash
approval as well as its GitHub environment approval. Required GitHub checks,
branch/ruleset/reviewer restrictions and bypass exceptions remain externally
unverified. No merge-queue or live governance enforcement is claimed.

Legacy role-secret acquisition, app-CD/TG_CD fallback and direct workflow mutation
are removed. WP7 retires the frozen broad Terraform roles/live roots and composite
actions. Local bootstrap/deploy wrappers and the standalone blue/green main reject
before AWS. Legitimate operations use the protected endpoints or explicit separately
authenticated security administration. See [final acceptance](e1-final-acceptance.md).

[E11 CI selection and enforcement](validation.md#current-contract--e11-ci-selection-and-enforcement)
starts validation on PRs and branch pushes, selects gates from complete event
history and requires actual selected job success. CD Safety covers PRs and
develop/main pushes independently. External required-check settings remain
unverified. No CI result grants deployment authority.

## Historical helper observations — not operational authority

The details below preserve accepted E3 behavior and historical artifact semantics.
They do not authorize the retired standalone deploy path or optimistic quality
defaults. The operational contracts are [qualified release](e1-internal-release.md),
[normal delivery](e1-wp4b-normal-delivery.md), [bounded recovery](e1-wp4c-bounded-recovery.md)
and [lifecycle](e1-protected-environment-lifecycle.md). Current eligibility, closed
runtime/role authorization before startup, protected dev activation and independent
prod approval are mandatory. No historical manifest alone qualifies content.

## Historical helper artifact and traffic lifecycle

1. Release build publishes an ECR image and resolves its immutable digest.
2. The manifest records source SHA/run identity, image fields and quality fields.
3. S3 indexes address manifests by digest, commit/run and develop candidate.
4. Dev/prod/manifest rollback consume an existing image digest.
5. The common deployment script discovers active color from the ALB, requires the
   candidate rule to point at the other color, stops that inactive service,
   registers a rendered task definition and starts the requested replicas.
6. Each task's non-essential one-shot probe polls its application's loopback
   `/ready` endpoint under finite request/response/total bounds and requires three
   consecutive healthy responses. The controller freezes the full cohort and
   repeatedly validates exact service, revision, digest, container, ENI and healthy
   target identities. Missing, stale, replaced, ambiguous or inconsistent evidence
   fails closed. A final complete revalidation occurs immediately before switching.
7. It changes the listener default action, then the candidate action, and schedules
   delayed scale-down. Those operations are not atomic.
8. Workflow smoke checks and deployment/current/history records follow the switch.

The readiness controller uses existing ListTasks/DescribeTasks, service, listener,
rule and target-health reads; it adds no ECS Exec, secret read, public candidate
route or target-group mutation. It exhausts AWS CLI pagination and batches task
descriptions at 100. Evidence is invocation-local and bounded by the scale-up
attempt deadline. Older image digests without the packaged `readiness-probe`
command fail before promotion and are not rebuilt or downgraded to liveness.

Startup observations retain service/deployment and task identities even before
the cohort is complete. PROVISIONING/PENDING/ACTIVATING may progress to RUNNING;
runtime metadata may fill in before probe completion. Previously populated
identity must remain unchanged, lifecycle cannot regress, and a stopped probe
requires complete task/container/network identity. Missing metadata never grants
promotion and cannot extend the original deadline.

Listener and candidate-rule reads use one forwarding normalizer: a direct ARN,
a single positive-weight target, or agreeing copies of both resolve to one target.
Conflicting, multi-target and unsupported shapes fail closed. Every service read,
including both reads in final revalidation, validates the complete response and
the retained deployment identity.

Captured authorization JSON is checked as exactly one object with the expected
endpoint envelope before filtering or semantic interpretation. The shared
`scripts/aws-response-boundary.sh` validator covers routing discovery and gate
observations (definitions, services, task lists and target health), plus preparatory
service/definition reads. DescribeTasks retains its independent per-batch boundary
before aggregation. A malformed prefix, suffix or additional JSON document cannot
be discarded to salvage an otherwise acceptable observation.

Each DescribeTasks batch also validates the nested evidence before aggregation:
attachments, attachment details, containers and container network interfaces must
be arrays of correctly shaped objects when present. Missing collections and
runtime fields may populate during startup; explicit null, wrong types and
malformed entries are rejected even when a later filter would ignore them.
Completion still requires the existing full runtime/network identity. This same
boundary applies to startup, complete observations and final revalidation.

Registered definitions must retain the image entrypoint (entryPoint absent), the
normal application command (command absent), and the exact probe command
`["readiness-probe"]`. App/probe essential flags remain true/false respectively.
Both restart policies must be absent or objects with boolean enabled=false and
valid optional policy fields; null, scalar values and enabled policies fail.
Neither container may add a health check or nonempty dependency list. The probe
also rejects workingDirectory/user overrides, nonempty mounts/volumesFrom, and
environment-file injection. Probe environment, secrets and port mappings must
be absent or empty arrays, as must its dependency/mount/environment-file lists;
explicit null is not an alternative spelling of absence. Logging/resource fields
that do not replace the probe execution remain outside this narrow validator.

Readiness scale-up, the gate and its AWS observations require Python 3 on the
Linux runner. The process supervisor reserves a graceful termination interval
inside the remaining budget, then sends SIGKILL to the private process group,
including surviving children. It cleans descendants even when their leader exits
first; nested observer supervisors clean their own groups on outer cancellation.
Output pipes are inherited rather than drained with an unbounded read. Cleanup
reaping has a further 250 ms cap, subject to normal OS scheduling tolerance.
These are implementation properties; exact-candidate deterministic and remote
validation evidence is tracked separately in [validation](validation.md).

The renderer defaults dotnetTests/dockerBuild to passed; the release-build job
does not bind a real exact-source test result to that default. Validation checks
shape/consistency but permits failed/skipped quality values. A prior PR check is
not proven evidence of the exact released artifact without a binding contract.

S3 objects are versioned but publication uses overwrite-capable copies. They are
not immutable/write-once records. ECR immutable tags are enabled, despite an old
code comment saying otherwise. Its lifecycle expires images beyond 15 with
tagStatus=any; retained manifests can point to expired images.

Evidence: [release renderer](../../scripts/render-release-manifest.sh),
[validator](../../scripts/validate-release-manifest.sh),
[publisher](../../scripts/publish-release-manifest-s3.sh),
[record writer](../../scripts/write-deployment-record-s3.sh),
[schemas](../../ci/schemas), [ECR lifecycle](../../ci/authority/retired/terraform/infra/shared/modules/ecr/main.tf.txt),
[deployment script](../../scripts/ecs-blue-green-deploy.sh).

## CURRENT CONTRACT — E2 mutation ownership

[Environment mutation arbitration](e2-environment-mutation.md) now coordinates
protected normal delivery/promotion/rollback, emergency, cleanup and conflicting
WP5 lifecycle operations. The later concurrency/cleanup paragraphs describe
historical pre-E1 algorithms, not current mutation authority. S3 ownership spans
all mutation calls and history publication; cleanup needs its originating schedule
generation. Interruption/uncertainty retains a non-expiring hold. This is offline
repository evidence; no infrastructure is deployed.

## Accepted E3 health and failure boundaries

ALB checks /health, which remains liveness only. Dependency checks live at /ready
(and /health/ready); KMS readiness tests Encrypt only. Task-local `/ready` evidence
is required before promotion, but it is historical one-shot evidence rather than
continuous dependency-health enforcement. Hosted-runner smoke checks
are optional and occur after the switch. Dev smoke URL handling also accepts
/health and /health/live, so its label does not guarantee readiness validation.
Local deploy --smoke-test calls /ready after active target health is observed.

The final ECS/target/routing observation and ALB ModifyListener have no shared
conditional-write boundary. The script minimizes this accepted residual race by
performing no unrelated work between them. Concurrent authorized workflows or the
cleanup Lambda can still change state; any observed mapping, count, revision, task
or target change aborts without a stale compensating write. A failed pre-switch
gate leaves active routing and the active service untouched, but candidate tasks
and the newly registered revision can remain for diagnosis. Startup migrations
may already have affected the shared database.

A failed post-switch smoke/record write does not automatically restore traffic.
Listener/rule failure can leave inconsistent color mappings. current.json can
lag runtime. Read [operations](bootstrap.md) before interpreting pipeline failure
as proof the old release is still active.

Normal dev delivery and emergency flip share cd-demo-api-<env>, but manifest
rollback and prod promotion have different concurrency groups. They can overlap.
The cleanup Lambda independently reads current listener state and stops the
inactive service if the active service has running/desired tasks. It does not
prove dependency health or bind the action to the originating release generation.

Evidence: [ALB health](../../ci/authority/retired/terraform/infra/global/modules/alb/variables.tf.txt),
[health implementation](../../demo-api/terragrunt-demo/Program.cs),
[dev deploy](../../.github/workflows/deploy-dev.yml),
[cleanup Lambda](../infra/apps/fargate/lambda/scale_down_old_color.py).

## UNRESOLVED / TARGET — rollback and evidence

The owner did not comprehensively test original rollback. The emergency flip
and manifest redeploy are current behavior, not a proven recovery contract.
Rollback must eventually consider artifact retention, history/current pointers,
DB compatibility, traffic switching, cleanup and evidence together.

Production should retain robust blue/green; development may become simpler.
Strict provenance and production-like governance are targets, not present
guarantees. See [decision register](decisions-and-limitations.md).
The old [pipeline diagram](diagrams/cd-pipelines.png) and
[phase plan](ci-cd-target-architecture.md) are historical, not instructions.

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


## First protected DEV CI/CD installation

The explicitly selected `dev_cicd_installation_only=true` administration mode
limits controller reservations, bucket creation and request-role creation to
WP3 neutral and the three existing WP4 DEV responsibilities. Its default remains
false; it does not activate WP5 or PROD. Runtime inline policies explicitly depend
on their role resources: a literal name alone does not establish Terraform order.
The first IAM apply exposed that defect; its partial state was read back and a
new four-policy plan completed it without repeating the failed binary plan.

Live readbacks confirmed four published Lambda versions, five CodeBuild projects
and the approved two existing S3 policy changes. Bundle readers gained only the
six runtime identities; WP4 DEV gained its three runtime identities. Existing
NAT/E16, TLS, conditional writes and deletion restrictions were preserved.
The neutral application repository is `demo-shared-demo-ms`; runtime installation
images are not qualified application releases. `demo-dev-shared-demo-ms` and its
manual application history do not establish WP3 qualification.

These runtime resources add ECR/S3/log storage and Lambda/build usage. Builds are
on demand. The original DEV infrastructure stays running and continues charging.
No Terraform state writer transfer, infrastructure deployment, DOWN, NAT failover
or PROD activation belongs to this CI/CD installation.
