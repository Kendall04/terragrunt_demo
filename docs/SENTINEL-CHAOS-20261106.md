# Sentinel DEV: retention and controlled incidents

Owner scope: `bbd5c6fa0b425a35a2264033296a48396bb604f45316a62bf5e274c293eb19c8`,
approved on 2026-11-06. The new modeled ceiling is USD 20, separate from previous
work. Stop new experiments on November 9 at 02:30 UTC; closure is due at 04:00 UTC.
Approval is not retroactive and does not provide an AWS billing cap.

## Implementation and evidence boundary

This page describes the implementation under validation. Local tests are not AWS
incident evidence. The final experiment records must distinguish those results.
The existing SQL and API run in private subnet B. Experiments target NAT A only;
neither SQL data nor retained disks/backups may be destroyed.

The private Lambda probe makes one HTTPS request to `checkip.amazonaws.com` from
private subnet A. The existing regional observer reads the ASG, EC2, route and EIP
and correlates the probe response with its invocation ID. A healthy ASG alone is
insufficient. A failed observer is **Unknown**, not a proven network outage.
The probe has no ingress and only HTTPS egress. Its Lambda service ENI permissions
require Resource `*`; a `lambda:SourceFunctionArn` Deny prevents function code
from using those EC2 permissions. The observer and Sentinel stay outside the VPC.

NAT uses its own content-derived monitor catalog. The two installed SQL monitor
definitions and their catalog identity remain unchanged. Both groups use the
existing journal, worker and **64-request/four-job** operational profile. NAT's
condition assessment reports actual evidence; it does not infer application or
SQL availability. Recovery notices require the existing resolution semantics.

## Historical failures

Four permanent ArchiveDecision failures refer to original November 5 audits.
Their exact effect/audit byte hashes are pinned by `ArchiveCompensation`.
The explicit compensation mode reads these records, conditionally creates archive
objects with `If-None-Match: *`, verifies full bytes, SSE-KMS and real VersionIds, then appends separate
`AC#` receipts. Any ambiguous write stops. It never changes O#/T#/A#/OP# records,
resets attempts, queues old effects or sends SNS messages. A 412 leads only to
readback of existing bytes; any other write failure stops. This avoids requiring
ListBucket merely to distinguish a missing object's 403 response from absence.

The watchdog checks original hashes and append-only receipts. It reports raw
historical failures and verified compensations separately. Only verified archive
compensations are subtracted in its in-memory current-health view. New failures,
old stuck work, missing progress and missing heartbeat retain their original
failure semantics. No healthy journal is fabricated.

## Remote backup retention

The new prefix is `terragrunt-demo/dev/sql-backups/v2-20261106/` in the existing
SQL backup bucket. Historical prefixes and existing Lifecycle rules remain intact.
The bounded retention admission verifies exact manifest and backup versions,
full SHA256, length, SSE-KMS and the producer checksum receipt. The newest two
verified pairs are never tagged for expiry. A bad newest pair fails closed.

Only older verified pairs receive `ecs-retention=verified-superseded-v1` on both
exact versions. Native S3 Lifecycle expires eligible current versions after seven
days, their noncurrent versions after one additional day, and removes empty
delete markers. Incomplete multipart uploads in this new prefix are aborted after
one day. Invalid/uncommitted objects are quarantined, not automatically deleted.
Enrollment of previously untagged data older than six days requires review.

The manifest is tagged first. A partial tag operation may retain an extra backup;
it cannot make the protected newest two eligible. No application DeleteObject is
used. S3 expiration is asynchronous, based on object age rather than tag age, and
is not an atomic pair deletion. Neither an exact deletion time nor seven-day
maximum physical retention is guaranteed. If production stops, the last two
verified pairs remain indefinitely and continue to incur storage charges.

Before relying on an eligible object for restore, run `backup_restore_pin.py` to
copy and fully verify the exact pair into the excluded
`terragrunt-demo/dev/sql-backup-restore-holds/v2-20261106/<operation>/` prefix.
The original manifest is retained; the restore manifest binds genuine destination
VersionIds. Its receipt must exist **before fencing the source or provisioning a
replacement**. A failed pin does not authorize continuing recovery. Removing a
tag does not cancel an expiration already queued by S3. Restore holds have no
automatic deletion and require a later explicit disposition.

References: [S3 expiration behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
[Lifecycle rules and versions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html),
[Lambda VPC permissions](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html).

## Controlled experiment limits

At most two A replacements, each with a 15-minute recovery limit; never disrupt B
simultaneously. The optional delayed-launch experiment requires a native timed
resume armed first. A producer-only backup failure lasts at most 150 minutes and
requires a native rollback timer before injection. Worker schedule pause is at
most three minutes, watchdog stays active, and restoration must be prearmed.
No fault begins without healthy SQL/API/B readbacks and baseline A egress evidence.

At most 20 notices go to the existing confirmed destination. Publication, SNS
delivery metrics and inbox confirmation are separate facts. Each experiment must
record fault, detection, journal, archive, publication and recovery timestamps,
including unsuccessful attempts. These are supervised DEV trials, not an SLA.
