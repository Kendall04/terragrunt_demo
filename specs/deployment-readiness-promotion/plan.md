# Implementation plan — Deployment readiness promotion gate

## Authority and outcome

Implement [the durable spec](spec.md), including the owner-approved §3.6 consistency boundary. This plan selects a one-shot, non-essential container in each candidate task, running repository-owned probe logic from the same immutable image as the application. The deployment runner accepts its successful completion only together with repeatedly validated task, revision, image, service, and target identities. The gate belongs before the existing listener switch.

The owner authorized investigation of task-local probing and explicitly accepted bounded control-plane evidence, not atomicity between discovery and switching. No continuously running production sidecar, new routing path, or remote command authority is needed. This document describes intended implementation, not deployed behavior or completed test evidence. No live AWS resources are assumed; the owner reported no infrastructure at reconciliation on 2026-09-18.

## Existing architecture the Executor must preserve

The relevant implementation and authority map is:

| Component | Current contract and implication |
| --- | --- |
| [Common deploy script](../../scripts/ecs-blue-green-deploy.sh) | Determines active color from the listener default target group, validates that the candidate rule points to the opposite group, stops the inactive service, registers a freshly rendered task revision, attaches it at zero count, and starts the requested replicas. It waits for ECS stability and at least the requested number of healthy ALB targets. Those observations currently prove liveness only. |
| [Task renderer](../../scripts/render-demo-api-taskdef.sh), [runtime template](../../demo-api/deploy/task-definition.template.json) | The registered runtime definition is deployment-owned: Linux/X86_64 Fargate, awsvpc, 256 CPU units, 512 MiB, one essential app container, immutable ECR image URI, color-specific roles/logs, and secret ARN injection into the application. No container health check or restart policy is present. Changing only the Terraform bootstrap definition would not update this runtime contract. |
| [ALB](../../terraform/infra/global/modules/alb/alb.tf), [target groups](../../terraform/infra/global/modules/alb/target_group.tf) | Internal HTTP listener on port 8080; separate IP target groups for blue/green. The priority-100 candidate rule matches `/__candidate_dummy__` and associates the inactive group with the listener. It is not a candidate `/ready` transport. Both permanent health checks use `/health`, with a 200–399 matcher, 10-second interval and two-success threshold. Preserve them. |
| [ECS services](../../terraform/infra/apps/fargate/modules/ecs_service/service.tf), [app skeleton](../../terraform/infra/apps/fargate/demo.tf) | Terraform starts both colors at zero and ignores runtime revision/count changes. It also leaves ALB forwarding deployment-owned. Services use FARGATE with 100/200 deployment percentages; there is no application autoscaling. Blue is an initial default, not a permanently active color. Desired count defaults to one in deployment but supports larger positive values. |
| [Networking](../../terraform/infra/global/security_rules.tf), [API integration](../../terraform/infra/edge/modules/apigateway/apigw_http.tf), [routes](../../terraform/infra/edge/modules/apigateway/routes.tf) | Public API Gateway → VPC Link → private ALB → private tasks → SQL Server on EC2. SG ingress permits VPC Link to ALB and ALB to app. Hosted runners cannot directly reach task IPs. Public GET proxy routing includes health endpoints but follows existing listener routing. |
| [Application startup/endpoints](../../demo-api/terragrunt-demo/Program.cs), [health checks](../../demo-api/terragrunt-demo/Health) | `/health` and `/health/live` are process liveness. `/ready` and `/health/ready` check database connectivity/pending migrations and KMS Encrypt, with bounded dependency checks. Startup migrations are enabled by default, run against the shared database and may fail startup. Readiness is not a new domain test, KMS Decrypt test, or schema-rollback guarantee. |

The exact production switch is `elbv2 modify-listener` changing the default action to the inactive target group. The subsequent candidate-rule update, EventBridge scale-down scheduling, output publication, workflow smoke test, and deployment-history writes occur afterward and are not atomic. Preserve their successful ordering and existing failure semantics. The new gate must complete before the first listener mutation, not merely before final deployment reporting.

