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
The legacy branch of ordinary SQL user-data still grants db_owner. The new opt-in
branch prepares the separate principals and leaves runtime disabled; it does not
declare strict runtime admission from installation alone. Do not deploy the strict
API profile before the reviewed handoff and schema setup.

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
bootstrap branch/connection generator as hardened merely because a strict opt-in exists.

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

## Bootstrap adoption route - local source and doubles, not applied

TARGET DEV and PROD now expose nullable `sql_database_security`; null explicitly
selects legacy-v1. Opt-in supplies a distinct `migration_user` and an exact metadata
reference `arn:aws:secretsmanager:<region>:<account>:secret:demo/<env>/db/sql-migrator-password-<suffix>`.
There is no secret value in Terraform and no new password generation. The existing
SA/app references stay owned by protected security. The additional secret container,
supplied value and SQL-role exact GetSecretValue/KMS access are NOT created/granted
by this increment. An AccessDenied must stop; never reuse the SA connection as the
application/migrator fallback or substitute another identity.

`sql-principals.sh` is sourceable and inert; its future mutating functions require
root, an explicit reviewed-change acknowledgement, validated identifiers and a
supplied admin process credential. An acknowledgement is not installation authority.
Its SQL port is fixed to local loopback, not an alternate remote transport. Local
administrative `sqlcmd -C` is confined to that bootstrap hop; it is not a remote API
TLS bypass. Password values stay out of argv/output and sqlcmd variable expansion
is disabled. Existing login passwords are never changed on replay.

The reviewed adoption sequence is:
1. The admitted delivery owner quiesces application traffic/tasks and establishes
   exclusive operation ownership. This helper does not fence Fargate or an AZ.
   Native SQL observes no sessions for either login, but that observation alone is
   not an exclusivity proof. Preserve backup/state and establish a viable exit first.
2. Fresh bootstrap creates the database through the existing installation path.
   The opt-in prepare phase consumes supplied password references, creates missing
   logins/users, validates SID bindings and refuses database ownership, server roles,
   elevated direct server permissions, unexpected runtime roles/permissions or
   ownership of securables. It disables runtime and removes only the legacy
   db_owner membership after quiescence. Other unexpected access is refused rather
   than indiscriminately revoked. DDL is transactional; no automatic retry follows
   an error or uncertain result. Read back exact state under admitted authority.
3. The migration identity has database-local db_ddladmin and schema dbo SELECT/
   INSERT/DELETE for EF history maintenance. This is intentionally broader than
   runtime, supports the two reviewed current migrations, and is disabled after
   use. It is not SA/sysadmin and does not have server administration. Review any
   future data migration or UPDATE requirement before expanding its privileges.
4. Install the separately admitted certificate/key on SQL and public trust on the
   clients; provide the strict identity configuration. The exact reviewed migration
   process runs `database-migrate --confirm-schema-change` with only its supplied
   migration connection. No HTTP task startup may perform that operation.
5. Under the same exclusive owner, the activate phase requires runtime still disabled,
   no application/migration sessions, both exact migration IDs, DemoTexts, Text as
   nvarchar(max), and no runtime role membership. It grants only object SELECT/INSERT,
   disables the migrator and then enables runtime. It never auto-enables after a
   failed schema/adoption check. Replaying activation after runtime was enabled is
   refused for readback/reconciliation; this is not unproven automatic idempotence.
6. The strict API startup performs its effective-permission check and the existing
   readiness/public read-write checks must pass before routing. No new callable
   protected deployment action or SSM transport was activated by these functions.

The helper is delivered as a small public gzip/base64 payload with a fixed timestamp,
decoded content matched to its source SHA before sourcing. Regeneration uses the
existing Python `gzip.compress(source, mtime=0, compresslevel=9)` and base64; no remote
download occurs. Exact LF attributes preserve source hashes on Windows/Linux.
Both module paths enforce a conservative 16383-byte combined EC2 user-data limit.
An oversized security/cohost configuration must be reduced/reviewed or its existing
package distribution used; never bypass the limit or truncate configuration.

The real Terraform 1.13.4 template function and Windows Git Bash loader/syntax were
checked locally, with all SQL ports substituted for adoption tests. This proves
rendering/control composition, not SQL engine grammar, transaction behavior, actual
role demotion, native idempotence, certificate installation or Linux qualification.
The final API regression is169/169 PASS on unchanged final C# source.

## Certificate recommendation from actual repository facts

The SQL endpoint currently comes from `aws_instance.db.private_ip`, and the bootstrap
discovers that IP by the demo-<env>-data-sql-instance Name tag. A tag is not DNS or a
certificate SAN. No SQL Route53 name, managed public chain, ACM certificate reference
or SQL certificate distribution is defined in these checked-in paths. No certificate
availability was inferred from the account and no private material was inspected.

Choose the stable logical SQL certificate identity `sql.demo.internal` for this
single-app lab; it is a proposed SAN/name, not a deployed DNS record. Connect to the
reviewed private IP with HostNameInCertificate bound to this name, so no new DNS
zone/record is needed for that override. It requires an actual supplied certificate
and a chain already managed/trusted outside this project; none is currently referenced.
Do not pretend a public CA will issue an internal-only name. If no managed issuer
exists, there is no ready certificate for that chain-validating profile: propose a
separately approved lab server-certificate pinning treatment (not a new CA/PKI) or
an owned public-domain certificate before changing this strict profile. Exact leaf
pinning is an alternative trust model, not proof of CA-chain/SAN validation; it is
NOT implemented or silently enabled here. No certificate/key was generated.

This removes the open naming choice from the owner. The material missing input is
the admissible certificate/trust source and its installation/distribution approval,
not a request to invent SQL/DNS/CA architecture. Internal ALB/task TLS remains a
separate disclosed hop; this SQL control does not secure it automatically.

## Linux environment boundary

Windows SSH is installed, but the visible codex-nat/codex-work configuration uses
an external bastion; it is not a verified local VM workspace. No local VM alias,
host-key binding or mounted project path was available in the known task folders,
and no VM manager command was available. Personal Context returned unavailable.
No connection to that bastion, new login, WSL fallback, host mount/service change,
Linux installation or native SQL command was attempted. A verified authorized VM
destination and mount are still needed for Linux qualification; Windows tests must
not be represented as that qualification.
