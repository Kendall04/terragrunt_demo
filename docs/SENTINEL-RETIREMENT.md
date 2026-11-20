# Reliability Sentinel: AWS runtime retired

**Completed 10 November 2026, 19:57 UTC**, account `341936017254`, `us-east-1`,
deployment `ecs-portable-r20261026p1`. This is a summary of the preserved retirement
receipts, rechecked locally on 18 November; it is not a new AWS inventory.
[Source recovery and project separation](history/SENTINEL-SEPARATION.md) remain independent.

## Removed and retained

The retirement disabled the exclusive producers and consumers, waited for
quiescence, then removed:

- Six Lambdas: ingestion, worker, watchdog, cleanup, backup-observer and egress-probe-a.
- Six EventBridge rules, the private bus and one SQS event-source mapping.
- Three queues and the active DynamoDB journal table.
- Seven alarms, the Sentinel SNS topic/subscription and six log groups.
- Four exclusive IAM roles and their boundaries, one probe security group;
  the exclusive Lambda ENI was released.

**No Sentinel runtime remains in that final readback.** SQL's native hourly
producer, NAT ASG/E13, ECS/API, TLS, delivery, CloudFront and historical E2 were
outside the retirement. Only the expired one-shot chaos rollback timer on SQL
was disabled; `sql-backup.timer` remained enabled and active.

| Preserved material | Evidence and recovery limit |
| --- | --- |
| 58,112 journal records | Consistent DynamoDB AttributeValue JSONL, unique keys and independent count checked; native on-demand backup remained AVAILABLE after table deletion. No restore was performed. |
| 1,723 operations-DLQ messages | Private JSONL, message IDs/attributes and body MD5 verified before deletion. The other two queues were empty. |
| 187,146 log events | Six private CloudWatch exports with counts, byte lengths and SHA-256. |
| Four compensation versions and S3 archive | Exact version locators retained. Original versioned archive and access-log buckets remain private. |
| Effective configuration and retirement receipts | Lambda, schedules, mappings, IAM, alarm history, owner-state snapshot and final readbacks retained privately. |

Two buckets deliberately remain:
`snt-ecs-portable-r20261026p1-341936017254-us-east-1` and
`snt-logs-ecs-portable-r20261026p1-341936017254`.
The `ecs-portable-r20261026p1-backup-observer` and
`ecs-portable-r20261026p1-worker` roles remain because shared KMS policies refer
to their principals. Retention is not permission to reuse them.

The shared backup/archive key `30f01bb6-03b5-4e5f-b7a8-e304fe607ced` and SNS key
`9d9a8e10-ffd6-4038-b7f0-c3f1ebb4c444` remained enabled. **Full decryption of the
historical S3 archive was not demonstrated:** Sentinel's decrypt grants had expired.
The original data was therefore retained, not replaced with an unverified copy.
Any future access/retention decision must preserve the other consumers of those keys.

## Private provenance

The owner's private evidence set is named `sentinel-closure-20261110`.
`RECOVERY.txt` identifies native backup and exact S3 references; the repository
contains no journal rows, queue bodies, email addresses, private logs or state.
Its 57 inventoried files were rehashed locally with zero mismatches on 18 November.

- `EVIDENCE-MANIFEST.json` SHA-256:
  `45df2270108bbba39952690a2505b8de88514363307eefbf5d45829c415cc813`.
- `FINAL-RESULT.private.json` SHA-256:
  `b4133bd808e512caba9dfef98503682b8245761091e8868fea07efca7eac9e78`.
- `retirement-readback.private.json` SHA-256:
  `66fe26111492a5e7b358efb00e64cdec5e640e9e299532a9c960c08eb7f690e2`.

These hashes identify private receipts for owner review; they are not public
access links or proof of a fresh AWS observation. The saved Terraform owner state
was left unchanged after native retirement and must not be applied blindly.

The closure estimated about **USD 1.87/month** of avoided Lambda and alarm cost
before Free Tier, extrapolated from the preceding 24 hours, not billing data.
Request/write/log costs also cease; retained storage, journal backup and shared
keys still incur their own costs. There is no remaining runtime teardown procedure
in this document: only deliberate archival retention remains to be managed.