Dev deployment, prod promotion, manifest rollback, and the local deployment wrapper invoke the common script. They must inherit the gate without optional bypasses. The [emergency color-flip action](../../.github/actions/ecs-blue-green/action.yml) is a separate existing rollback path; this feature does not redesign it or claim it is now readiness-gated. Manifest rollback using the common deployment path must not bypass readiness because of its rollback label.

Read the authoritative [delivery](../../terraform/docs/deployment.md), [architecture](../../terraform/docs/architecture.md), [security](../../terraform/docs/secrets-strategy.md), [operations](../../terraform/docs/bootstrap.md), and [decision register](../../terraform/docs/decisions-and-limitations.md) as needed. Their historical gaps are not additional implementation scope.

## Selected probe and artifact design

Each candidate task contains its essential application and one explicitly non-essential readiness probe. The probe starts with that task, calls the application's loopback HTTP endpoint on port 8080, polls under a finite deadline, requires consecutive successful readiness observations separated by a nonzero interval, and terminates. Exit code zero is reserved exclusively for completing the readiness policy; timeout, cancellation, malformed configuration, HTTP/probe failure at exhaustion, or unexpected termination must not produce zero. Transient connection failures or an unready response reset the success streak and may retry inside the original deadline.

The probe must request the existing `/ready` contract, reject redirects and non-success responses, and validate the expected Healthy result and required dependency checks. It must not accept liveness, an empty/HTML response, or a different endpoint as readiness. Bound each request, response size, parsing, and total execution. The endpoint is local and fixed by the task architecture, not an arbitrary URL supplied by release metadata. No public HTTP fallback or environment proxy detour is allowed.

Use a dedicated probe execution mode/tool packaged in the application image. Both containers must reference the exact same digest-qualified image URI. The mode must execute without starting ASP.NET, applying migrations, resolving the database connection, initializing AWS clients, or becoming another HTTP server. A small .NET HTTP client can use the runtime already present in [the Docker image](../../demo-api/Dockerfile); do not assume curl, wget, a shell feature, or another runtime exists. The Executor may choose an early isolated command mode or a small executable assembly packaged in that same image, subject to these isolation and image-build tests.

This couples probe logic to the existing release digest and source without adding a second image publication/retention/version contract. Do not inject DB secrets, KMS configuration, or application environment wholesale into the probe. It needs only non-secret bounded policy configuration, if any. Preserve the app's normal entrypoint and environment behavior. Existing manifest provenance weaknesses remain separate work; sharing the digest does not prove that historical quality flags reflect real tests.

Older image digests without the probe capability cannot supply evidence. They must fail closed without promotion, never fall back to `/health`, rebuild a selected digest, or silently pull a different probe artifact. This compatibility boundary applies to old manifests consumed through the common script and must be documented. Supporting those artifacts via another architecture requires human review.

### Lifecycle comparison and verified ECS semantics

AWS documentation was inspected during planning on 2026-09-21:

| Model | Viability and selection rationale |
| --- | --- |
| Persistent non-essential sidecar with a container health check | Technically viable; its container health is observable but does not contribute to task health. It would keep running and making dependency calls after promotion. Reported health can remain cached during agent disconnection. It provides no atomic promotion boundary. Reject this ongoing cost/behavior for a pre-promotion feature. |
| One-shot non-essential probe, restart disabled | Selected. AWS specifies that a non-essential container's failure does not affect the other containers. Restart policies are opt-in. Thus normal probe completion leaves the application running, without a permanent probe process or ongoing readiness checks. |

Sources: [Fargate task parameters](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html), [container restart policies](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-restart-policy.html), and [task health and cached health observations](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html).

Containers in one awsvpc task share networking and can communicate over loopback. The required relationship is probe → same-task application at local port 8080. No probe port mapping, SG ingress, ALB health mutation, API Gateway route, or ECS Exec is required. See [AWS awsvpc networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-networking-awsvpc.html).

Keep restart policies disabled for both containers. Do not make application startup depend on probe success: readiness needs a running application, and an essential dependency would change runtime replacement semantics. Starting the probe after the application container starts is permissible, but START is not application readiness. Bounded polling must handle listener startup itself.

### Post-promotion footprint

