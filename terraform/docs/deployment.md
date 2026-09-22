# Deployment and release contract

Read [architecture](architecture.md) for ownership and [validation](validation.md)
for command effects. This describes checked-in behavior, not proven deployment
results. No AWS infrastructure currently exists (owner reconciliation 2026-09-18).

## CURRENT CONTRACT — entry points

| Entry point | Behavior |
| --- | --- |
| ci.yml | Path-selected checks on working-branch pushes and PRs to develop/main |
| ci-cd-safety.yml | Independent CD Safety Validation job on PRs to develop/main and develop pushes; conservative selection, offline scope/layer/gate tests and explicit outcome checks |
| ci-dotnet.yml | Restore/build/test and Docker build |
| ci-terragrunt.yml | TFLint, tfsec and format checks; no remote plan |
| ci-terragrunt-plan.yml | AWS-backed initialization/validation/plan; PR caller currently passes dev even for main-target PRs |
| ci-terragrunt-manual.yml | Static checks; optional remote plan for selected dev or prod |
| cd.yml | Develop safe-layer applies, high-risk approval flow and app delivery; main emits manual-promotion notices |
| cd-terragrunt.yml | Manual layer plan/apply; dev data/apps use protected-environment-shaped high-risk path; prod data/apps explicitly rejected |
| release-build.yml → deploy-dev.yml | Build/publish image and manifest, then deploy existing manifest to dev |
| promote-prod.yml | Manual existing-manifest promotion; normally requires matching dev deployment record; emergency override exists |
| rollback-manifest.yml | Redeploy selected manifest and record rollback |
| cd-rollback.yml | Emergency color flip; does not update S3 manifest history/current pointer |
| scripts/deploy.sh | Local bootstrap/deploy wrapper; not equivalent to audited manifest workflow |

Evidence: [workflows](../../.github/workflows),
[scope resolver](../../.github/scripts/cd/resolve-terragrunt-layers.sh),
[gate](../../.github/scripts/cd/validate-infra-gate.sh).

The [CD safety check](../../.github/workflows/ci-cd-safety.yml) has passed independent
review of all 12 spec criteria. Its entry points, selection/history contract and
review/remote evidence are recorded in [validation](validation.md#cd-safety-enforcement--reviewed-contract).
It detects regressions on develop without changing CD ordering or adding a new
deployment dependency. The observed GitHub check identity is `CD Safety Validation`.
Required-status-check enforcement remains external and unconfigured/unverified:
configure main to require this check from the expected GitHub Actions source.
Required/missing-check enforcement, bypass exceptions, fork approval policy and
any actual merge-queue usage must be checked externally before claiming governance
is enforced. No merge-queue compatibility is claimed by this implementation.

Develop change classification orders safe layers shared, secrets, global,
platform, edge. Nested module changes and root/unmapped paths are critical/manual;
data and apps/fargate are managed high-risk layers. The orchestrator can plan
and apply those through dev-infra-approval after safe work succeeds. Critical
paths block app delivery rather than silently skipping required infrastructure.

The approval job requires DEV_INFRA_APPROVAL_GATE_CONFIGURED=true. This variable
does not prove required reviewers exist. Approved high-risk work is replanned and
applied, not applied from a saved reviewed plan. Generic manual applies are
layer-scoped, not graph-wide. Prod high-risk support is intentionally absent in
the current workflow; do not describe all prod layers as supported.

## CURRENT CONTRACT — identity and resource configuration

OIDC replaces static AWS pipeline credentials. Trust subjects are environment
shaped; external GitHub branch/reviewer protections remain unverified.
Read [security](secrets-strategy.md) before changing role selection.

Current role inputs include AWS_ROLE_TG_CI, AWS_ROLE_TG_CD,
AWS_ROLE_TG_CD_HIGH_RISK, AWS_ROLE_RELEASE_BUILD, AWS_ROLE_DEV_DEPLOY,
AWS_ROLE_PROD_PROMOTE and AWS_ROLE_APP_ROLLBACK. Some build/deploy/promotion paths
retain legacy AWS_ROLE_APP_CD fallbacks; manifest rollback refuses that fallback.
The orchestrated high-risk apply has a TG_CD fallback, whereas manual high-risk
delivery requires its dedicated role. Do not assume these migration allowances
are deployed or endorsed as the final boundary.

Resource resolution uses ALB_LISTENER_<ENV>, ALB_CANDIDATE_RULE_<ENV>,
TG_BLUE_<ENV>, TG_GREEN_<ENV>, SCALE_DOWN_LAMBDA_<ENV>, DB_SECRET_ARN_<ENV>
and optional SMOKE_TEST_URL_<ENV>. Consult
[resource resolver](../../.github/actions/resolve-demo-api-resources/action.yml),
[artifact resolver](../../.github/actions/resolve-demo-api-artifact-resources/action.yml)
and [backend resolver](../../.github/actions/resolve-backend/action.yml) for exact
defaults and validation. Do not copy real resource/credential values into docs.

## CURRENT CONTRACT — artifact and traffic lifecycle

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
[schemas](../../ci/schemas), [ECR lifecycle](../infra/shared/modules/ecr/main.tf),
[deployment script](../../scripts/ecs-blue-green-deploy.sh).

## CURRENT CONTRACT — health and failure boundaries

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

Evidence: [ALB health](../infra/global/modules/alb/variables.tf),
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
