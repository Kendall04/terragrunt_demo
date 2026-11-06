# ECS V2 recovery and security work — 5 November 2026

This is the current implementation/evidence record. It supplements the successful
[DEV deployment](DEV-V2-20261105.md); historical recovery fixtures are not evidence
of a new cold recovery. Starting main: `a913a822492b633784eda15758d1feaf43a7c051`.

## Live inventory, 22:39 UTC

AWS account `341936017254`, `us-east-1`, authenticated administrator
`cnp-cert-admin`. One SQL Express host is active in AZ A, two NAT instances are
healthy in A/B, and ECS blue has one running task; green has none. Native state
serials: security 71 (161 managed + 2 data), shared 3, global 37, data 11,
platform 5, apps 12, edge 20. No persistent backend locks were found.

The SQL readback found SQL 16.0.4305.5 Express, two applied EF migrations,
one application row, runtime enabled and migrator disabled. The previous isolated
restore remains read-only. There was no installed hourly backup package, timer,
or dedicated backup login. The existing versioned SSE-KMS backup bucket had no
current objects under the DEV prefix. Prior local restore success did not provide
an operational remote backup policy.

## Architecture decision

Keep one active SQL writer. SQL Express is a recoverable single node, **not** a
high-availability database. Two NAT instances protect egress per AZ, but do not
make SQL or a single application task highly available. The private subnets and
SQL security group already support selecting A or B for a new SQL host.

Use the existing COPY_ONLY/CHECKSUM producer, immutable S3 versions, existing backup
CMK and restore/CHECKDB implementation. A cold recovery must positively fence the
source before allowing a recovered database to accept writes. Network failure or
an unreachable SSM agent is insufficient. Preserve the original encrypted disk
and remote backups; do not rely on the current root disk's delete-on-termination
default. Terraform owns the SQL instance and skeletons; the deployment procedure
owns ECS task revisions, desired counts and listener forwarding.

The planned recovery starts its RTO clock before fencing/provisioning. It ends
only after application read/write/decrypt tests against the recovered database.
Measure actual backup timestamps for RPO; the configured hourly interval is not
an RPO guarantee. An emergency backup taken after writes stop must be labelled as
a planned-cutover optimization, not disaster RPO evidence.

## Backup policy and progress

- Hourly full COPY_ONLY backup, native CHECKSUM/VERIFYONLY, then encrypted
  create-only S3 upload and exact VersionId/hash readback.
- RPO target: one hour plus backup/upload duration; alert threshold: two hours.
- Proposed retention: seven days for this new experiment prefix. No old object,
  version, lifecycle rule or Sentinel journal is to be deleted or rewritten.
- Initial RTO engineering target: 60 minutes including provisioning. **Unmeasured**
  until the complete cold test succeeds.
- Runtime role: own backup prefix and exact package version only; no S3 delete,
  IAM mutation, secret creation or access to another backup prefix.
- New strict credential-bootstrap mode uses `sqlcmd -N -F sql.demo.internal` and
  SqlClient `TrustServerCertificate=False`. Historical explicit lab mode remains
  separately identified. The strict mode passed 29 focused Linux tests.

The producer package was built from `93d4f877178569515c3edaa23c1d0280002b4443`
with SDK 10.0.402/runtime 10.0.13. Its RID-independent dependency graph was first
restored in locked mode; the isolated linux-x64 restore was compared with that
graph before publishing. The source lockfile was unchanged.

### Actual installation and automatic backup

The host installation completed at approximately 23:01 UTC. Package SHA256:
`7658cb3ac4b226d1ee069a24e6e862d3435c8862bad40bee8444eeefeb52fa40`,
authentic S3 version `BkdqGclnbSplQTmo66qIF40pFWsruFrR`. The first manual service
run completed a remote-verified backup with SHA256
`0f27defbf8cc2ecb0438af48b0a2c5487af5a9924ae1f9a2ede4292d11cf956d`.