The probe definition, stopped container metadata, image/filesystem storage, and any configured limits remain. No probe process continues consuming application-level CPU/memory after exit. Keep the existing task size and avoid introducing a dedicated soft memory reservation or a permanent capacity increase. A reasonable probe hard limit and bounded startup CPU use may be chosen and tested within that envelope; do not claim zero startup overhead or automatic reclamation of task-level allocation.

No essential-container health checks are added. Task-health interpretation, ALB liveness, service replacement policy, desired count, and autoscaling behavior remain unchanged. A future replacement task created from the promoted definition also runs its own bounded probe; outside an active deployment attempt, its exit has no control over production traffic or service replacement. Thus the probe is one-shot per task, not literally absent from all post-promotion task launches. This feature does not enforce ongoing dependency readiness after promotion.

## Identity and evidence contract

The deployment attempt has immutable identity: environment/account/region, cluster, active and inactive service/group mapping, newly registered task-definition ARN including revision, expected digest-qualified application image, intended desired count, and a finite deadline established before candidate launch. Evidence belongs only to this invocation. Never persist a reusable ready flag in S3, task tags, files shared across runs, or ALB configuration.

For each replica, evidence must bind the task ARN, expected service/deployment membership, task-definition ARN, application container identity and image, probe container identity and image, and task ENI address/application port. Names or IP addresses alone are insufficient. The registered definition must actually contain the expected non-essential probe execution configuration, with restart disabled; arbitrary containers exiting zero are not evidence.

Use existing ECS discovery plus target discovery. [DescribeTasks](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeTasks.html) can return failures alongside tasks and accepts batches of up to 100. [ListTasks](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ListTasks.html) is paginated and filters desired status, not actual running state. Exhaust pagination and batches; never truncate replica coverage or use count-only proof.

The [Task API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_Task.html) provides revision, group, deployment origin, task timestamps, status, connectivity, and version. The [Container API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_Container.html) provides name/ARN/runtime ID, image/digest, last status, optional exit code, network identity, and a diagnostic reason. Reason text is not machine-verifiable success. Managed-agent status is not the application container's restart history. Container completion time and restart count are not fields of that Container response; do not invent them or misuse task stoppedAt for a probe that exited inside a running task.

Acceptance requires all of the following together:

- The candidate service still references this invocation's new revision and intended count, with no unexpected deployment, pending replacement, or configuration change. Its app container/group/port mapping matches the intended inactive target group.
- Every selected task belongs to that service and expected revision, is desired RUNNING and actually RUNNING, and has a running expected application container. Reject observed stopped/stopping/disconnected states and conflicting identities. Validate the digest-qualified image configuration and reported image identity; do not use mutable tags or silently accept mismatches. Missing required identity fields are not success.
- Every task's expected probe is STOPPED with a present numeric exit code equal to zero. RUNNING probe status is normal pending evaluation; it is not readiness. Missing probe/container, missing exit code on a stopped probe, failed API entries, unexpected command/configuration, or nonzero exit is terminal failure.
- The complete registered candidate target set maps one-to-one to the selected task ENIs and application port, has the requested cardinality, and all targets are healthy under unchanged liveness checks. Reject extra, unmapped, stale, draining, or mismatched targets at authorization; a healthy subset is insufficient. Exact registered-set equality is deliberately conservative, avoiding assumptions about target routing in unhealthy/fail-open situations.
- The listener and candidate rule retain the originally validated, unambiguous opposite-color mapping. Do not infer active color from task count, labels, or deployment records. Unsupported weighted/multi-target actions must not be reduced to the first target and accepted as this deployment contract.

### Startup, replacement, and freshness

Ordinary candidate launch can initially have fewer tasks, incomplete target registration, and running probes. Treat these as bounded startup states with no promotion authorization, not an excuse to accept incomplete final coverage. Establish task identities as they are discovered and freeze the complete cohort once the expected replicas are present. A previously observed task disappearing, being replaced, changing identity, or stopping is a failed attempt; do not substitute another task, reset the cohort, or restart the deadline. An unexpected service revision or desired-count change is also terminal. A new deployment invocation is the recovery path after such a failure.

The probe obtains an actual series of successful `/ready` responses; repeatedly reading one zero exit code does not constitute the readiness stability window. Controller polling subsequently validates identity and continued applicability of that result.

