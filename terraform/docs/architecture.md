# Architecture and current contracts

Implementation baseline: `f8c948cf54ec869bc135aea8a9bf1d43e02030f5`.
These are checked-in contracts, not deployed facts. The owner confirmed no
deployed infrastructure on 2026-09-18. See [decisions](decisions-and-limitations.md)
for accepted constraints and future direction.

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
recovery, not cross-AZ failover or verified packet-forwarding health.

Evidence: [global](../infra/global/main.tf), [VPC](../infra/global/modules/vpc),
[SG rules](../infra/global/security_rules.tf), [NAT](../infra/global/modules/nat),
[edge](../infra/edge/modules/apigateway).

## CURRENT CONTRACT — layers and state

| Layer | Owns | Dependency inputs |
| --- | --- | --- |
| shared | KMS, ECR, GitHub IAM, alerts, artifact bucket | Account/environment settings |
| secrets | Secret metadata only | Shared KMS |
| global | VPC, SGs, NAT, ALB/target groups | Shared alerts |
| data | SQL EC2, role, root disk, alarms | Global, secrets, shared alerts |
| platform | ECS cluster/capacity providers | Environment settings |
| apps/fargate | Service skeletons, roles, logs, alarms, cleanup Lambda | Global, platform, shared, secrets; data ordering |
| edge | API Gateway/VPC Link | Global listener, subnets, SG |

[Live roots](../live) use S3 state and DynamoDB locking. Keys are
`path_relative_to_include()/terraform.tfstate`; environment separation depends
on distinct buckets. Wrapper scripts export account-qualified backend names;
root defaults omit the account suffix. TG_ENV can override the directory default.
Directory, environment, backend and AWS identity must agree.

Terragrunt generates provider/backend files and uses mocks for validate/plan.
Mocks do not prove deployment viability. [Bootstrap](bootstrap.md) includes
secret writes outside the dependency graph.

Dev/shared creates the account-wide OIDC provider, shared artifact ECR and release
bucket; prod/shared consumes them. **This is a historical ownership mistake,
not an invariant to preserve.** Production independence is a target; its mechanism
is unresolved. Evidence: [dev root](../live/dev/root.hcl),
[dev shared](../live/dev/shared/terragrunt.hcl),
[prod shared](../live/prod/shared/terragrunt.hcl).

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
Evidence: [app skeleton](../infra/apps/fargate/demo.tf),
[ECS lifecycle](../infra/apps/fargate/modules/ecs_service/service.tf),
[ALB](../infra/global/modules/alb/alb.tf),
[cluster](../infra/platform/modules/ecs_cluster/main.tf),
[deployment gate](../../scripts/ecs-readiness-gate.sh).

## CURRENT CONTRACT — application and data

| Interface | Behavior |
| --- | --- |
| POST /text | Reject blank input, then plaintext over 4096 UTF-8 bytes; KMS-encrypt accepted bytes; persist base64 ciphertext; return plaintext DTO |
| GET /text | Read/decrypt page; default 50, maximum 100; ten concurrent decrypts per request |
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
still takes precedence. Larger payload support, pagination overflow/tie ordering
and dependency error contracts remain limitations.

DB_CONN_STRING is required outside Development; Development may use configured
fallback. KMS_KEY_ID selects encryption; SDK credentials use the runtime chain.
APP_ENV does not select ASP.NET Development; APP_ENV/DEPLOYMENT are not used by
the inspected application logic.

SQL Server 2022 Express runs on Ubuntu EC2 in the first private subnet, default
t3a.small. Its encrypted 30-GiB root disk is deleted on termination. The app user
has db_owner; startup EF migrations are enabled by default and fail startup on
error. Both colors share the DB. Image rollback does not reverse schema changes.

Evidence: [Program](../../demo-api/terragrunt-demo/Program.cs),
[controller](../../demo-api/terragrunt-demo/Controllers/DemoTextController.cs),
[handlers](../../demo-api/terragrunt-demo/Features/Texts),
[repository](../../demo-api/terragrunt-demo/Repositories/ITextRepository.cs),
[encryption](../../demo-api/terragrunt-demo/Services/IEncryptionService.cs),
[data](../infra/data/main.tf), [SQL setup](../infra/data/user_data.sh).

The original simple demo is not the final backend target. Read the decision
register before adding identity or treating database limitations as accepted.
