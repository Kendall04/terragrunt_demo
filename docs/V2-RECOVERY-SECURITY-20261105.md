# ECS V2 recovery and security work — 5 November 2026

This is the current implementation/evidence record. It supplements the successful
[DEV deployment](DEV-V2-20261105.md); historical recovery fixtures are not evidence
of a new cold recovery. Starting main: `a913a822492b633784eda15758d1feaf43a7c051`.

**Later operation, November 6:** [the Sentinel incident and retention record](SENTINEL-CHAOS-20261106.md)
documents the installed policy for the new backup prefix, preserved historical
versions, and the independently approved USD 20/window through November 9 at
04:00 UTC (closure reserve 02:30). Retention proposals and November 7 permission
dates in the chronological record below are historical. The measured SQL recovery
results remain unchanged; no further SQL recovery was performed for that work.

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
  until the complete cold test succeeds; see the subsequent measured trials below.
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
and next trigger 01:00 UTC. This proves a scheduled execution. The later SAME-AZ
trial below additionally verifies the producer after an actual host reboot.

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
The initial Sentinel/observer expiry was 6 November 02:00 UTC. The separately
approved renewal below moved the existing expiry conditions to **7 November
04:00 UTC**. This remains a bounded trial, not permanent monitoring.

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
updates, no drift. At preparation it was **not applied**; the owner subsequently
approved both trials and USD 3. The actual execution below records a partial
failure and reconciled completion of this plan. Neither a plan nor
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
corrected to 8000; the corrected real readback passed. That inspection preceded
the source fence and cold trials described below.

The Linux recovery/portable suite passed **289 tests in 23 suites, zero skips**
using the existing local CI image, with no network/credentials. The isolated
Sentinel Terraform mock suite passed **23 tests**. These counts do not certify a
cold AWS recovery. Full E1/remote CI results are recorded with the eventual PR.

The bounded Sentinel renewal plan is
`a0361292511ddd7de0fcff378bbc2c3bb458dca9219969edc0d2abad270e0ab4`:
five in-place updates, zero drift, only existing grant dates and observer expiry.
Three existing external KMS statements need the same expiry change. It is
**applied after explicit owner confirmation**. Readbacks matched all five
planned updates and the three exact KMS date changes. State advanced from 22 to
23, with 78 managed resources and no persistent lock. The end remains 7 November
04:00 UTC, not an extension of the lab. Additional model: USD 0.20, cumulative
USD 4.84/5. These are estimates, not billed totals or an AWS cap.

The scheduled observer verified the automatic midnight backup using its actual
S3 VersionId and SHA256. At 00:33 UTC the worker checkpoint was revision 228,
with no retained lease or consecutive failure; the four permanent historical
failures remained preserved. No inbox receipt is claimed for this new observation.

Recovery fencing rejects active or transitioning backup services, including
systemd's `activating` state for a running oneshot. It rechecks after stopping
the timer to close a timer-fire race before any SQL write fence. A refusal at
that point leaves the timer stopped for explicit operational reconciliation;
it does not stop a backup already in flight or mutate SQL.

## Cold recovery execution — 6 November UTC

The owner approved sequential CROSS-AZ and SAME-AZ trials, at most 90 minutes each,
with temporary API interruption, exact temporary subnet/TLS-secret permissions,
all source disks/backups retained and USD 3 additional reserve. The cumulative
model is **USD 7.84 against USD 8 authorized**, not observed billing. The existing
7 November closure remains unchanged.

### CROSS-AZ A → B: functional PASS with reconciled failures

RTO started at **01:17:11.489316** before ECS drain and ended at
**01:58:42.993704** after real API health/readiness, preservation of all three prior
records and a new POST/GET/KMS decrypt round trip: **2,491.504388 seconds
(41 minutes 31.5 seconds)**. This includes provisioning and all repairs;
it is not an unattended first-pass recovery claim.

The source was positively fenced at 01:24:43: zero writers, READ_ONLY and disabled
runtime/migrator logins. Its final remote-verified backup started at
01:24:44.9681095, with SHA256
`3a27ae8c0c7060f76352ce2ad4e986050add00d9e4d504bb5f0c7c1c89af1a1a`
and object version `7RQeysasFZPXAfxydJ81VFGtFZoCjUpA`. Original instance
`i-0ca57b4758f2c2821` was verified terminated; its encrypted 30-GiB disk
`vol-02ba613d809942381` remained detached and available. The fresh destination
`i-0becd5dbb41e6d487`, `10.0.101.242`, was created in `us-east-1b` without a
pre-provisioned recovery server.

The original saved plan became invalid because a transitive `authority.json` read
changed after planning; the initial preflight checked only Data root files. Apply
terminated the source and then stopped before creating the destination. Data 15
was reconciled, the retained disk and backup verified, and a new full-root plan
sealed all 264 tracked Terraform configuration files. It contained the identical
approved destination (one create and three alarm updates), without another delete.
Plan `e3b1d9f44d7ccecfe27314800bc8e8f2fdc022165ec1d82ff995440552b95151`
completed to Data 16. No state surgery, old-plan replay or source rollback occurred.

Three host defects were corrected without discarding failed receipts:
root-owned private restore files caused SQL errors 3201/3013; inherited umask 077
made public package directories untraversable; and the restored READ_ONLY database
needed READ_WRITE before promotion. The fixes run the CLI as `mssql`, scope public
directory umask 022, and persist the completed restore receipt before making only
the restored copy writable and renaming it. A completed restore was reconciled by
CHECKDB/hash and promoted, **not restored a second time**.