Freshness is conservative and attempt-bounded. Start the controller's finite launch/readiness budget before scaling up, and tie evidence to the newly registered revision and tasks launched for it. A successful probe can have finished before first discovery; its first observed STOPPED time is not its completion timestamp. Its maximum permissible age must therefore be bounded using the attempt/candidate creation window, not a fabricated completion time. Re-reading exit zero never refreshes evidence age. Choose compatible finite probe, ECS startup/stability, ALB convergence, and observation budgets; all relevant waits and AWS calls must remain bounded, including CLI retries/socket waits. No sleeps, task churn, API retries, or identity changes may extend the original gate deadline.

Require repeated consistent complete observations, including a final complete service/task/container/target/routing revalidation immediately before `ModifyListener`. Collect mutually consistent snapshots across discovery calls; ordering must bracket the identity/target checks so a detected change cannot slip through a cached earlier success. Detect contradictory or regressing observations, retain observed invalidations, and fail closed. Do not run unrelated work or another long waiter between final validation and switching. Abort if the deadline expires during final validation. No pre-existing ECS waiter or aggregate ALB health count may bypass this final gate.

This establishes the bounded observational guarantee accepted in spec §3.6. [ECS eventual consistency](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html) and [ModifyListener's API](https://docs.aws.amazon.com/elasticloadbalancing/latest/APIReference/API_ModifyListener.html) do not supply a shared conditional update. Task version counters and repeated reads help reject observed stale state but cannot certify a globally latest snapshot. The residual observation-to-switch race is accepted, must be minimized, and must not be described as eliminated.

## Privilege, ownership, and concurrency constraints

[Split delivery roles](../../terraform/infra/shared/modules/iam_github/github_delivery_split.tf) and [legacy/rollback roles](../../terraform/infra/shared/modules/iam_github/github_ecs_blue_green.tf) already declare ListTasks/DescribeTasks alongside service and target discovery. No new AWS action is required merely to observe probe results. Preserve environment/resource scoping, OIDC trust, secret-access denies, and existing pass-role boundaries. No ECS Exec, RunTask, SSM session, log-read, secret-read, new IAM role, or target-group mutation permission is needed by this design. If an existing permitted observation requires an ARN-scope correction, keep it limited to the relevant environment's resources; do not broaden unrelated authority.

The probe makes local HTTP requests, while the application retains responsibility for accessing SQL/KMS under its existing configuration. It requires no AWS SDK calls or secret injection. However, [AWS task-role credentials](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html) are available within the task, not isolated per container. A non-essential flag is a lifecycle setting, not a security boundary. Using the same repository-owned digest avoids introducing independently trusted third-party code into that task boundary; do not claim the probe is technically unable to obtain task credentials.

Current concurrency is incomplete: normal dev delivery and emergency flip share `cd-demo-api-<env>`; prod promotion uses `promote-prod-demo-api`; manifest rollback uses `rollback-manifest-demo-api-<env>`. Local tooling is outside GitHub concurrency. The [cleanup Lambda](../../terraform/infra/apps/fargate/lambda/scale_down_old_color.py) independently reads the listener and can stop whichever service it considers inactive, without a release-generation binding. It may therefore stop a candidate during evaluation.

No new shared lock or shared mutable readiness state is required for this design. Preserve current workflow concurrency and recovery policy. Recheck original routing before candidate-destructive preparation where practical, and revalidate throughout the gate. Abort on any observed competing service/routing/count/task change. Never repair another actor's mapping, fight cleanup by repeatedly scaling up, or restore a stale listener snapshot. The gate's failure path must itself leave active routing and active service revision/count untouched. It cannot promise to prevent another authorized actor from changing them concurrently; document that limitation alongside the accepted consistency boundary.

## Failure behavior and diagnostics

| Failure | Required behavior |
| --- | --- |
| Alive but never ready; transient failures never stabilize | Probe exhausts its finite policy and exits nonzero. Deployment fails before listener/rule/schedule/success-output changes. |
| Probe crashes, cannot launch, uses unsupported image capability, is OOM-killed, or finishes without an interpretable result | Fail closed. No inference from application health, ECS stability, reason strings, or optional smoke tests. |
| Application/container/task replacement, disappearance, identity change, or competing service revision | Invalidate the attempt. A later healthy replacement cannot inherit or salvage earlier evidence. |
| Discovery permission error, malformed/partial response, ambiguous identity, inconsistent snapshot | Fail closed with bounded diagnostics. Ordinary explicitly recognized startup states may wait only inside the original budget; errors must not be converted into empty successful sets. |
| Unexpected target, stale old target, replica-count mismatch, or target health loss | Never authorize the switch. Initial expected registration may converge boundedly; a change to an established evaluated set invalidates the attempt. |
| Delayed cleanup or concurrent deployment changes candidate count/routing | Abort without restoring cached routing or scaling either side as compensation. |
| Cancellation or controller timeout before switching | No promotion, success record, or new cleanup schedule. Existing temporary local-file cleanup can remain. Do not add automatic candidate teardown with stale ownership assumptions. |
| Failure at/after ModifyListener | Preserve existing non-atomic post-switch behavior; report switch uncertainty honestly. Do not label it a failed pre-promotion gate or implement automatic rollback. |

Diagnostics should identify stage, color, expected versus observed non-secret identity, replica coverage, probe status/exit, elapsed budget, and a concise reason. Preserve existing identifier masking/redaction. Do not dump environment variables, secret values, raw task definitions, or unrestricted response bodies. Probe output may summarize dependency names/statuses but is diagnostic only; successful exit plus validated identity is the evidence channel.

Failed pre-promotion attempts can leave candidate tasks and registered revisions for inspection, as existing deployment failures can. They are failed promotions, not production rollbacks. Startup migrations may already have affected the shared database; unchanged routing is not a database rollback guarantee. Do not expand this feature into schema recovery, release history correction, or cleanup-generation redesign.

## Deterministic validation contract

Tests must exercise production decision paths and record ordering, not merely return zero. Use isolated HTTP/application doubles for the probe and a fail-on-unexpected-call AWS CLI/API substitute for the deployment script. Use disposable outputs, synthetic identities, and controlled clocks/sleeps. No test may fall through to real AWS or start the normal application against configured SQL/KMS. Reuse the repository's Bash fixture conventions and existing .NET test infrastructure as appropriate.

Required evidence includes:

| Scenario | What must be demonstrated |
| --- | --- |
| Ready candidate, both color directions | All exact replicas complete the probe policy; repeated complete identity/target validation precedes the first listener mutation. Existing listener → candidate rule → scale-down scheduling → success outputs sequence remains. |
| Liveness succeeds while readiness fails | Healthy ALB targets and ECS stability cannot reach ModifyListener. Active routing/service state is unchanged by the failed attempt; no success outputs or post-success scheduling/record path runs. |
| Transient startup | Connection refusal/unready responses can recover under one deadline. Isolated success followed by failure resets the streak; success requires the chosen stability window. |
| Multiple replicas | One successful replica cannot cover another; all actual targets are mapped, including pagination/batching. Missing, duplicate, extra, wrong-port, old-revision, or foreign targets cannot pass by matching counts. |
| Identity changes | Replacement during probing, disappearance after success, container identity change, mismatched digest/revision, count/deployment change, and final-stage cohort change all fail the attempt without switching. Test old success returning again after invalidation; it must remain rejected. |
| Incomplete/hostile-shaped observations | STOPPED with absent exit code, RUNNING with an anomalous zero field, nonzero exit, missing probe, API failures embedded in otherwise successful responses, stale/regressing snapshots, and ambiguous forwarding configuration cannot authorize promotion. |
| Freshness and bounds | A completed probe from an earlier attempt, aged evidence, slow/hung HTTP or AWS calls, invalid timing settings, and deadline expiration during final checks fail closed. Polling never renews freshness or extends the deadline. |
| Concurrent activity and cleanup | Inject changed listener/candidate mappings, candidate scale-down, and another deployment revision between reads. Verify abort with no compensating stale writes. Model final-read replacements explicitly; document that unseen changes after the final observation are outside the accepted guarantee. |
| Probe isolation and lifecycle | Probe execution needs no DB secret or KMS credentials, never starts migrations/server/application services, returns correct process exit codes, and stops. Built-image testing proves the selected command/tool exists. Rendering proves same immutable image, non-essential probe, restart disabled, no readiness health-check change, and unchanged normal application launch. |
| Failure boundary | Pre-switch errors cannot invoke listener mutation. Separately verify that a listener/rule failure after authorization is not represented as readiness failure with guaranteed unchanged routing. |

Test the probe against the existing readiness response shape and retain [health endpoint tests](../../demo-api/terragrunt-demo.Tests/HealthEndpointTests.cs). They establish liveness/readiness separation but do not replace deployment ordering tests. Local container tests can demonstrate process completion and command packaging; mocks and Docker tests are not claims of a live Fargate deployment. AWS lifecycle claims rest on the cited documentation until a separately authorized runtime verification.

Wire new tests into an actually selected offline CI path. [App CI](../../.github/workflows/ci-dotnet.yml) restores/builds/tests .NET and builds Docker. [Repo hygiene](../../.github/workflows/ci-repo-hygiene.yml) provides actionlint, shellcheck, and task-render checks but currently does not execute a deployment readiness suite. [CI selection](../../.github/workflows/ci.yml) selects app and hygiene separately: application-only probe changes must still run the relevant gate/renderer contract tests, and script/template changes must select their tests. A suite merely present on disk is insufficient. Preserve existing [CD safety enforcement](../../.github/workflows/ci-cd-safety.yml); do not claim its scope/layer/gate tests already test runtime deployment readiness.

Follow [validation guidance](../../terraform/docs/validation.md). No Terraform plan, dependency installation, live AWS call, deployment, or push is implied by testing. Run appropriate available local checks and authorized CI checks; report unrun checks accurately. Update authoritative deployment/architecture/validation wording alongside the eventual implementation so it no longer says readiness is absent, while retaining the new limitations and existing rollback boundaries.

### Acceptance-criterion review map

| Spec criterion | Plan obligation and review evidence |
| --- | --- |
| 1 | Per-task probe success, exact cohort/target equality, and final revalidation precede ModifyListener. |
| 2 | Liveness is necessary existing evidence but never sufficient; alive/unready negative ordering test. |
| 3 | Exhausted/nonzero probe and controller timeout terminate deployment unsuccessfully. |
| 4 | All pre-switch failure tests assert no active routing/revision/count mutations or stale compensating writes. |
| 5 | Finite probe/controller/request budgets, bounded CLI calls, and fake-clock deadline tests. |
| 6 | Retryable startup with consecutive readiness successes and reset-on-failure tests. |
| 7 | Successful path preserves the current switch and post-promotion sequence, for both colors. |
| 8 | No permanent ALB health-check or essential-container readiness-health change; rendering/static assertions. |
| 9 | Isolated production-path probe and deployment tests run through selected offline CI. |
| 10 | Same image artifact, unchanged public API/routing/runtime ownership, no new recovery/autoscaling mechanism; scope review. |
| §3.6 | Exact identities, full replica coverage, attempt freshness, observed-change invalidation, immediate repeated final validation, and explicit residual race. |

## Executor freedom and human stop conditions

The Executor may choose helper boundaries, filenames for implementation/tests, function signatures, local variable names, fixture representation, a dedicated probe command versus assembly within the same image, reasonable finite timings and success-streak length, bounded resource limits within current task size, test organization/CI placement, and precise diagnostic/documentation wording. These choices need no further human approval when they meet this plan and the spec. The chosen timing and response-validation policy must be explicit and tested, not hidden behind tool defaults.

Return to the owner only if correctness requires a material departure: new independently versioned probe artifact or trust boundary; ECS Exec/new write authority or network exposure; permanent sidecar, essential readiness health, or altered post-promotion replacement behavior; increased task capacity/cost; changes to `/ready` or public routing; bypassing the gate for old artifacts; modifying rollback/cleanup/concurrency ownership beyond observational checks; or weakening per-replica evidence, fail-closed invalidation, or freshness. Absolute observation/switch atomicity is already explicitly out of scope and is not a new blocker.

No further human architecture decision is needed for the selected design under the amended spec. Residual risks are bounded historical readiness rather than continuous dependency health, eventual-consistency/observation races, concurrent external actors, startup resource overhead, old-image incompatibility, and the pre-existing migration/post-switch recovery limits. They must remain visible in implementation documentation and review evidence.
