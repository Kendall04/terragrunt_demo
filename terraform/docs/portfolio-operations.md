# DEV operations and retained costs

Use [native infrastructure operations](native-dev-lifecycle.md),
[automatic application delivery](../../docs/DEV-DELIVERY-DESIGN.md) and
[SQL backup/recovery](../../operations/sql-backup/README.md) for current procedures.
The independent DEMO [hosting guide](../../portfolio/product/HOSTING.md) has its
own owner, budget and rollback process.

## Operating boundary

DEV has real automatic delivery, SQL/KMS and CA-only TLS evidence. PROD remains
disabled and unqualified. A dated inventory does not establish today's running
resources, permissions or bill. No AWS inspection accompanies this consolidation.

The former 9 November shutdown window and temporary grants were historical;
permission expiry never stopped EC2/ECS. Any future maintenance or retirement
needs a fresh inventory, explicit owner scope and current permissions through
completion. Preserve state locking, source-volume retention, backup holds and
the exclusion of manual/Terraform/application writers.

## Residual cost categories

Compute/network costs include ECS tasks, SQL EC2, NAT Instances/ASGs, EIPs and
ALB. Stopping compute does not remove EBS, versioned S3, ECR, Secrets Manager,
KMS, logs or state/evidence costs. Decide retention separately from teardown;
keys required to decrypt data are not disposable because a workload is stopped.

The original laboratory model of roughly USD 14.72 against USD 20 was an estimate,
not Cost Explorer billing and not authorization to extend the laboratory. The
public CloudFront DEMO uses pay-as-you-go with a separate USD 1/month reserve;
its documented low-traffic model is not a hard AWS spend limit.

Sentinel's runtime was [retired on 10 November](portfolio-operations.md#separated-sentinel-resources).
Two private buckets, a native journal backup and two KMS-referenced roles remain
deliberately retained. Shared keys stay enabled. That storage is not active
Sentinel and its costs do not disappear with the Lambdas.

Earlier resource counts, volume estimates and read-only Cost Explorer observations
are preserved in the [dated engineering review](https://github.com/Kendall04/terragrunt_demo/blob/5b13b448c328241e02ee1432fba221e675e85810/docs/ENGINEERING-REVIEW.md).
Use current billing and resource evidence for any future cost decision; do not
reinterpret those observations as a present inventory.

## Separated Sentinel resources

Reliability Sentinel was developed/evaluated separately and its ECS-integrated
runtime was retired on 10 November 2026. It is not an ECS operating dependency.
Source is recoverable at `528a583d4f74ccd0368cf00929b7315d582cdb35`; the exact
inventory is [retired-sentinel.json](../../ci/authority/retired-sentinel.json).
Private evidence is managed independently: 58,112 journal records, 1,723 DLQ
messages, 187,146 log events and the native journal backup were preserved.

The archive buckets `snt-ecs-portable-r20261026p1-341936017254-us-east-1` and
`snt-logs-ecs-portable-r20261026p1-341936017254`, plus the `backup-observer` and
`worker` roles under `ecs-portable-r20261026p1`, were deliberately retained.
Do not remove shared KMS keys `30f01bb6-03b5-4e5f-b7a8-e304fe607ced` or
`9d9a8e10-ffd6-4038-b7f0-c3f1ebb4c444`: other consumers remain. Full historical
archive decryption was not demonstrated because the grants expired.

The private `sentinel-closure-20261110/EVIDENCE-MANIFEST.json` has SHA-256
`45df2270108bbba39952690a2505b8de88514363307eefbf5d45829c415cc813`.
The 57 files were rehashed locally on 18 November with zero mismatches. This is
receipt provenance, not a new AWS inspection; no runtime removal remains to execute.