The next run was **automatic**, triggered by systemd at
**2026-11-06 00:00:02 UTC**, completed at 00:00:05 with exit 0 and
`REMOTE_VERIFIED_CLEANUP_VERIFIED`. Backup SHA256:
`8f58c3f70dae6b88a8a3e56389b13685c081c7fb20a24bb675c78e6638c9dd88`.
Readback showed `Persistent=yes`, `UnitFileState=enabled`, `ActiveState=active`
and next trigger 01:00 UTC. This proves one scheduled execution. Persistence is
configured; an actual reboot of the active database has not been performed.

The producer grant expires at the existing laboratory closure, 7 November
04:00 UTC. Seven-day retention is a **proposal**, not an installed deletion
policy. Existing lifecycle rules and old backup versions were not altered.

### External observation

Nine resources were added under the existing portable Sentinel owner, without
another EC2: a read-only Lambda, its bounded role/boundary/policy, log group,
asynchronous retry configuration, schedule, target and invoke permission.
The observer runs every 15 minutes and checks the newest committed manifest,
its exact S3 version, complete backup bytes, SHA256 and SSE-KMS identity. It
reports the original backup start time, not a fresh timestamp pretending that
an old backup is current. Missing/invalid/unreadable backups are never success.
The existing Sentinel freshness threshold is two hours.

The first real observation produced audit
`f78e03a1b1b6ffd8a2ae1d9600d33a64ea816602387ab5544800e1fbdd54d8ec`.
Its archive and resolution effect both reached `Confirmed`, each with one attempt.
Archive S3 version: `GhqLWf3JlAT7KaA8fys70hXgqvowKXE7`; SSE-KMS readback matched
the existing backup/archive CMK. Journal revision 78 completed at 23:43:30 UTC,
with no owner/lease and zero consecutive failures. Worker invocations used
25–50 requests, within the unchanged 64-request/four-job profile. The four
historical permanent failures are byte-identical; no journal reset occurred.

These are real storage/processing observations, not a new SQL restore or an inbox
receipt. The prior owner-confirmed notice remains the separate inbox evidence.
Current Sentinel/observer permissions expire **6 November 02:00 UTC**, earlier
than SQL/NAT closure. This trial configuration is not a permanently maintained
monitor. Continuing beyond that timestamp requires a reviewed bounded renewal
or inhibition; it must not silently become an expired, failing scheduler.

### Preserving the source disk

Data's native DEV owner now accepts `recovery_preserve_root_volume=true` without
changing the existing Terraform address. AWS confirms that the original encrypted
30-GiB root disk has `DeleteOnTermination=false`. Data state is serial **14**,
version `pUsCU_YdMeoV92wsOTVGZ3tL9qcKKgj1`, with no persistent lock.

Two initial attempts exposed separately missing volume-attribute and volume-tag
permissions. Each stopped and was reconciled by readback; neither failure was
hidden. Exact-volume, expiring inline grants were installed, followed by reviewed
plans. The final successful operation changed only the remaining tags. Part6,
boundaries, Deny and other roots were preserved.

The prepared CROSS-AZ plan is
`6a45412c7ba4af2401c79f4db8725e36b9d572be8ac9c5a9660dca0fc556c417`:
one SQL instance replacement into private subnet B and three alarm dimension
updates, no drift. **Not applied**: database interruption and the additional
USD 3 recovery reserve are awaiting the owner's decision. Neither a plan nor
local tests establish cold-recovery RTO/RPO. The retained disk is an additional
safety asset, not a second active database or an automatically authorized rollback.

## Reproduced security findings

Pinned TFLint 0.64.0 and tfsec 1.28.14 scanned a clean tracked export of the starting
main. TFLint reported 24 warnings and tfsec 46 findings, exactly matching the
existing baseline. The checker and tolerances were unchanged.

