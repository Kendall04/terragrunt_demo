# Architecture and current contracts

> **Closure status — 2026-10-16:** the complete original DEV topology below was deployed and
> exercised, then destroyed. The [portfolio operations guide](portfolio-operations.md)
> distinguishes retained security/control resources from the empty runtime states. Early
> inactive/default declarations below describe the source baseline; the dated [delivery
> evidence](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback)
> records the separately installed DEV WP3/WP4 path. No PROD deployment or Cloud Map is
> implied.

WP7 defines the repository E1 authority model. Its eleven external identities
and default sixteen WP4D/eight WP5 binding declarations remain inactive. The
[first real DEV deployment](first-real-dev-deployment.md) records separately
installed DEV state authority, original runtime resources and three NAT handlers;
repository acceptance alone does not establish those installations.
[Final acceptance](e1-final-acceptance.md) separates repository
evidence from genuine future installation and live verification. The immutable
[specification](../../specs/iam-hardening/spec.md) and
[plan](../../specs/iam-hardening/plan.md) govern the accepted architecture.

## CURRENT CONTRACT — authority, layers and state

[E15 DEV lifecycle](e15-ephemeral-lifecycle.md) maps retained authority and the
proposed reverse dependency teardown. Local preparation cannot authorize AWS;
active-service quiescence, destroy preview and NAT executor settlement remain gates.

[E8 retention](e8-rollback-image-retention.md) removes automatic expiration from
the three protected application repositories. WP3 publishes untagged images to
the neutral repository shared by dev/prod; digest references alone do not prove
availability. Storage remains unbounded pending a horizon/cleanup decision.

Only the neutral [security root](../infra/security/README.md), its
[wrapper](../live/security/terragrunt.hcl) and the fixed
[TARGET environment modules](../modules/target) remain operational configuration.
Ordinary lifecycle cannot change the security root, workload roles, protected
bindings, controller executables, eligibility or protected storage controls.
Public requesters have an exact pinned gateway or read-only plan authority;
internal roles have service-only trust. Security administration remains separately
authenticated human authority without a GitHub role or automatic fallback.

| Owner / layer | Represented responsibility |
| --- | --- |
| Neutral security root | OIDC, workload/request/controller IAM, KMS, secret metadata/policies, ECR/evidence/control storage, protected state and NAT launch configuration |
| Environment shared | Alerts and nonsensitive configuration |
| Environment secrets | Fixed consumption of admin-published metadata; no values |
| Environment global | Networking, ALB/target-group skeletons, bounded NAT ASGs/EIPs with protected launch bindings |
| Environment data | SQL EC2/root disk/alarms with fixed profile and launch binding; high-risk approval |
| Environment platform | ECS cluster/capacity providers |
| Environment apps | Role-free, zero-count service bootstrap/logs/alarms; high-risk approval |
| Environment edge | API Gateway/VPC Link |
| Qualified delivery/recovery | Task revisions/counts, ALB forwarding and bounded existing-content repair |

[E2 ownership](e2-environment-mutation.md) uses conditional protected S3 heads
per environment/conflict domain across delivery/recovery and conflicting lifecycle.
Shared alerts and metadata-only consumption remain independent; status/plans
gain no mutation authority. There is no lease takeover after interruption.
[E4 bounded continuation](e4-post-switch-recovery.md) reconciles one post-switch
evidence-persistence failure inside the still-owning delivery invocation; it adds
no compensation or interrupted-owner takeover.
[E2-R diagnostics](e2r-owner-recovery.md) retain that hold: S3 generation fencing
cannot stop an already checked/issued downstream call, and authenticated executor
termination plus remote quiescence is not currently verifiable.

Lifecycle state uses fixed environment buckets/keys and S3 lockfiles. It never
reads security state. Protected controllers select layers, membership, backend
and bindings; public callers cannot supply arbitrary Terraform or redefine roles.
Neutral protected dependencies remove dev-owned security authority over prod.
Broader production operational independence remains the separate owner target;
E1 does not select account migration or database durability.

Legacy infra/live roots, broad GitHub IAM, composite actions and direct local
bootstrap/deploy entry points are retired. Frozen source bytes under
[retired text](../../ci/authority/retired) preserve provenance and exact generators;
they are not installable infrastructure. No live state reconstruction, migration,
session revocation or deployment occurred.

## CURRENT CONTRACT — topology and networking

