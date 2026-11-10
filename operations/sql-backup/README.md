# SQL backup/restore increment

## Current recovery and retention

Use [native cold recovery](recovery/NATIVE-RECOVERY.md) for the implemented host
replacement procedure. Real SAME-AZ **24m42.6s** and CROSS-AZ **41m31.5s** trials
include source fencing, new EC2, restore/CHECKDB and API/KMS validation.
[The dated record](../../docs/V2-RECOVERY-SECURITY-20261105.md#cold-recovery-execution--6-november-utc)
preserves failures and the planned-cutover RPO limitation.

Hourly production is independent of Sentinel: the SQL host runs `host.py` through
`sql-backup.timer`, with a persistent hourly schedule and separate backup/verify
credentials. S3 versions and SSE-KMS remain unchanged. On 10 November expired
producer IAM/KMS time conditions were repaired; a new S3 backup passed SQL
`RESTORE VERIFYONLY WITH CHECKSUM`, followed by an automatic hourly publication.
This did not repeat a full restore.

[Storage verification, retention admission and restore holds](storage/README.md)
remain part of SQL. The former Sentinel observer is retired from the repository;
its AWS resources await separate retirement approval. Existing Lifecycle expires
only admitted older versions; no new automatic admission worker is installed.
The two newest valid pairs and restore holds must remain protected.

The sections below record earlier component/install experiments. Their statements
about absent AWS infrastructure, pending recovery or Sentinel integration describe
those dates, not current operation. Installed producer packages are not replaced
by this source separation; the native recovery installer still verifies its exact
original artifact/version before use.

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


### Published corrected component and receipt qualification - 2026-10-23

Clean source b2bf8d82938e690561a85e45b3ab9e2a383413cf was locally published as
Linux-x64 self-contained .NET 10.0.13 using existing cached packages only and an
offline NuGet source list. The component has 237 files / 133344738 bytes; no application
archive was created. Its executable build-info reports that exact compiled Git
revision without config or credentials. Component DLL SHA256:
d84141e91939f41042f7cb3c0a243e9036a82a676108849da31d556b17571d88.
Versioned local manifest SHA256:
b0a98b236d25fa2d0bcc72269ac42e294276c53603f48945bc99ecfb3664c978.

The actual published Linux executable passed three replay cases through the real
Protocol.Check and local log renderer: FAILED, MISSING and STALE all produced
nonzero CLI status and ATTENTION with Delivery:NONE. Stale uses the unchanged az6
captured receipt, now older than 2 h; failed uses that actual metadata plus an
explicit synthetic local FAILED attempt; missing uses an explicit empty captured
list, not live S3 absence. Every replay says RemoteStorageObserved:false; no SQL,
API, AWS or notification call was made. Original receipts remain untouched.

Full CLI suite: 62 PASS / 1 native SQL integration skip. Nine focused Python tests cover
status/exit/maintenance/unknown/privacy and manifest/source/DLL/extra-file/payload
substitution. The real old 65c7901 tar remains unchanged and was refused with
BUNDLE_COMPONENT_MISMATCH by the current pinned component gate. Archive binding
checks actual backup payload bytes as well as declared manifest hashes. This gate
does not replace whole-bundle hygiene/inspection, IAM review or live acceptance.

The qualification tooling/doc commit may be later than the compiled component:
pin the actual b2bf8d8 source and manifest above, never infer them from latest HEAD.
The next concrete artifact packet must invoke verify-bundle before upload and
execution. Automatic AWS/CI wiring is not installed. Live producer log forwarding,
independent periodic missing/stale checking and confirmed human email/Sentinel
delivery remain open, together with unchanged full EC2/systemd/remote-restore/API
acceptance. No external email or unavailable Sentinel API was configured.


## Independent periodic observer — local implementation 2026-10-23

The [observer runbook](OBSERVER.md) and observer.py implement a finite fresh
read-only check, persistent condition/reminder deduplication and recovery candidates.
Separate inert service/timer proposals have no SQL dependency and leave cadence,
reminders and expected-UP authority explicit. Nothing was installed. Missing,
stale, failed, recovered, maintenance and unknown are covered locally. Real role,
producer ingestion, independent timer operation, Sentinel and mail remain pending.
Producer interval, freshness and retention remain unchanged.
