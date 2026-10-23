# SQL backup/restore increment

Current status - 2026-10-21: native/S3-KMS component qualification and real
EC2-role manual plus two hourly backups passed. The temporary service/runtime
was retired; residual network closure and permission removal completed that
evening. See [dated evidence](../../terraform/docs/e16-ec2-backup-trial-20261021.md).
No EC2 service or scheduler is currently installed. The example configuration is
**PROPOSED**, with synthetic ARNs that must be replaced before any cloud session.
The local milestone did not accept retention, budget, RPO or RTO. On 2026-10-16
the owner subsequently approved the bounded synthetic S3/KMS component drill
and its proposed lab values. The subsequent
[real cloud component qualification](../../terraform/docs/validation.md#sql-s3kms-component-qualification---2026-10-16)
used Windows AWS and Linux SQL without credential transfer; the Linux-profile
preflight remains historical.
RPO/RTO remain unmeasured. The older proposed AWS session below is historical;
the [isolated recovery packet](recovery/RUNBOOK.md) prepares the remaining SQL/API
cross-AZ proof without repeating hourly acceptance or recreating ECS delivery.

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
compression. Multipart, differential/log backups, PITR and HA remain excluded. The subsequent
local service increment below adds only remote-confirmed owned-file cleanup. SQL Express lacks SQL Agent and native encrypted/compressed/S3 URL
backup support; scheduling is external and encryption is local EBS + S3/KMS.

Build/test: the existing app solution includes both CLI and tests. The SQL
integration fact is explicitly skipped unless an isolated Express lab is supplied.
Offline tests never contact AWS; SDK request/response tests use an anonymous
local fake client. The production S3 adapter requires `--aws`, selects only local
profile cnp-cert-dev, verifies account 341936017254, and uses us-east-1 with SDK
write retries disabled. Future EC2 installation instead explicitly adds
`--ec2-role` and must configure ExpectedEc2RoleName: STS verifies that exact
assumed-role name in the same account. The original local milestone did not use either mode against AWS. The later
component drill used explicit minimum-role sessions on Windows; native Linux
profile/EC2-role installation remains unverified. No sessions were copied between
machines.

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
the local service can delete only its own older .bak after fresh remote proof;
there is no deletion or retry of unconfirmed mutations. Rerunning a
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
The independent checker must remain outside the SQL host failure domain. When
the configured local last-attempt.json is FAILED, both local and remote-enabled
checks now return FAILED/LAST_ATTEMPT_FAILED, even if an older remote commit is
still recent. Maintenance suppresses the signal without erasing failure evidence;
a later verified backup clears it through the normal attempt-state transition.
An independent host without that local file can only assess remote freshness:
HEALTHY/RECENT_REMOTE_COMMIT does not prove no later producer failure occurred.
It therefore still needs a separate producer failure signal from service logs/
exit status. Missing/stale remote commits expose absence independently. CloudWatch
wiring, periodic independent execution and real human/email notification remain
pending; no fake notification or Sentinel integration is installed. See the
[consumer state contract](../../terraform/docs/v2-local-completion.md#backup-alert-consumer-contract).

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
outside Terraform. The CLI restore validates SQL only. The subsequent component drill separately
proved real KMS decrypt of restored synthetic ciphertext; application /ready and
POST/GET remain future full-application acceptance.


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
preservation of newer source rows. The service increment additionally verifies
a separate verifier login: denied before a master CREATE DATABASE grant, then
HEADERONLY/VERIFYONLY successful with sysadmin=0 and dbcreator=0, while source
SELECT remains denied. Restore still uses the separate administrative lab
connection; minimum restore permissions and real host login installation remain
unqualified. Storage is an in-memory S3 fake: neither actual S3/KMS
encryption nor application decryption/readiness is proven by this local test.

The `.service.in`/`.timer.in` files are inert proposals. The service uses Requisite,
so it cannot start SQL by itself; it never starts EC2 or bypasses lifecycle
ownership. The subsequent service increment below supplies a self-contained Linux package. Secret delivery,
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

## Local service increment - 2026-10-16

Owner scope: implement source, scripts/templates, local commit and isolated SSH
fixtures only. No AWS calls, deployment, push/merge, persistent host installation,
credentials or security changes occurred. `windrose-sql` remained untouched.
Hourly/two-hour stale/2+2-day expiry are the previously accepted lab settings;
RPO <=70 minutes and component RTO <=30 minutes remain unmeasured objectives.

`cleanup --config <config> --aws --ec2-role` acquires the CLI operation lock and
keeps two verified local backups by default (`RetainLocalVerifiedBackups`, 1..10),
including the last-success pointer. It considers only UUID directories with an
exact matching `owner.json` and a valid committed receipt. Before deleting an
older `database.bak`, it rereads the exact S3 manifest and backup versions and
checks KMS identity, manifest equality, size/SHA-256 and the local file hash.
Only that owned .bak is removed; receipts/metadata, SQL data, restored databases
and all S3 versions remain. No DeleteObject grant is needed. Legacy directories,
foreign entries, changed files and unconfirmed failures are preserved. Old failed
directories can accumulate: this is bounded deletion of confirmed backups, not
a guarantee of bounded total disk usage. The existing free-space reserve refuses
new work when exhausted; an operator must investigate retained failures.

`host.py run --config <config> --executable <absolute-binary>` holds one private
flock across backup plus cleanup. It requires REMOTE_VERIFIED before cleanup and
does not report job success on partial cleanup. Two SQL connection values are
read from private systemd `CREDENTIALS_DIRECTORY` files named `backup-connection`
and `verify-connection`, passed only to the backup child, then removed from the
cleanup child's environment. Captured child output is not logged. AWS is the
explicit EC2-role path with exact role/account checks; no profile/session is
copied to Linux. IMDS/role execution remains untested on a real EC2 host.

`host.py inhibit --config <config> --wait-seconds 600` first fences future wrapper
runs, then waits for the current whole job without killing it. A wait timeout
leaves inhibition in place. `status` exposes the local state; `resume` is an
explicit operator action. STARTED/UNKNOWN from an interrupted/deadline job blocks
the next activation until review and explicit resume. Resume does not replay work
or certify remote SQL/S3 cancellation. INHIBITED_LOCAL_IDLE certifies local wrapper
idleness only, never SQL quiescence or global E2 ownership. Direct CLI invocations
outside this wrapper are not inhibited. No E16 hook or installed DOWN integration
is claimed; preserve existing lifecycle authority.

The inert service uses Requisite=mssql-server.service, no Restart, private staging,
LoadCredential, read-only system protection and a 1300-second outer bound. It
cannot start SQL or EC2. After an authorized installation, first verify SQL is
ready and run one successful manual service backup before enabling the hourly
timer. Persistent=true permits one catch-up activation; it cannot recover missed
hourly RPO or prove startup SQL readiness. Failure and missing-commit observation
still need the independent observer and an approved human notification channel.

`package.py build --publish-dir <self-contained-linux-x64-publish> --out <new.tar>
--source-commit <40-hex-commit>` verifies runtime 10.0.13 and required apphost/runtime
files and writes a deterministic tar with file hashes/modes and a source commit.
Use SDK 10.0.402 and `dotnet publish -c Release -r linux-x64 --self-contained true
-p:RuntimeFrameworkVersion=10.0.13`. The package still requires compatible Linux
native libraries (including ICU/OpenSSL), Python 3, systemd and local SQL.

`package.py install --package <tar> --expected-sha256 <reviewed-sha256> --config
<public-config> --service-user mssql` produces an INSTALL_PLAN by default. Config
has no secret fields; replace every proposed-lab placeholder before real use.
It checks archive traversal/links, digest/inventory, exact role/key syntax and
existing unmanaged targets. `--apply --root <existing-isolated-fixture>` stages
files without services/credentials; the same package/config returns
ALREADY_INSTALLED, while drift/replacement is refused. It is not an upgrade or
uninstall framework. Keep a failed partial install for investigation.

Actual `/` application additionally requires root and
`--confirm-host-install <same-reviewed-sha256>`. No such application occurred.
Its concrete future changes are root-owned `/opt/terragrunt-demo/sql-backup`,
root:service-group 0640 `/etc/terragrunt-demo/sql-backup/config.json`, two 0644
units under `/etc/systemd/system` and service-owned 0700 staging. The installer
never calls systemctl or creates logins/credentials. Separately authorize and
review any real host ownership changes, SQL login/grants, runtime credential
delivery, EC2 role/key-policy binding, daemon-reload, manual service start and
timer enable/start before executing those installation actions.

Validation: 104 app tests, 51 backup offline tests, 12 Python host/package fixtures
and one native Express fact passed. Fixtures cover two accelerated executor
activations, concurrency, startup SQL unavailable, failure, low space, private
permissions, inhibition/wait/resume, deadline fencing and inert/idempotent install.
Unprivileged writes were exercised only inside a temporary container. Units passed
systemd-analyze static verify in a temporary root; no PID1 manager or real hourly
timer was run. A real self-contained package passed temporary staging, idempotence
and cloud-preview on codex-vm. See [qualification](../../terraform/docs/validation.md#sql-backup-service-local-qualification---2026-10-16).

## EC2 installation preparation - 2026-10-16

The owner authorized the next source/read-only preparation. The
[installation approval packet](EC2-INSTALL-REVIEW.md) groups exact retained
storage/role changes, private host credentials, original two-AZ global/data
activation, gateway endpoint, four-hour qualification and retirement. Nothing is
installed by this preparation. ec2_snapshot.py reads only metadata/pricing;
ec2_prepare.py renders review JSON offline; ec2_credentials.py plans by default
and has explicit root/approval/package/instance-role guards before secret or SQL
access. Credentials would persist root-only on encrypted EBS and be injected by
systemd LoadCredential; no new Secrets Manager secret is proposed.

Current AWS reads show the original runtime absent. Do not adopt the default VPC,
invent resource IDs, overwrite existing policies, place IAM in an ordinary root
or treat generated endpoint Terraform as E1-admitted source. The new operational
prefix is isolated from the retained historical drill. Real co-located CLI and
two actual hourly timer activations still require grouped owner approval and a
fresh original E16 saved-plan/identity/network reconciliation. The independent
observer, cross-AZ restore and full application deployment remain outside scope.

## Approved execution checkpoint - 2026-10-16

The owner approved the grouped 8009b21 installation/retirement request. The first
fresh E16 execution attempt is paused before runtime creation: native Terraform
state read failed, and the existing historical SDC retirement guard needs a fresh
owner risk disposition. No old exception was reused. See the
[evidence and exact resume boundary](../../terraform/docs/validation.md#approved-ec2-backup-execution-preflight---2026-10-16).
No timer, credential or AWS security change was installed; the approved four-hour
runtime window has not started. Automatic review rejected reading/storing the
potentially sensitive diagnostic, so a human sanitized error summary or explicit
bounded diagnostic approval is needed before that investigation continues.

## Local human-review candidate - 2026-10-17

The [concrete privacy diff and human step](LOCAL-PLAN-REVIEW.md) replace outer-only
stderr discard with explicit discard in the canonical E16 process too, and
metadata-only plan output. The wrapper defaults to review-only. These are local
source edits and mocked checks, not a retry or tool-review clearance.
The new bounded historical UNKNOWN disposition is recorded, preserving the journal,
UNKNOWN and all other controls; it authorizes neither apply nor deletion. Exact
binding to any fresh execution configuration remains necessary. Runtime is still
absent and no four-hour billable-runtime window has started.


## Local signal and versioned component qualification - 2026-10-23

`SqlBackup build-info` returns only component/revision/informational version;
no config, SQL credential or AWS resolution. A Linux-x64 self-contained publish
must pin runtime10.0.13 and SourceRevisionId to the reviewed clean Git commit.
`local_release.py create` inventories every published file and binds that binary
identity to the commit. `verify` requires BOTH the separately pinned manifest
SHA256 and source commit. `verify-bundle` additionally checks the full archive
SHA256 and compares every backup file/source binding in its bundle manifest.
Old manifests, substituted DLLs and older bundles refuse. These are local
preparation gates; no automatic AWS/CI enforcement or signed attestation is claimed.
The next trial's concrete packet must pin and invoke this check before publication
and execution. Old65c7901 is preserved and cannot be called the current component.

`replay-check --config <config> --receipts <captured-receipt-array> --expected-up true`
executes the real Protocol.Check with a read-only captured-metadata store, never
S3/SQL. Output explicitly says LOCAL_RECEIPT_REPLAY/RemoteStorageObserved:false.
Use original captured receipt metadata to qualify parsing/staleness; an empty
array demonstrates only missing captured evidence, not actual remote absence.
A staged synthetic FAILED Attempt tests producer-failure precedence; label it as
such and preserve originals. No restore/download/write is supported by this store;
--aws/--ec2-role refuse in replay mode. Live checking remains the existing explicit
--aws path and needs its own authorized observation and independent failure domain.

`signals.py health --receipt <Health.json> --observed-at <UTC> --exit-code <0-or-1>`
or `signals.py job --receipt <last-job.json> --observed-at <UTC>` renders bounded
sanitized local log JSON from existing source-defined fields. Status/code/exit
must match; unknown/future/oversized/duplicate/private-field inputs refuse.
STARTED, UNKNOWN and OPERATOR_RESUMED are never success. Every output says
LOCAL_RECEIPT_REPLAY, Delivery:NONE, SentinelIntegrated:false and
RemediationAllowed:false. This is not a Sentinel API or email sender.

Inspection found existing service stdout/stderr/private last-job state and inert
CloudPreview monitoring proposals, but no backup metric/log forwarding, independent
periodic checker or confirmed notification channel. Existing ordinary infrastructure
SNS/alarm declarations do not install backup producers/observers. Real alert
delivery still needs those bindings, maintenance/freshness semantics and explicit
installation/channel approval; private Sentinel source/contracts remain unavailable.
No cloud permission, external email, upload or deployment was configured here.