Client → public API Gateway HTTP API → VPC Link → internal ALB HTTP:8080 →
active Fargate color → private SQL Server TCP:1433. KMS and public AWS endpoints
use NAT egress. There is one application; blue/green are release slots.

Each environment inherits VPC `10.0.0.0/16`, public subnets `10.0.0.0/24`
and `10.0.1.0/24`, private subnets `10.0.100.0/24` and `10.0.101.0/24`,
and the first two available AZs. Public routing uses an internet gateway.
Each private subnet has a route table whose default route is Lambda-managed.
Both environment CIDRs overlap; no interconnection exists.

Ingress SG references allow VPC Link → ALB → app → DB. ALB/tasks/DB are private.
Application and database egress allow all protocols to 0.0.0.0/0; this is not a
permanent accepted invariant. No VPC endpoints are configured.

Two t3.micro NAT ASGs each maintain one instance. User data configures forwarding
and masquerading. Three independent ASG launch-success targets associate an EIP,
update a route and disable source/destination checks. This is per-AZ replacement
recovery. [E13](e13-nat-reliability.md) separately contains EventBridge delivery
and Lambda execution failures, verifies exact network/bootstrap evidence and keeps
private-subnet egress explicitly unverified pending genuine traffic observations.
There is no cross-AZ failover or continuous packet-forwarding health algorithm.

Evidence: [global](../modules/target/dev/global),
[edge](../modules/target/dev/edge),
[protected NAT installation](e1-protected-environment-lifecycle.md).
Protected NAT compute remains gated; configured topology is not live availability.

## CURRENT CONTRACT — runtime ownership

Terraform creates both colors at zero tasks, 256 CPU units and 512 MiB memory,
with separate roles/logs and IP target groups. Deployments render the real
[task template](../../demo-api/deploy/task-definition.template.json), containing
the essential application and a non-essential one-shot readiness probe from the
same digest-qualified image. The probe calls the same task's loopback `/ready`,
requires bounded consecutive healthy dependency responses, then stops.
Permanent ALB health remains process-liveness `/health`; `/ready` is a
deployment-time promotion gate, not continuous runtime health enforcement.
ECS ignores task-definition/desired-count changes; ALB ignores forwarding action
changes. Deployment tooling owns those fields. Blue is only the initial default,
not permanently active. A dummy-path candidate rule associates the inactive TG.

Deployments default to one task; no app autoscaling exists. Container Insights and
capacity providers exist, but services explicitly use FARGATE, not Spot.
No Cloud Map registration exists despite a stale code comment. Before changing
the listener, deployment tooling freezes the exact candidate cohort and requires
independent evidence from every exact candidate replica. Evidence is bound to the
task, deployment, revision, digest, container and network identity that produced
it and cannot transfer to a replacement task. The frozen cohort must equal the
observed routable healthy ALB target set. Contradictions, identity or lifecycle
regressions, replacements, malformed responses and ambiguous observations fail
closed. An unsuccessful gate leaves active traffic unchanged.

Probe exit zero authorizes promotion only after the registered task definition
proves the intended execution contract: the immutable application image, exact
`["readiness-probe"]` command, inherited image entrypoint, application/probe
essential flags, disabled restart semantics, and the absence of the execution
overrides or injection paths rejected by this feature. This is a narrow validator,
not a claim that every possible container-isolation property is enforced.

Authorization data from external commands is structural evidence, not merely jq
input. Before semantic interpretation it must establish, in order: exactly one
JSON document, the expected top-level/cardinality contract, endpoint-specific
structure, required nested structure, and semantic validity. Filtering, optional
iteration, `select`, slurping, normalization or jq last-result behavior must not
discard malformed or contradictory evidence to salvage an authorization result.

Readiness is bounded by a total probe deadline plus request, response-body and
external-observation bounds; a success arriving after the total deadline is not
success. External observations use bounded process supervision and terminate the
private process group. Process-group containment is the implemented boundary; it
does not promise universal containment of a deliberately escaped group/session.