| Finding family | Count | Readback / classification so far |
| --- | ---: | --- |
| TFLint required_version | 7 | Child-module metadata; native owner version pinned |
| TFLint deprecated index | 1 | Maintainability; not an AWS vulnerability |
| TFLint unused declaration | 14 | Unused metadata; no effective authority |
| TFLint required_provider | 2 | Child-module metadata; provider locks pinned |
| tfsec S3 encryption | 7 | Five installed security buckets use SSE-S3; encryption-missing reports do not establish plaintext storage |
| tfsec S3 CMK | 7 | SSE-S3 versus CMK is a real key-control distinction, not missing encryption |
| tfsec S3 logging | 7 | Installed buckets have no access logging; no permanent CloudTrail trail/event data store found |
| tfsec S3 versioning | 7 | Five installed security buckets have versioning enabled; static JSON references were not resolved |
| tfsec ECR scanning | 18 | All 14 installed relevant repositories have scanOnPush enabled; uninstalled declarations require separate classification |

The initial deployed image had 12 HIGH entries (six CVEs counted for binary/source
packages), four MEDIUM, two LOW and three UNDEFINED. The latter were real CA-bundle
and XZ advisories, not harmless missing labels. Exact Ubuntu fixes were included
for APT, PCRE2, zlib, CA certificates and liblzma. The final image is:

`341936017254.dkr.ecr.us-east-1.amazonaws.com/demo-dev-shared-demo-ms@sha256:5c4a1108170482089ca832e9ce3102d5f49e3b320675189d7773ddc52deef219`

ECR basic scan: **COMPLETE, zero findings**, at this dated scan. ECS blue revision
13 completed deployment with zero failed tasks; green remains at zero. The image
runs as UID 1654 and preserves the exact public SQL certificate/trust. Live
`/health` and `/ready` returned 200; a new synthetic POST/GET round trip at
00:01 UTC passed SQL and KMS and preserved prior rows. No SQL privilege or schema
change was made for this image update.

NuGet's vulnerability audit of all four solution projects, including transitive
dependencies, returned no known vulnerable packages using the official feed.
This does not prove absence of undisclosed vulnerabilities. The actual trust
boundaries, IAM composition, scanner limitations and residual risks are detailed
in [the security review](V2-TRUST-AND-THREATS.md).

## Costs and operational boundary

Fresh AWS price quotes: t3a.small Linux $0.0188/hour; t3.micro $0.0104/hour.
Cost Explorer's account-wide, estimated daily values are not attributable spend
for this execution and are delayed. New producer installation is modelled at
at most $0.15 for package/storage/requests within the current window, excluding
already-running resources. A fresh recovery trial needs a separately reviewed
incremental estimate and explicit permission to interrupt the active database.

The existing reserve begins **2026-11-07 02:30 UTC**, with closure by **04:00 UTC**.
This work does not extend either time. Retained disks/backups continue to cost
money after compute stops. Their deletion is not implicitly authorized.

Private evidence is retained in `v2-recovery-security-20261105-01`: authentic
inventory/state metadata, SQL readback, policy before/after documents, package
receipts and unmodified scanner outputs. No passwords, private keys or raw
database contents belong in this repository.

## Native recovery preparation and validation status

The [native procedure](../operations/sql-backup/recovery/NATIVE-RECOVERY.md)
uses the existing Data root and exact published backup package. Read-only AWS/SQL
inspection passed: three rows, exact two migrations, expected Express identity,
runtime enabled, no concurrent SQL session at the sampling instant. A client
argument error (`sqlcmd -y 8192`, maximum 8000) was found before SQL execution and
corrected to 8000; the corrected real readback passed. No source fence or compute
replacement has been executed in this session.

The Linux recovery/portable suite passed **288 tests in 23 suites, zero skips**
using the existing local CI image, with no network/credentials. The isolated
Sentinel Terraform mock suite passed **23 tests**. These counts do not certify a
cold AWS recovery. Full E1/remote CI results are recorded with the eventual PR.

The bounded Sentinel renewal plan is
`a0361292511ddd7de0fcff378bbc2c3bb458dca9219969edc0d2abad270e0ab4`:
five in-place updates, zero drift, only existing grant dates and observer expiry.
Three existing external KMS statements need the same expiry change. It is
**not applied**: automatic approval review requires explicit owner confirmation.
The proposed end remains 7 November 04:00 UTC, not an extension of the lab.
Additional model: USD 0.20, cumulative USD 4.84/5 if authorized; before renewal,
the model is USD 4.64/5. These are estimates, not billed totals or an AWS cap.
