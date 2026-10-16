# SQL backup/restore increment

Status: local implementation; no AWS installation. The example configuration is
**PROPOSED**, with synthetic ARNs that must be replaced before any cloud session.
The local milestone did not accept retention, budget, RPO or RTO. On 2026-10-16
the owner subsequently approved the bounded synthetic S3/KMS component drill
and its proposed lab values. Its Linux authentication preflight is
[blocked before resource creation](../../terraform/docs/validation.md#approved-s3kms-component-drill-preflight---2026-10-16).
RPO/RTO remain unmeasured; no schedule or AWS installation exists. The full
EC2/cross-AZ proposal below remains outside that minimum component scope.

Finite acceptance: native SQL Server 2022 **Express** COPY_ONLY/CHECKSUM backup;
separate backup and verifier/restore SQL contexts; private bounded local staging;
SHA-256/size/database/version/key-bound manifest; exact S3 version and SSE-KMS
readback before immutable commit; unknown writes reconciled by exact-key readback
without blind resend; no success heartbeat on partial failure; restore to a new
isolated database without REPLACE, CHECKDB and readable application table; failure,
missing, stale and maintenance states distinguished; no secrets in output.

This first lab increment supports one data file and one log file and refuses
allocated databases/backups beyond the configured bound (512 MiB proposed,
maximum configurable 1 GiB). It never truncates a database or silently relies on
compression. Multipart, differential/log backups, PITR, HA and automated cleanup
are excluded. SQL Express lacks SQL Agent and native encrypted/compressed/S3 URL
backup support; scheduling is external and encryption is local EBS + S3/KMS.

Build/test: the existing app solution includes both CLI and tests. The SQL
integration fact is explicitly skipped unless an isolated Express lab is supplied.
Offline tests never contact AWS; SDK request/response tests use an anonymous
local fake client. The production S3 adapter requires `--aws`, selects only local
profile cnp-cert-dev, verifies account 341936017254, and uses us-east-1 with SDK
write retries disabled. Future EC2 installation instead explicitly adds
`--ec2-role` and must configure ExpectedEc2RoleName: STS verifies that exact
assumed-role name in the same account. Neither credential mode was used against
AWS in this increment; no temporary sessions are copied between machines.

Run the built SqlBackup DLL with `backup --config <private-config>` for local-only
verification. SQL_BACKUP_CONNECTION_STRING and SQL_VERIFY_CONNECTION_STRING are
separate transient environment credentials, never config/argv/log fields. Backup
uses a dedicated login with only db_backupoperator in the source database.
RESTORE HEADERONLY/VERIFYONLY require a separate SQL context with CREATE DATABASE;
that elevated permission must never be given to the application or backup login.
TLS encryption is mandatory and certificate validation is the default. The
explicit `--local-sql-self-signed` exception accepts TrustServerCertificate only
for 127.0.0.1/localhost/::1, suitable for this synthetic lab or a separately
approved co-located SQL process; it never permits an untrusted remote server.

`backup --config <config> --aws` additionally publishes to unique UUID keys with
If-None-Match, SHA-256 and exact SSE-KMS key, reads back bytes and version, and only
then publishes/readbacks manifest.json. It writes the new unique key before
readback: no missing-object preflight GET or producer ListBucket grant is needed.
All S3 requests enforce ExpectedBucketOwner=341936017254. See the
[AWS missing-object permission behavior](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html).
A local .bak or LOCAL_VERIFIED result is
not a remote backup. Failures retain private local files and sanitized state;
there is no automatic deletion or retry of unconfirmed mutations. Rerunning a
whole backup creates a new unique run, never overwrites a previous one.

`restore --config <config> --aws --manifest-key <exact-key> --manifest-version
<exact-version> --target <source>_restore_<name>` downloads the exact backup
version, checks hash/size/SQL header/checksum, refuses existing/source/system DBs,
uses FILELISTONLY logical names with new local data/log paths, runs CHECKDB and
queries DemoTexts. Restored directories are retained for explicit investigation
or cleanup. It does not rebind the application or replace the source.

`check --config <config> --expected-up true` exposes local failure/UNKNOWN;
adding `--aws` checks committed manifests from an independent host. It returns
nonzero for FAILED/MISSING/STALE/UNKNOWN. `--expected-up false` reports maintenance.
The independent checker must remain outside the SQL host failure domain. Native
service logs/exit status expose immediate failure; missing remote commits expose
absence. CloudWatch wiring and real human notification remain pending. No fake
notification or Sentinel integration is installed.

`cloud-preview --config proposed-lab.json` emits reviewable bucket/encryption,
retention and least-privilege policy proposals. It creates nothing. Bucket and
backup key must survive DEV DOWN; retain the original text-encryption KMS key as
well, or restored ciphertext cannot be decrypted. No DeleteObject, state access,
PassRole or broad KMS administration is granted. Versioning, encryption, endpoint
and bucket policy installation require separate protected review/authorization.

Proposed lab schedule: hourly full backup, current-object expiry at two days,
noncurrent-version expiry two days after supersession, stale after two hours
while UP. Versioned data can therefore remain around four days or longer with
eventual expiry; this is not a two-day deletion guarantee. Defaults are
configurable and uninstalled. Freshness conservatively uses backup start time,
not upload completion, so verification/upload latency cannot freshen old data.
RPO would depend on successful interval plus backup/upload duration, and RTO must
be measured by an actual restore drill. No SLA is claimed. Local disk contains
sensitive .bak data: run co-located with SQL as its mssql OS user on encrypted
storage, dedicated private directories, sufficient free space and secret injection
outside Terraform. Remote restore validates SQL only; actual KMS decryption and
application /ready and POST/GET remain future AWS acceptance.


## Reproduce the isolated native SQL test

First build the solution with the pinned SDK. On codex-vm, run
`python3 operations/sql-backup/run-sql-lab.py --accept-sql-eula --source
/mnt/hgfs/CodexDrop/terragrunt_demo --results <existing-private-results-dir>`.
The acceptance flag is a deliberate operator action, not implied by reading this
file. The owner approved this local Express test under the
[Microsoft SQL Server 2022 Developer/Express/Evaluation terms](https://www.microsoft.com/content/dam/microsoft/usetm/documents/sql-server/sql-server-2022-developer-express-evaluation/retail-packaged/SQLServer2022_SQLServer2022DeveloperExpressEvaluation_English.pdf),
dated 2022-10-21. The pinned official image is recorded in the harness. It uses
MSSQL_PID=Express, network=none, no published ports, random process-only passwords
and a fresh labelled volume. Tests run with SQL's actual UID/GID (10001/10001
for this image), private 0700 staging, source/package-cache mounted read-only and
the SDK's VSTest runner directly, avoiding SDK first-use writes under that UID.
The harness refuses insufficient space/memory and existing resource names, and
removes only its own labelled containers/volume in finally, including on failure.
Other SQL containers, caches and volumes are not touched.

The synthetic native test verifies Express engine/backup checksums, a backup login
without sysadmin or CREATE ANY DATABASE, successful restore/CHECKDB/known-row
read, refusal to overwrite the restored DB, rejection of a truncated .bak and
preservation of newer source rows. SQL verification/restore uses a separate
administrative lab connection: production minimum verifier permissions still
need installation review. Storage is an in-memory S3 fake: neither actual S3/KMS
encryption nor application decryption/readiness is proven by this local test.

The `.service.in`/`.timer.in` files are inert proposals. The service uses Requisite,
so it cannot start SQL by itself; it never starts EC2 or bypasses lifecycle
ownership. Publishing a reviewed self-contained Linux artifact, secret delivery,
an accepted EC2 role/bucket/key, external observer and notification wiring remain
separate installation work. A deadline failure retains files and reports failure;
it does not claim remote SQL/S3 cancellation or authorize blind replay.

Primary contracts: [BACKUP](https://learn.microsoft.com/en-us/sql/t-sql/statements/backup-transact-sql?view=sql-server-ver16),
[VERIFYONLY and permissions](https://learn.microsoft.com/en-us/sql/t-sql/statements/restore-statements-verifyonly-transact-sql?view=sql-server-ver16),
[S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html),
[SSE-KMS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingKMSEncryption.html).

## Proposed AWS session - not authorized by this milestone

Use only cnp-cert-dev/account 341936017254/us-east-1 after fresh STS and current
E2/lifecycle checks. The runtime is down; any full original DEV UP must receive
its own scope, reviewed plans and budget approval. Do not reuse old IDs, bindings,
expired temporary grants or the historical E13 uncertainty exception.

Proposed resources: one dedicated retained versioned/private backup bucket, one
backup CMK, scoped producer and observer/restore permissions through existing
protected security administration, and an S3 gateway endpoint on both private
route tables. Install only the reviewed artifact/secret delivery/role binding.
Keep the original text KMS key and existing state/evidence boundaries. SQL login
creation and the separate verifier context also need explicit installation review.

First cloud drill: create one synthetic record through the real SQL/KMS app,
native backup, exact-version encrypted S3 readback, external failure/absence
observation, then restore onto one temporary private SQL EC2/EBS in the other AZ.
Use fresh target files/DB and verify CHECKDB, KMS decrypt and isolated /ready and
POST/GET; never overwrite source or redirect production traffic. Measure recovery
there before deciding RPO/RTO. Human notification requires a separately approved
recipient/channel; no delivery claim follows from a fake or an alarm definition.

Cost proposal, not an approved budget: the backup CMK adds a base
[USD 1/month prorated hourly](https://aws.amazon.com/kms/pricing/), plus key usage.
[S3 charges](https://aws.amazon.com/s3/pricing/) depend on measured .bak size,
storage duration, versions and requests; hourly 512-MiB files with the proposed
2+2-day expiry illustrate around 48 GiB at steady state before eventual-expiry
delays/extra runs. Apply the current regional price to that quantity before the
session. [The gateway endpoint has no extra endpoint fee](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html).
Original DEV runtime, temporary restore EC2/EBS, logs/metrics and requests are
additional variable charges; no zero-cost or total-price promise is made.

Retirement plan must be approved with the session: remove the isolated restore
instance/EBS and its temporary configuration/access; stop scheduled work before
supervised E16 DOWN. Retain backup objects, backup CMK and original text key for
the owner-selected horizon. Deletion, retention changes, IAM changes and another
UP/DOWN remain unapproved; never delete backup keys just to report a zero bill.
