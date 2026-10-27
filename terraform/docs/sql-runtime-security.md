# SQL runtime security increment - 2026-10-27

Local implementation, NOT installed, native SQL/TLS proof, IAM authority or rollout approval.
No password, certificate, private key, CA, SQL grant or trust store was generated or changed.

## Runtime and migration are separate operations

The real repository (`demo-api/terragrunt-demo/Repositories/ITextRepository.cs`) only
selects and inserts `dbo.DemoTexts`. A data-only runtime user therefore needs CONNECT
and object-scoped SELECT/INSERT, not db_owner, schema DDL, UPDATE or DELETE. This is
a permission contract for a later reviewed installation, not a GRANT script.

`Program.cs` now disables startup migrations by default. Legacy startup migration
requires an explicit `Database:RunMigrationsOnStartup=true` setting and legacy-v1;
it is not allowed in validated-v2. Existing legacy credentials/grants are not altered.
The ordinary SQL user-data still grants db_owner; it cannot satisfy the strict gate.
Do not deploy the strict profile before a reviewed permission handoff and schema setup.

The explicit `database-migrate --confirm-schema-change` app operation uses only
`DB_MIGRATION_CONN_STRING`; it never falls back to DB_CONN_STRING, starts HTTP, or
registers KMS. It requires validated-v2, the same endpoint/database/TLS contract and
a different login from `Database:ExpectedRuntimeUser`. It does not need the runtime
password. No migration credential belongs in the web task. Only a future admitted
deployment/migration owner may inject that reference and run this mutating command.
It is NOT wired into an unapproved workflow/task or a way to bypass protected delivery.
The database must already exist; creation and privilege provisioning remain separate.

Current migrations create DemoTexts and alter its Text column; EF also maintains its
history table. Review the emitted migration SQL, schema compatibility with both
colors and exact DB-scoped migration permissions before execution. Do not give the
web task ddladmin/db_owner or use SA/sysadmin for it. Image rollback does not undo
migrations; the existing shrink-to-nvarchar(1000) Down can lose data and is not an
automatic recovery step. The new CLI is not installed migration authority or a
completed deployment-order integration.

## Explicit SQL TLS contract

The opt-in template `demo-api/deploy/database-security.validated-v2.json` is not
automatically loaded; null identity fields intentionally refuse use. An admitted
runtime configuration supplies SecurityProfile=validated-v2, migrations=false,
ExpectedSqlEndpoint (`tcp:<reviewed-host>,1433`), ExpectedDatabase,
ExpectedRuntimeUser and ExpectedCertificateHostName. No example name is operational.
Connection references remain outside state and Git.

Both runtime and migration connection strings must explicitly request Encrypt=True
(Mandatory), TrustServerCertificate=False and the exact HostNameInCertificate.
Unknown profiles, SA, Windows/alternate auth, target/database drift, failover targets,
attach files and arbitrary certificate pin files are refused. The override binds the
certificate identity while the reviewed private target IP may change on recovery;
it does not resolve DNS, install trust or bypass expiry/chain validation.

Supply a SQL server certificate meeting SQL requirements, with the selected DNS SAN,
its private key installed only on SQL under a separately reviewed operation, and an
existing issuer/intermediate chain trusted in every app/migration client image.
Recommendation: use an existing managed/organizational issuing chain and stable SQL
certificate name; do not create another CA/PKI for ECS. Actual SAN, chain, distribution
and renewal evidence are still missing. Native tests must accept the correct chain/name
and reject an untrusted issuer, wrong SAN and expired certificate. No such TLS handshake
was performed in the local configuration tests.

Before serving HTTP, validated-v2 performs a read-only effective permission check.
It requires SELECT/INSERT and rejects fixed elevated server roles, CONTROL SERVER,
login/role impersonation/administration, db_owner/ddladmin/securityadmin, dbo/guest,
database control/create-table/user/role management and object control/alter/update/delete.
Unknown/null/missing evidence refuses startup. This bounded check is not an exhaustive
proof of every effective permission, certificate provisioning, server patching or an
authorization grant. No native SQL permission query was executed in this increment.

legacy-v1 remains explicitly selected in existing appsettings, logs a warning and
does not claim certificate or least-privilege acceptance. There is no fallback from
a malformed or failing validated-v2 profile to legacy. Do not label the legacy
bootstrap/connection generator as hardened merely because a strict opt-in exists.

## Real network paths and bounded egress change

API Gateway -> VPC Link -> internal ALB -> Fargate remains HTTP/8080 internally.
Fargate -> SQL is TCP/1433, already restricted by the DB security-group reference.
Fargate also uses HTTPS for KMS, image/layer retrieval, secret injection and logs.
The existing TARGET DEV/PROD `fargate_egress_any` rule now allows only TCP/443
to 0.0.0.0/0, retaining its address and the separate exact SQL rule; no resources
or inbound permissions are added. This limits ports, NOT remote domains or all
exfiltration. AmazonProvidedDNS is not filtered by security groups. Additional
associated SGs can broaden access and must be checked in a future real plan.

SQL host bootstrap uses APT HTTP/HTTPS, Microsoft HTTPS packages, AWS HTTPS for
secrets/backups/events/logs/SSM, plus DNS/time. Its existing broad egress and NAT
forwarding are not silently narrowed to 443: doing so would break installation or
traffic. No new endpoints, proxy or network architecture is invented here.
Internal ALB TLS still requires certificate/listener/client trust/routing work;
changing a protocol boolean alone would not secure it. Before that change, bind an
existing ACM certificate/name and API Gateway integration TLS serverNameToVerify,
and separately decide whether ALB->task remains the documented private HTTP hop
or receives an approved certificate at the task. Do not claim full-path TLS now.

## Admission, validation and rollback

The strict profile requires supplied certificate/name/trust and a reviewed permission/
migration handoff. These are inputs to one future install/deploy review, not new
cloud authorization in this increment. No protected caller approval, secret read,
grant, role, SG, service, timer or host was activated. SSM diagnostic denial and
retirement prohibitions are unchanged; the migration CLI is not an alternate transport.

Local tests use synthetic connection strings and permission results. The compiled
Windows CLI refusal test proves rejection before a migration, not Linux packaging or
native migration success. Existing native receipts remain historical. API source has
changed, so the previously sealed recovery tar/image cannot represent these repairs;
keep it immutable and qualify a new Linux API artifact only in the next coherent build.

Rollback is a separately reviewed image/config change. Never silently fall back to
TrustServerCertificate=True, inject migration credentials into runtime, auto-downgrade
schema, or restore db_owner to pass a health gate. A legacy rollback has an explicit
unresolved security posture, not acceptance of the new controls.

Primary references:
- [EF deployment and separate migration identity](https://learn.microsoft.com/en-us/ef/core/managing-schemas/migrations/applying)
- [SqlClient encryption, chain/name validation](https://learn.microsoft.com/en-us/sql/connect/ado-net/encryption-and-certificate-validation)
- [ECS network paths and TLS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-network.html)
- [SG rules, aggregation and DNS limitation](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html)
