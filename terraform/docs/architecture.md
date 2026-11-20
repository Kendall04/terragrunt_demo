# Architecture and current contracts

[Project](../../README.md) · [Five current diagrams](../../docs/interactive/CURRENT-INDEX.md)

DEV is an AWS laboratory with automatic API delivery and measured cold SQL
recovery. PROD declarations are not a deployed or qualified environment.
The [dated evidence](../../docs/RESULTS.md) distinguishes implementation
from observed AWS behavior; this guide is not a live resource inventory.

## Topology and networking

HTTPS client → public API Gateway HTTP API → VPC Link → internal ALB HTTP:8080 →
active ECS Fargate color → private SQL Server TCP:1433 with strict TLS.
The task calls AWS KMS for text encryption/decryption. Secrets Manager supplies
an exact connection-secret version through the ECS execution role.

The DEV VPC uses `10.0.0.0/16`, public subnets `10.0.0.0/24` and `10.0.1.0/24`,
and private subnets `10.0.100.0/24` and `10.0.101.0/24`. Both ECS colors are
eligible for both private subnets; neither color is permanently active. The
latest documented cold recovery placed SQL in private B. SQL is a single writer,
not a redundant database pair. See [global](../modules/target/dev/global),
[edge](../modules/target/dev/edge) and [app skeleton](../modules/target/dev/apps/ordinary-demo.tf).

Security-group references restrict VPC Link → ALB → application → database.
Application egress permits HTTPS and SQL/1433; the SQL host retains broader
outbound access. Public AWS endpoints use NAT; no runtime VPC endpoints are
configured in this topology. API Gateway has no user authentication. Internal
HTTP is a documented boundary, not end-to-end TLS.

## NAT recovery

Two NAT Instances, each in an ASG with one instance, serve their respective AZ.
ASG launch events invoke three E13 handlers to associate the EIP, replace the
private default route and disable source/destination checking. User data enables
forwarding and masquerading. This is **independent per-AZ replacement**, not
cross-AZ failover or continuous packet-forwarding health checking.

[E13](e13-nat-reliability.md) retains bootstrap/network checks, failure queues
and operational procedures. The [6 November trial](../../docs/SENTINEL-CHAOS-20261106.md)
measured HTTPS recovery in 2m29.191s; Sentinel observed that experiment but did
not perform the recovery. Its runtime has since been retired.

## Ownership, state and deployment

| Owner | Responsibility |
| --- | --- |
| Security administrator / neutral security root | IAM/OIDC, KMS, secret metadata, protected state and storage controls |
| Terraform/Terragrunt environment layers | Shared configuration, secret metadata consumption, global networking/ALB skeletons, SQL EC2, ECS cluster/service skeletons and API Gateway/VPC Link |
| Automatic application delivery | Image build in DEV, ECR digest, task revisions/counts, ALB forwarding, health/drain and release records |
| E13 | NAT private default routes and launch-event recovery |
| Native SQL producer | Hourly backup, local staging/cleanup and exact-version publication |

[Native lifecycle](native-dev-lifecycle.md) uses the existing state owners and
normal locking. Secret values stay outside Terraform state. The security root
and ordinary runtime layers must not compete over authority, and Terraform
must not reclaim delivery-owned service counts/revisions or ALB actions.

[Automatic delivery](../../docs/DEV-DELIVERY-DESIGN.md) uses GitHub environment
serialization, administrative exclusion of other writers and versioned S3
operational state. The old E2 ACTIVE record is preserved and pinned by the
approved handover; it is **not acquired or released by current delivery**.
The [E1 repository contract](e1-final-acceptance.md) and retired-source fixtures
remain acceptance dependencies, not an instruction to reactivate old controllers.

## Runtime and readiness

One essential API container and one nonessential, one-shot `readiness-probe`
container use the same digest. The probe calls loopback `/ready` and must finish
successfully; only the API connects to SQL. Deployment validates every candidate
task, image/revision, ENI and healthy ALB target before moving traffic.

The executor checks the client route after promotion and again before drain,
while retaining the previous capacity for compensation. ALB liveness checks
are not continuous SQL/KMS readiness. ECS/ALB observations are bounded checks,
not an atomic transaction. The [delivery guide](../../docs/DEV-DELIVERY-DESIGN.md)
describes rollback and reconciliation after partial effects.

## CURRENT CONTRACT — application and data

The common Linux image uses .NET 10, UID 1654 and HTTP 8080. Before starting
.NET, its non-root entrypoint prepares environment-supplied public SQL trust;
`validated-v2` is mandatory for the ordinary API. DEV uses the definitive CA,
with `Encrypt=True` and `TrustServerCertificate=False`. The historical SQL-Lab
image and temporary bridge are not the current deployed trust configuration.
See the [SQL trust contract](../../demo-api/deploy/sql-trust/README.md).

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

SQL Server 2022 Express runs on Ubuntu EC2, default t3a.small. The native Data
owner accepts the selected private subnet; the latest cold recovery placed SQL
in B. `recovery_preserve_root_volume=true` retains the encrypted 30-GiB root.
The installed validated-v2 runtime has SELECT/INSERT on DemoTexts and SELECT on
EF history, no db_owner/DDL; the migrator is separate and disabled after handoff.
Startup migrations default off and validated-v2 refuses them. The legacy recipe
remains distinguishable in source and is not the deployed strict profile. Both
colors share the DB. Image rollback does not reverse schema changes.
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

The [SQL backup/restore CLI](../../operations/sql-backup/README.md) provides
COPY_ONLY/CHECKSUM, exact-version S3/KMS verification and isolated restore/CHECKDB.
The hourly persistent producer remains installed; Sentinel observation was retired on 10 November 2026. Seven-day
Lifecycle admission protects the two newest valid pairs; restore inputs need an
independently verified hold. [Native cold recovery](../../operations/sql-backup/recovery/NATIVE-RECOVERY.md)
positively fences the original writer before provisioning and activating a new
host. SAME/CROSS-AZ trials include API/KMS validation and measured RTO; no automatic
SQL failover, transaction-log PITR or abrupt-disaster zero-RPO guarantee is implied.