All three original ciphertext rows and both migrations matched. Runtime regained
only existing SELECT/INSERT and migration-metadata SELECT; the migrator stayed
disabled. ECS blue revision 14 used the same qualified image and only a new SQL
endpoint/connection-secret version. A new row made four rows. At 01:59:54 the new
host completed another remote-verified backup and enabled its hourly timer.

The last scheduled pre-interruption backup began at **01:00:03.8725578**: age
**17 minutes 7.6 seconds at RTO start**, **24 minutes 39.5 seconds at the write
fence**. No committed rows were lost in the planned cutover because a final backup
was taken after fencing. This does not establish zero RPO for abrupt outage or
prove a transaction-log/PITR chain.

### SAME-AZ B → B: second trial

The independently reviewed plan
`d4ba413b6ade860b67ad1b13288694909c4cfcbfd3ddf3ec7cb71cebab39fdcf`
contains one SQL replacement and three alarm dimension updates, no drift, identical
desired configuration and retained root disk. RTO starts at **02:06:19.052177**.
Its final backup preserves four rows with SHA256
`e6412e581f0a1df6a0b1707970d1a1c04d8cce6dce7acf6ff565949127e845ae`.
The destination is `i-010e3bf5edd05d11a`, `10.0.101.160`, AZ B. Its predecessor is
terminated and disk `vol-0235be4922f977c92` is retained. Data state is serial 17,
version `l4ryszZHZjcEeoQh1q9RHzEdkEtNitGm`, without a lock.

**Functional PASS at 02:31:01.635056: 1,482.582879 seconds (24 minutes 42.6
seconds)** from initial drain through API health/readiness and POST/GET/KMS.
This corrected trial completed its sole apply, installation, restore and handoff
without corrective replay or manual file/SQL repair. CHECKDB, four original rows,
ciphertext hash and two migrations matched; a new application write made five rows.
The image, task roles, listener and SQL grants remained unchanged. Blue revision
15 points to `10.0.101.160`, with a new versioned connection secret; green stays zero.

Before reactivating ECS, one supervised reboot changed boot ID from
`c5cd1230-9752-40d4-b56f-59cc33385d67` to
`2da5afce-75f5-4907-bc51-a6bcd9345a66`. SQL/TLS and data identity passed afterwards;
the timer remained enabled/active with `Persistent=yes`. A real post-reboot service
run finished at 02:28:47 with `REMOTE_VERIFIED_CLEANUP_VERIFIED`, backup SHA256
`5fbb6c6baea0993e3b7031f406a767d9df6eb6e562a9b420f38b7de7af43582e`,
version `8zPBT_1wtX97VNbouWoDbLhEu7CINs0w`. This is actual reboot persistence plus
functional backup execution, separate from the earlier automatic hourly runs.

The verified backup available before this second interruption began at
01:59:52.6855848: age 6 minutes 26.4 seconds at RTO start. The later final fenced
backup again preserved all rows. Neither trial simulates loss of every region-wide
dependency or proves an automatic recovery decision.

The corrected Linux recovery/portable suites pass **297 tests in 23 suites with
zero skips**. A direct Windows CRLF mount initially failed shell parsing; the LF
Git export passed. This fixture issue is separate from AWS results.

### Post-recovery observation and resource closure

The scheduled external observer verified the second trial's final backup and the
new host's 02:26:28 backup using exact versions and full hashes. At 02:35:27 the
Sentinel checkpoint was revision **594**, owner/lease null and consecutive failures
zero. All eight records representing the four historical permanent failures matched
their prior content. No journal reset or historical resend occurred.

Archive audit `fd7213b47a79d6faff6076976045d2ec925ac0ae6abb4216153bcf415764b43a`
was confirmed in one worker attempt at 02:34:26. S3 readback confirmed version
`nJnEivlS1JYT2WGo4v0k8hmbuXcvud4P`, 9,990 bytes and the expected SSE-KMS key.
The administrator's independent body read was denied `kms:Decrypt`; no permission
or identity was changed to bypass it. Content verification is the worker's actual
receipt, not a second administrative hash claim. Prior owner-confirmed email remains
the separate inbox evidence; no new inbox receipt is claimed here.

At 02:35:56, one SQL EC2 and two NAT EC2s were running; blue had one task and green
zero. Data 17, shared 3, global 37, platform 5, apps 12 and edge 20 had no persistent
S3 locks. The two predecessor SQL disks are detached, encrypted and retained; the
current 30-GiB root also has delete-on-termination false. Their key is AWS-managed
`alias/aws/ebs`, not a customer-managed CMK.

Cost Explorer reported **USD 1.3251945145 estimated, account-wide for 5 November**
at this readback. This delayed number cannot be attributed to these trials or
compared as an actual execution bill against the USD 7.84 model. The two retained
30-GiB gp3 disks add approximately **USD 4.80/month** while retained; all three SQL
roots would total approximately USD 7.20/month if compute is later retired and all
remain. No disk/backup deletion is authorized by these trials.

The existing native closure procedure remains required at 7 November 02:30–04:00
UTC. Earlier Data retirement binaries refer to replaced instances/state and are
**invalid**. Any retirement must review a fresh plan against Data 17/current instance,
drain writers and preserve retained data unless separately authorized for deletion.
No automatic shutdown or extension has been installed or assumed.