The controller performs a complete final revalidation immediately before the
listener write. This is intentionally a bounded observational consistency model,
not an atomic ECS/ALB transaction: those APIs provide no shared compare-and-swap
boundary, so the remaining final-observation-to-`ModifyListener` race is an
accepted consistency boundary rather than an unresolved defect.
Protected normal delivery authorizes qualification, current eligibility, closed
runtime properties and exact color/environment task/execution roles before startup.
External callers cannot register tasks, pass roles or mutate services/listeners.
Emergency recovery has a separate existing-content contract and cannot register
or publish content. The old shell main rejects execution; its library remains
for accepted E3 regression fixtures.
Evidence: [app skeleton](../modules/target/dev/apps/ordinary-demo.tf),
[ECS lifecycle](../modules/target/dev/apps/modules/ecs_service/service.tf),
[normal delivery](e1-wp4b-normal-delivery.md), [recovery](e1-wp4c-bounded-recovery.md),
[E3 gate](../../scripts/ecs-readiness-gate.sh).

## CURRENT CONTRACT — application and data

The [E14-A container contract](e14-container-hardening.md) pins both .NET 8
base images to verified Linux/x86-64 manifests and explicitly runs the application
and packaged readiness probe as UID 1654. HTTP 8080, `/app`, the framework-dependent
DLL entrypoint and ECS environment/secret semantics are preserved. Deterministic
checks, host startup and isolated Linux container execution pass; live Fargate
execution remains unverified. See the linked batch integration evidence.

| Interface | Behavior |
| --- | --- |
| POST /text | Reject blank input, then plaintext over 4096 UTF-8 bytes; KMS-encrypt accepted bytes; persist base64 ciphertext; return plaintext DTO |
| GET /text | Read/decrypt page ordered by CreatedAt descending, then unique Id descending; default 50, maximum 100; ten concurrent decrypts per request |
| /health, /health/live | Process liveness only |
| /ready, /health/ready | DB connectivity/pending migrations and KMS Encrypt |
| Swagger | Development environment only |

Gateway authorization is NONE; no application auth pipeline exists. GET proxy
routing exposes health endpoints too. CORS is disabled by default, not an access
control. MediatR handlers call an EF SQL repository and KMS interface.
No business queues or separate encryption service exist. One decryption failure
fails the request. The symmetric direct-KMS wrapper accepts at most 4096 UTF-8
bytes and rejects larger plaintext before calling KMS. POST returns HTTP 400
with the string `Text must not exceed 4096 UTF-8 bytes.`; blank-input validation
still takes precedence. GET rejects page numbers below 1 and page sizes outside
1–100 with the existing HTTP 400 string errors. Offsets are calculated with widened
arithmetic; `(page - 1) * pageSize` above `int.MaxValue` returns HTTP 400 with the
string `Page is too large for the requested PageSize.` before repository/decryption
work. Representable pages beyond the result set return an empty HTTP 200 array.
Internal handler/repository calls retain lower-bound normalization (handler size
also caps at 100) and throw `ArgumentOutOfRangeException` for unrepresentable
offsets. Unique ordering prevents timestamp ties from moving records between
pages for an unchanged dataset; offset pagination does not provide a snapshot
across concurrent inserts/deletes. Larger payload support and dependency error
contracts remain limitations.

DB_CONN_STRING is required outside Development; Development may use configured
fallback. KMS_KEY_ID selects encryption; SDK credentials use the runtime chain.
APP_ENV does not select ASP.NET Development; APP_ENV/DEPLOYMENT are not used by
the inspected application logic.

SQL Server 2022 Express runs on Ubuntu EC2 in the first private subnet, default
t3a.small. Its encrypted 30-GiB root disk is deleted on termination. The app user
has db_owner; startup EF migrations are enabled by default and fail startup on
error. Both colors share the DB. Image rollback does not reverse schema changes.
The ciphertext-expansion migration explicitly declares its DbContext and migration
identity so EF discovers and applies the existing `nvarchar(max)` operation.
A provider-only regression scripts it without opening SQL; the first real DEV
startup separately verified both migrations and the resulting column length.

Evidence: [Program](../../demo-api/terragrunt-demo/Program.cs),
[controller](../../demo-api/terragrunt-demo/Controllers/DemoTextController.cs),
[handlers](../../demo-api/terragrunt-demo/Features/Texts),
[repository](../../demo-api/terragrunt-demo/Repositories/ITextRepository.cs),
[encryption](../../demo-api/terragrunt-demo/Services/IEncryptionService.cs),
[data](../modules/target/dev/data/ordinary-main.tf), [SQL setup](../infra/data/user_data.sh).

The original simple demo is not the final backend target. Read the decision
register before adding identity or treating database limitations as accepted.

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
