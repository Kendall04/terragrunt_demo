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

## CURRENT CONTRACT â€” final E1 protected workflows

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
Each still requires the existing separately authenticated G1â€“G9 observation,
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

## Historical helper observations â€” not operational authority

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

## CURRENT CONTRACT â€” E2 mutation ownership

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

## UNRESOLVED / TARGET â€” rollback and evidence

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

When WP3 becomes active, DEV NAT keeps its existing `e1-evidence-<account>-<region>`
administrative bucket. It must not inherit the neutral release-artifacts bucket
from the WP3 selection. The coexistence fixture tests both configurations, and
an installation plan containing NAT function updates must be rejected here.

Request-role activation follows gateway creation. Terraform independently reads
the exact installed numeric Lambda version named by the administrator's WP6
record. This preserves the endpoint comparison without making request IAM depend
on all compute instances; pending NAT publication metadata is outside this stage.
Third-party action pins remain in the toolchain manifest. Same-repository reusable
pins are checked against the exact WP6 source approvals instead of invented tags.


### Approved DEV eligibility and ECS-readback correction

Only new `normal-delivery/deploy-dev` and `cleanup-recovery/cleanup-dev` bundles
select `E1_ELIGIBILITY_DEV_V2`: exact schema, administrator writer, qualified
release ID and ELIGIBLE/REVOKED state. The object body does not predict its own
S3 VersionId. The protected CURRENT read supplies the actual VersionId; the
runtime intent retains that version and the exact body hash. Caller evidence,
historical reads and revoked/foreign releases remain rejected. PROD V1 source,
all NAT packages and immutable previous versions remain unchanged.

The same two DEV bundles recognize only explicitly inert ECS API defaults:
circuit breaker `{enable:false,rollback:false}`, `strategy:ROLLING` and integer
`bakeTimeInMinutes:0`. Active/unknown variants stop the operation. `LATEST` is not
converted to a false numeric platform pin. The candidate must be configured and
read back with a supported numeric platform before normal delivery. Authentic
CloudTrail CreateService records confirm current-cycle skeleton revision `:5`
was created at desired count zero; the currently running revision `:4` is a
later workload and is not misrepresented as an inert bootstrap.

The two DEV bundles also accept the exact derived ECS response capabilities seen
on the live, closed two-container task, while retaining `requiresCompatibilities`
exactly FARGATE. Unknown capabilities, nonempty system controls and nonzero
container CPU defaults reject; these normalizations grant no new task feature.
AWS's inferred EC2/FARGATE/MANAGED_INSTANCES metadata is not launch authorization.

Live candidate replacement demonstrated more than 30 seconds of ECS/ALB drain.
The DEV normal runtime can continue read-only effect observation for up to 600
seconds, bounded by the original immutable operation deadline, only for its own
current invocation's persisted ACK. It never resends a mutation. Missing ACK,
interrupted invocation and unresolved/deadline outcomes remain UNKNOWN and retain
E2. This preserves supervised reconciliation instead of treating normal async
settlement as an instantly final API acknowledgement.

ECS can omit the empty capacity-provider strategy for explicit FARGATE. Only that
absence is normalized to []; nonempty strategies or other launch types reject.


### Fresh DEV namespace absence

The first WP4 Actions attempt stopped before creating a gateway intention,
CodeBuild build or E2 generation: GetObject on a missing S3 key returned 403.
The owner-approved DEV-only correction checks absence with a complete exact-prefix
listing. A denied, truncated, foreign, historical-version or present-key read
cannot become absence. It adds only ListBucket scoped to each existing readable
prefix for gateway/normal/cleanup DEV; it adds no write, delete, state or PROD
permission. Existing NAT and common source implementations remain unchanged.
The owner explicitly approved these own-prefix reads and immutable DEV versions.
After CI 38683396476 passed, a reviewed seven-update plan installed gateway 2,
cleanup 3 and the normal controller bundle. Native IAM/configuration reads and
the existing G1-G9 administrative channel verified the new gateway. The source
request approval names gateway 2. After CI 38684045312 passed the complete E1
gate, the reviewed one-policy plan and GitHub DEV variable were cut over and
read back; release remains gateway 1 with the same immutable workflow pin.
The first failed request created no intention, CodeBuild build or E2 owner;
its request is not resent. A new request may use the same qualified release.


### First authentic Actions / OIDC / WP3 / WP4 DEV result (2026-10-14)

