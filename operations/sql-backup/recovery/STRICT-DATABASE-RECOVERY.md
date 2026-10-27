# Strict database recovery — local opt-in, not native acceptance

Implemented after `7e0ac5b5dc0275f64e90faa84491f3455a81b537`, 27 October 2026. This connects the already-reviewed API `validated-v2` policy to source/restore, private connection publication, offline Fargate rendering and the protected WP4 V2 projection. No new transport, PKI, credentials, SQL server, grants, trust installation or cloud resources were executed or created.

## Contract and exact sequence

The optional `DatabaseSecurity` object contains only these five fields:

| Field | Required value |
| --- | --- |
| Profile | `validated-v2` |
| RuntimeUser | `recovery_app` (existing synthetic recovery identity) |
| MigrationUser | `recovery_migrator` (separate identity) |
| CertificateHostName | `sql.demo.internal` |
| MigrationSecretArn | Actual admitted `demo/dev/db/sql-migrator-password-<six-character suffix>` ARN in account 341936017254/us-east-1; no password in this file |

Missing/wrong fields, wildcard names, SA runtime identity, wrong secret purpose/account/region or an unsupported profile are refused. The default historical loopback drill remains explicit legacy compatibility. Supplying a strict object never falls back to it. A newly written **private** application connection requires strict mode; historical legacy service plans remain reviewable metadata, not a way to write another unvalidated private connection.

For host `source`/`restore`, the existing execute/trial/host/hash/private-directory gates still apply. New `--database-security FILE --database-security-approved-sha256 SHA256` binds the exact metadata bytes; its hash is an acknowledgement, not owner authorization. Default plan mode still constructs no port and reads no credentials. No command was sent through SSM, SSH or another principal during development.

Strict source flow: create the synthetic database, use the existing public `sql-principals.sh` prepare function, run the API's separate `database-migrate --confirm-schema-change` CLI, activate the minimal runtime via the existing helper, then start the web process with migrations off. Strict restore: preserve existing source-fencing and restore/CHECKDB gates; bind the two restored users to newly supplied logins on the new host; prepare/migrate/activate in the same order; then validate recovered markers/read/write. Unknown migration/helper outcomes do not retry or activate runtime. This is an explicitly admitted migration phase, never web-startup migration or a promise that arbitrary schema upgrades are rollback-compatible. The helper's exact two migration IDs/schema checks remain intact.

The admin/helper `sqlcmd` path uses `-N -F sql.demo.internal`, with **no `-C` in strict mode**. Runtime and migration SqlClient connections use:

`Server=tcp:<bound endpoint>,1433;...;Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.demo.internal;`

No ServerCertificate pin, trust callback, automatic root generation or hostname fallback is added. The existing backup client receives the same validated TLS connection and omits `--local-sql-self-signed` in strict mode. The original self-signed loopback exception remains only in the historical legacy branch.

The migrator process receives only its own DB connection; the API receives only the runtime connection. The strict process environment excludes inherited DB connections, migration credentials and static AWS credentials. Runtime remains disabled during migration; helper activation disables the migrator before enabling the limited runtime. The helper is bundled as reviewed public source and hash-bound before invocation. No key/certificate private material is added to the bundle.

## Delivery and evidence binding

`prepare.service_plan` and `service_taskdef` project the API's five existing security settings plus migrations-off. `render-demo-api-taskdef.sh --recovery --database-security-plan FILE` renders the same projection using real Bash/jq; use the reviewed service input file, not the placeholder printed in the dry plan. Endpoint, database, image and pinned secret version must match. No migration secret reaches a task definition or readiness sidecar.

Protected WP4 V2 accepts the option only inside its admin-only/current protected recovery binding, not public gateway parameters. Its verifier evidence must contain the matching security-object hash, `RUNTIME_MINIMAL_MIGRATOR_DISABLED`, and a nonempty SHA256 reference to a real SQL TLS receipt. The final native verifier/owner must supply and authenticate that receipt; this change does not manufacture it from JSON. The entire approval/evidence fingerprints, source fence, qualified release, exact secret version, expiry, E2/E3 and task model checks remain mandatory. Altered security environment is rejected. V1 and explicit legacy V2 fixtures remain compatible; nothing installed has been upgraded.

A strict source receipt is required for strict restore; an old legacy receipt cannot be relabelled as a successful strict experiment. The old az6 142.63s prepared-target result, Fargate A→B→A history and original archives remain historical evidence. They are not requalified by this code change.

## Local qualification and remaining gate

154 affected Linux tests passed with zero failures/skips: strict composition7, historical recovery37, cold execution4, connection-version10, service-plan10, actual Bash/jq renderer9, POSIX entrypoints4, bundle-runtime3, existing principal primitives8, runtime precheck27, private listener10, listener transition11 and protected V2 compatibility14. The actual jq1.8.2 was reused from the approved isolated cache; no software was installed. WSL source snapshots were hash-compared byte-for-byte. Seven focused strict tests and14 protected V2 tests also passed on Windows; these duplicates are not added to154.

The first Linux snapshot omitted the unchanged public `.gz.b64` fixture, causing one fixture-file error in the8 principal tests; the failed log is preserved. A small hash-recorded supplement added it, and the full8-test suite passed. A new strict test and its final small input guard were requalified on the final snapshot. This is test-harness correction, not SQL or AWS recovery evidence. The existing offline CI runner now explicitly includes strict recovery and principal suites; `--list` is discovery only, not extra executed acceptance.

No SQL Server was installed or connected. No SQL user/grant, secrets, certificate key, OS trust, AWS policy or network configuration was changed. The API source and qualified lab-trust Linux image are unchanged by this increment; no image rebuild was necessary. The existing self-contained recovery archive is historical and was not repinned: a new runtime bundle must bind the current API source/dependencies, current host source and this public helper before an admitted trial.

Required native prerequisites remain: install the already-generated lab certificate/key on the exact SQL node through an explicitly admitted confidential distribution path; supply public trust to each SQL client that runs on that node and the qualified API image; create/reference a separate migrator credential and exact read access; verify actual SQL chain/name/expiry and least-privilege grants; install the reviewed strict protected binding and qualified immutable image; admit SQL execution/fencing/restore transport. Failure in any of these blocks activation. The unexplained b2/d1 SSM rejection was not retried or declared fixed.

The grouped future access/control scope remains the one in [NATIVE-PREREQUISITES-20261027.md](NATIVE-PREREQUISITES-20261027.md): three missing infra/emergency CodeBuild projects and three gateways plus associated protected resources, exact Part4 deny exceptions/portable lifecycle Allows/backend prefix, four portable workload roles and boundaries, SQL-role EventBridge/artifact grants, separate migrator-secret read and confidential TLS handoff. Those are proposed changes, not effective rights. Final creation/retirement plans, current identities and a full new cost ceiling remain mandatory; no old102/135 count or USD6 budget becomes approved here.

Microsoft documents sqlcmd `-F` as the expected CN/SAN for normal certificate validation and `-C` as trusting the server certificate: [sqlcmd utility](https://learn.microsoft.com/en-us/sql/tools/sqlcmd/sqlcmd-utility?view=sql-server-ver17). This preserves the existing SqlClient name/chain-validation policy; runtime proof still requires a real handshake.
