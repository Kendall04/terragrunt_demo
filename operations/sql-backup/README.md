# SQL backups and recovery

The SQL EC2 host runs the native `host.py` producer through `sql-backup.timer`.
The schedule is hourly and persistent. Backup production is independent of
Sentinel; its [runtime was retired](../../docs/SENTINEL-RETIREMENT.md) on 10 November.

**Read next:** [cold recovery](recovery/NATIVE-RECOVERY.md) Â·
[storage verification, retention and holds](storage/README.md) Â·
[measured AWS results](../../docs/V2-RECOVERY-SECURITY-20261105.md#cold-recovery-execution--6-november-utc).

## Producer and integrity

The .NET [SqlBackup CLI](SqlBackup) creates COPY_ONLY backups with CHECKSUM,
verifies them using SQL Server, and publishes backup/manifest pairs to versioned
S3 with SSE-KMS. Receipts bind the exact object versions, byte length and SHA-256.
A success filename or S3 listing alone is not an integrity check.

`host.py run --config <config> --executable <absolute-binary>` holds one private
flock across backup and cleanup. It requires REMOTE_VERIFIED before cleanup and
does not report complete success after a partial cleanup failure. Private systemd
credentials named `backup-connection` and `verify-connection` supply separate SQL
identities. Only the backup child receives them; captured child output is not logged.
AWS access uses the explicit EC2 instance-role path with identity/account checks.

The systemd service requires SQL to be running; it does not start SQL or EC2.
`Persistent=true` allows one catch-up activation, not reconstruction of every
missed hourly backup. A failed job is a failed recovery point even if the API
continues serving normally.

## Inspect and recover a failed producer

On the authorized SQL host, inspect the existing timer/service, private last-job
receipt and bounded service logs. Keep connection strings and raw SQL data out
of output. Check the error against current role/KMS grants, connectivity, SQL
availability, staging free space and the last exact remote-verified pair.

The 9â€“10 November incident had 36 failed cycles under expired IAM/KMS conditions.
The recorded repair on 10 November produced a valid backup at **15:40:32 UTC**,
passed `RESTORE VERIFYONLY WITH CHECKSUM`, then published on the next hourly cycle.
This was a producer repair, not a repeated full restore. The final retirement
readback separately recorded an automatic manifest at **19:00:31 UTC**.
These are dated observations, not a fresh health claim from this document edit.

`host.py inhibit --config <config> --wait-seconds 600` fences future wrapper runs
and waits for the current job without killing it. Timeout leaves inhibition in
place. `status` reports wrapper state; `resume` is an explicit operator action.
STARTED/UNKNOWN after interruption requires review. Local idleness does not prove
SQL quiescence or cancellation of a remote write; direct CLI calls are outside
the wrapper lock. Do not blindly replay an uncertain backup/publication.

## Retention

Local cleanup retains two verified backups by default (configurable 1â€“10).
It deletes only an owned older `database.bak` after rechecking the exact remote
versions, manifest, KMS identity, size/hash and local hash. Receipts, SQL data and
remote versions remain. Foreign, failed and uncertain directories are preserved;
they can accumulate disk use and require investigation.

S3 has a separate seven-day Lifecycle admission policy. The two newest verified
pairs and restore holds stay protected. [Storage helpers](storage/README.md)
plan admission of older versions and copy verified recovery inputs outside the
expiring prefix. There is no newly installed automatic tagger after Sentinel
retirement. Existing tagged versions still expire; untagged versions can accumulate.
No Object Lock, atomic pair deletion or exact physical deletion time is promised.

Keep the application/backup KMS keys, required secret versions and current SQL
trust material available. Encrypted backup storage is not proof of future
restoreability without those dependencies.

## Installation and package provenance

The existing [package builder/installer](package.py) validates deterministic file
hashes/modes, source identity, archive safety and unmanaged targets. Preview is the
default. A real host install needs root, the reviewed package hash, public config
and explicit confirmation. It does not create credentials, invoke systemctl or
turn on the timer. No reinstall is needed for documentation maintenance.

`local_release.py` binds compiled component identity to a source commit and
independently pinned manifest. `verify-bundle` checks the actual payload, not
only a declared hash. The native recovery installer retains exact package-version
checks; do not repack or relabel an old binary as current. See
[cold recovery prerequisites](recovery/NATIVE-RECOVERY.md#preconditions-and-evidence).

## Current TLS prerequisite for another cold recovery

The native runbook is a source pinned by Archify and retains the exact 6 November
trial. Its step 5 uses the original fingerprint-pinned installer, which accepts
the old laboratory leaf. **Do not replay that TLS step under CA-only tasks.**
Before interrupting SQL, qualify a new server certificate under the definitive
DEV CA, its confidential installation path and recovery configuration, as required
by [the current trust contract](../../demo-api/deploy/sql-trust/README.md#root-only-completion).
No new CA-era cold recovery is claimed. Current writer exclusion is the delivery
handover/maintenance procedure; do not acquire or force-release historical E2.
The final backup check uses the native producer and exact S3 receipt, not a retired
Sentinel observer. These qualifications supersede the old installation assumptions
without changing the authenticated trial document or its hashes.

## Recovery evidence and limits

The 6 November cold trials measured **SAME-AZ 24m42.6s** and **CROSS-AZ 41m31.5s**,
including source fencing, fresh EC2, restore/CHECKDB and API/KMS validation.
SQL is one writer; these were supervised planned recoveries, not automatic HA.
An hourly objective is not measured zero RPO, and a final cutover backup cannot
prove behavior during abrupt loss. VERIFYONLY is distinct from a full restore.

The older [prepared-target experiment](recovery/RUNBOOK.md) and local
[service-cutover contract](recovery/SERVICE-CUTOVER.md) remain historical inputs
for evidence/tests. They are not competing instructions for the current host.
The [local observer helper](OBSERVER.md) emits local candidates only; it does not
install monitoring, send mail or replace the retired Sentinel runtime.

Offline checks: [validation guide](../../terraform/docs/validation.md).
Cloud installation, backup execution, retention tagging, copying holds and cold
recovery each have explicit operational effects and require their own scope.