[WP3 Actions 38681029373](https://github.com/Kendall04/terragrunt_demo/actions/runs/38681029373)
and [WP4 Actions 38685068331](https://github.com/Kendall04/terragrunt_demo/actions/runs/38685068331)
completed successfully. CloudTrail independently confirms the two restricted OIDC
request roles. WP3's controller and three isolated workers succeeded, including
103 .NET tests, image build/publication and probe capability checks. The neutral
repository is `demo-shared-demo-ms`, distinct from the prior manually deployed
DEV repository. Its qualified application digest is
`sha256:ca7d92532de8cfeee7a7a59a80f78714a26083ff323019d512d8be20f83ebfb8`.

WP4 registered green revision 6, passed the real E3 gate, switched the internal
ALB listener and published its protected SUCCESS and DEV activation records.
Independent ECS/target-group reads confirm that digest on active green, readiness
HTTP 200 and successful SQL/KMS POST/GET round-trip. Blue subsequently reached
zero tasks and zero targets. These are live observations, not fixture readiness.
The legacy WP3 manifest's `sourceBranch=develop` and run-number defaults are not
real provenance: qualification source commit and actual Actions/CodeBuild/OIDC
observations establish this first trial's origin. Raw evidence remains private.

The automatic inactive-color cleanup separately returned FAILURE after its
acknowledged/observed scale-to-zero: an ALB target was still draining when the
next strict target-membership guard ran. No RemoveTargets call was attempted.
It retained E2 as designed. With separate explicit owner approval, the operator
disabled only that cleanup rule, waited for authenticated empty blue tasks and
targets, verified active green, removed the exact cleanup target/rule and closed
the exact generation-3 E2 record using its unchanged ETag. Owner/generation,
original FAILURE journals and earlier versions were preserved; no automatic
cleanup SUCCESS or generic recovery capability is claimed. E2 is RELEASED and
the cancelled schedule is cleared. Before another delivery, fix and test the DEV
cleanup's observation of target deregistration within its original deadline;
do not replay the failed operation or introduce automatic owner release.

The original DEV architecture, exclusive E16 state writer and remote main/develop
refs are unchanged. No DOWN, NAT failover, PROD installation or WP5 activation
occurred. DEV remains running and billable. Additional CI/CD costs are on-demand
CodeBuild/Lambda, ECR images and S3/CloudWatch evidence; there is no always-running
CodeBuild worker. This successful first delivery does not establish production,
rollback or unattended cleanup readiness.


### DEV cleanup drain settlement correction

The original cleanup did not exhaust its 600-second operation budget. Its
scale-zero effect checked ECS task counts only and returned APPLIED; the next
strict observation then rejected the old ALB target still in `draining`.
The invocation ended after approximately 14 seconds. STOPPED tasks are not
included in the RUNNING desired-status cohort, but ALB deregistration outlives
that cohort. Treating those two observations as simultaneous caused the failure.

Only the new cleanup DEV bundle selects `dev_cleanup.application`. Its existing
scale-zero ACK remains provenance; completion additionally requires stable zero
ECS desired/running/pending counts, no tasks and a complete empty target-health
response. Read errors, absent response fields and draining targets cannot prove
completion. Only the still-running invocation with its own ACK continues polling
within the original mutation/operation deadline; no new deadline, resend or
owner release is added. Retry uses the existing journal/readback path. E2 CAS,
FAILURE retention, PROD/NAT and all other immutable bundles remain unchanged.
Deterministic subcases cover active tasks, stopped/draining, empty terminal state,
transient/malformed/failed reads, deadline, idempotent reconciliation and CAS
failure. Live installation and automatic success must be recorded separately.

### DEV startup settlement and bounded E3 diagnostics

The next authentic WP4 trial (Actions 38689162523) failed before traffic changed
or cleanup was attempted. Green revision 6 remained active. All four issued
candidate effects were observed APPLIED, but the protected delivery outcome was
FAILURE; CodeBuild exit zero was not delivery success. Startup evidence preceded
ECS rollout completion. Native CloudTrail shows E3's service observations across
that transition and no API access errors. The old process port discarded stderr,
so its exact rejection code is unavailable; a service-fingerprint transition is
an inference, not a recovered error message.

Only the normal DEV bundle selects `dev_startup.delivery`: settling the existing
start effect additionally requires the observer's ECS steady-state predicate,
within its original deadline. Strict E3 identity/fingerprint checks are preserved.
A rejected E3 process emits only an allowlisted fixed diagnostic code; arbitrary
child output, SDK values and credentials are not printed. Other environment and
recovery bundles retain their existing implementation. This source correction
and its deterministic tests do not establish live delivery or cleanup success.
The failed generation 5 requires its separately owner-approved reconciliation;
prior FAILURE evidence must remain intact and no old invocation may be replayed.

The subsequent Actions trial 38692781756 reached ECS steady state but failed with
the authentic fixed E3 diagnostic `COMPLETE_E3_EVIDENCE_CHANGED`, before switch or
cleanup. Green revision 6 stayed active, blue revision 7 remained a candidate,
and generation 6 retained FAILURE/ACTIVE. The original four effects were APPLIED;
no cleanup invocation or automatic success is inferred. Its cancellation and
exact FAILURE CAS require the separately approved generation-6 reconciliation.

Only the normal DEV package now restarts the consecutive-stability window when
two independently complete observations have different full fingerprints. It
keeps the complete fingerprints (no fields removed), frozen service/deployment
and task cohort identities, image/probe/network/lifecycle validation, read-error
rejection, original deadline, and immediate final equality check. Continuous
changes time out; changed final evidence still fails. The exact changing AWS
fingerprint component was not retained by the failed invocation and is unknown.
This bounded waiting correction does not classify an identity contradiction as
settled or fabricate the lost snapshots. PROD and the common E3 source retain
existing behavior. `test-dev-e3-stable-window.sh` exercises the actual extracted
DEV loop with deterministic observation ports: settling/incomplete observations,
continuous drift to deadline, final drift, identity rejection and read failure.

### Verified DEV automatic cleanup — 2026-10-15

Authentic GitHub Actions deliveries
[38696034872](https://github.com/Kendall04/terragrunt_demo/actions/runs/38696034872)
and [38697168833](https://github.com/Kendall04/terragrunt_demo/actions/runs/38697168833)
completed SUCCESS through the existing pinned WP4 request workflow. Protected
receipts independently confirm blue revision 8 (operation
`1e55ec37-7628-4351-96bc-7898241f8f65`) and green revision 7 (operation
`6471310a-0a3a-489a-81dd-42213a00ad80`). Both used the existing WP3-qualified
release `sha256-b22f33f93bdac5608da1dcd1e17f372f638dcaa766c1e758f34ee6f396673f44`
and digest `sha256:ca7d92532de8cfeee7a7a59a80f78714a26083ff323019d512d8be20f83ebfb8`.
These trials demonstrate delivery/runtime corrections with the same application
binary, not a new application release or independent WP3 build.

Automatic cleanup Lambda version 4 completed both directions without manual
reconciliation: green cleanup `09da0422-c6c1-584b-aadd-e8412294a923` and blue
cleanup `56e539b3-04b1-5d3b-9c7b-739cc3061c2e`. Each has protected SUCCESS outcome
and receipt plus APPLIED observations for scale-zero, remove-target and delete-rule.
During each drain, native ECS showed zero tasks while ALB still retained a target;
the journal retained its scale-zero ACK without prematurely recording APPLIED.
Native Lambda durations were approximately 325 and 326 seconds, below the
unchanged 600-second deadline. The existing ALB deregistration delay was 300 seconds.
No timeout increase, IAM action expansion or new compute service was needed.

Independent final reads confirmed green revision 7 desired/running 1, pending 0,
healthy target and active listener; blue revision 8 desired/running/pending 0,
no tasks and no targets; temporary cleanup rule absent. E2 generation 10 is
RELEASED with schedule null, through normal automatic completion. `/ready`
returned Healthy and a unique POST/GET roundtrip verified SQL persistence and
KMS encryption/decryption through the active API, all HTTP 200. Earlier generation
3/5/6 FAILURE journals and object versions remain unchanged. Separately authorized
manual reconciliations of the two failed pre-promotion trials are not automatic
cleanup evidence. Queued duplicate invocations did not create a new E2 owner.

Validation: the final executable-source revision `f0bf1ffe6a6a21732ad858e5377768a3bea68ad0`
passed the complete local E1 gate (959 regressions + 24 WP7, AC1–AC16), generated
packages/inventory, affected safety suites and Terraform format checks. The six
extracted DEV loop cases and ShellCheck also passed. Existing static findings
remain 24 TFLint / 46 tfsec by identity/multiplicity; no IaC topology changed.
Application source was unchanged; this increment did not rerun .NET/Docker builds.
Live proof and local gate results remain distinct. Private runtime evidence was
kept outside Git. No commits were published automatically.

Rollback is prepared, not executed. Both successful histories now exist, but
the DEV `rollback-manifest.yml` caller still requires `develop` while its approved
OIDC entry allows only `codex/final-github-actions-cicd`. The smallest proposed
fix selects the already approved `source_ref(deploy-dev)` for that DEV caller;
PROD stays on main. Protected renderer-source/governance reconciliation and
explicit publication authorization remain required; a normal feature push would
also publish the earlier local documentary commit that the owner excluded from
automatic publication. Do not bypass the caller by direct Lambda/ECS/listener
writes. A qualified rollback recreates a revision from the selected SUCCESS
history and current eligibility; removed tasks are not themselves recoverable.
The two current histories share a digest, so such a test would prove rollback
mechanics rather than behavior between two different application binaries.

DEV remains running and billable. This work added only versioned S3 bundles and
on-demand CodeBuild/Lambda/log activity; no additional persistent compute or
network topology. No DOWN, NAT failover, PROD/shared mutation or Terraform DEV
state operation occurred.

### Pending distinct-image DEV rollback trial

The live baseline remains green revision 7, blue revision 8 stopped, E2 generation
10 RELEASED, with the two automatic cleanup SUCCESS receipts above. Native
preflight confirmed both protected histories refer to the same qualified image;
the neutral ECR repository contained only that image. They are not evidence of
restoring a different application version.

The prepared source change aligns only the DEV rollback caller with
`source_ref(deploy-dev)`, the already authorized exact feature ref. PROD remains
restricted to main, workflow_dispatch remains mandatory, and existing Environment,
OIDC audience/repository/subject, numeric gateway and immutable reusable workflow
requirements remain in force. No direct ECS/Lambda/listener rollback route is added.
Tests assert exact DEV and PROD caller conditions and existing identity rejection.

Because the authoritative renderer is source-bound, its old release/deploy-dev
source approval records cannot attest this changed source. This preparation
explicitly removes those source activations and regenerates callers as inactive;
it does not apply their removal to AWS. Never apply the whole security root to
install this intermediate preparation. The current live identities remain on the
previous authenticated pin. After explicit public-publication approval, publish
only the feature branch, verify its actual CI and immutable sources plus G1–G9,
then use the existing approval procedure to admit only release/deploy-dev against
the new exact commit and observed numeric gateways. Reconcile the generated
caller pins, exact request-role trust and Environment variables through reviewed
installation/readbacks before WP3/WP4 dispatch. No approval may be fabricated from
local JSON. No PROD/shared activation, new IAM actions or wildcard refs are needed.

A single fixed startup message, `Application revision: rollback-proof-v2.`, is
prepared in the application binary. It changes no HTTP payload, database schema,
SQL/KMS contract or dependency. Its sole purpose is a traceable, harmless second
binary. The digest must be measured from a genuine new WP3 qualification; it is
unknown before build. Do not publish a manual image or reuse an old qualification
as the new version.

Supervised trial after authorization: preserve the old qualified release and
SUCCESS receipt for green operation `6471310a-0a3a-489a-81dd-42213a00ad80`; qualify
the new source once via WP3; deploy its distinct measured digest to inactive blue
via WP4; verify health/SQL/KMS, promotion and automatic cleanup; then use
`rollback-manifest.yml` with environment dev, that exact old green history and
replicas 1. Refresh only the legitimate inactive-color binding from actual
readbacks. WP4 must reauthorize the history and current eligibility, register a
new task revision, prove its old digest, promote, and complete automatic cleanup
and E2 release. Never restart deleted tasks or rewrite history/FAILURE receipts.
Stop and reconcile any ambiguous result before another request.

Publication and execution have not occurred for this preparation. A normal push
also includes the unpublished documentary/cleanup commits after remote d016fc5;
the exact final range, files, secret/history audit and automatic workflows must
be presented for explicit owner approval first. The second digest, release ID,
new task revision and rollback outcome remain unknown until genuine execution.

#### Authentic new-pin admission prepared, not activated

The first owner-approved feature publication ended at immutable commit
`f0ba8ad1d6528d362693c8de932f935c8084529d`. Its real GitHub CI
[38702309795](https://github.com/Kendall04/terragrunt_demo/actions/runs/38702309795)
completed SUCCESS, including E1, .NET/Docker, hygiene, static infrastructure and
aggregate validation. No release or deployment workflow was triggered.

The existing administrator readback procedure independently verified every WP6
source hash at that published commit, current subject customization, branch and
Environment restrictions, isolated entries/runners, secret-name exposure limits,
project bundle versions, runtime trust/inline/resource policies and the two
existing numeric gateways (release 1, deploy-dev 2). Only release/deploy-dev
received new source-bound admission records from those authentic observations;
no PROD entry, IAM action, ref wildcard or lifecycle authority was added. The
new generated callers pin that exact immutable commit. Private readbacks remain
outside Git; the checked-in admission is not a substitute for live installation.

This second local revision requires its own exact publication authorization.
Before dispatch, its CI must pass; review/apply only the two existing request-role
trust replacements from the old immutable pin to the new pin, without modifying
permissions, and update/read back only the two existing Environment configuration
variables. Do not apply the intermediate inactive root or a graph-wide plan.
Until those installation readbacks succeed, the live request route retains its
old configuration and no new WP3/WP4/rollback request is permitted.

### Rollback trial: authentic admission and source transport (2026-10-15)

The authorized feature publication reached `8317c604ee4c86fa05ec261256fc3eebc5cfe744`.
[CI 38704428485](https://github.com/Kendall04/terragrunt_demo/actions/runs/38704428485)
passed E1, hygiene and infrastructure; app CI was correctly skipped for that
metadata-only delta. The preceding
[CI 38702309795](https://github.com/Kendall04/terragrunt_demo/actions/runs/38702309795)
had passed app/Docker checks. Both existing request-role trusts and Environment
configurations now pin `f0ba8ad1d6528d362693c8de932f935c8084529d`, without new actions,
refs or gateways. CloudTrail independently observed successful GitHub OIDC for
the exact release subject, audience and new immutable pin.

[WP3 38705672347](https://github.com/Kendall04/terragrunt_demo/actions/runs/38705672347)
was rejected before creating a build: the published source lacked its existing
source-admission record. The administrator admitted only that exact published,
CI-successful commit with create-only/version readback. Later genuine requests
38706006545, 38706580283, 38712621736 and 38800776556 produced protected terminal
source failures: all seven checks NOT_RUN, without workers or image publication.
Their polling jobs were cancelled only after terminal readback; failures remain.
No delivery/rollback was dispatched and no E2 owner/generation changed.

A read-only diagnostic in the existing immutable controller image reproduced
HTTP 403 and anonymous GitHub REST quota zero. After the announced reset, a
separate complete read-only acquisition passed all 42 REST reads and source
integrity checks. Diagnostic CodeBuild successes are not qualifications. Each
business attempt suppresses its transport exception, so the observed quota
failure is not a proven explanation for every later failure.

The local, not-installed Source patch retains commit/tree REST reads and obtains
file bytes through fixed-repository raw URLs at that exact commit. Every body
must match its selected tree's Git blob SHA before materialization; portable
paths, modes, source-size bounds and sealed execution checks remain enforced.
This application needs two REST reads plus 40 raw-content reads, rather than
42 REST reads. HTTP failures remain fail-closed; diagnostics log only a fixed
transport category and integer status, never URLs, headers or error bodies.
No token, IAM action, archive extraction, branch/latest fallback or retry is added.
Two metadata reads still require REST availability; this cannot promise success.

Focused tests exercise production URL construction/encoding, SHA mismatches,
wrong source, links/traversal, oversize bodies and metadata/raw rejection without
private diagnostics. New subcases preserve the accepted regression methods.
The executable pin and derived package IDs are reconciled; historical fixture
normalization verifies the exact inverse of 49 content-ID fields while retaining
original digest/security assertions. Derived inactive PROD/WP5 hashes do not
activate or install those paths. WP4 cleanup, E2, workflow, app and IAM behavior
are unchanged by this patch.

Fresh AWS observations: green revision 7 healthy, blue revision 8 at zero, E2
generation 10 RELEASED, original histories preserved, /ready and POST/GET SQL/KMS
passed. DEV remains running and billable. No second qualified digest or real
rollback is claimed. The changed Source also passed actual public reads of all
40 files and source integrity from the local host; that is not AWS qualification.

Next: review/authorize the additional public source commit, verify its actual CI,
then rebuild/review the existing WP3 immutable runtime installation, including
its shared support identity and exact bundle/version/permission readbacks.
Prepare the concrete affected-resource plan before installing; never apply a
whole security-root graph with stale installation inputs. Keep current WP4 DEV
runtime/gateway versions and evidence readable; no PROD/WP5 activation or writes
to the five E16 states. Only genuine distinct-digest WP3 success enables the
already-described protected delivery/rollback trial. Remote main/develop stay
unchanged. Private plans, logs and native evidence remain outside Git.
