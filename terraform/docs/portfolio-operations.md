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

Sentinel's runtime was [retired on 10 November](../../docs/SENTINEL-RETIREMENT.md).
Two private buckets, a native journal backup and two KMS-referenced roles remain
deliberately retained. Shared keys stay enabled. That storage is not active
Sentinel and its costs do not disappear with the Lambdas.

Earlier resource counts, volume estimates and read-only Cost Explorer observations
are preserved in the [dated engineering review](../../docs/ENGINEERING-REVIEW.md).
Use current billing and resource evidence for any future cost decision; do not
reinterpret those observations as a present inventory.
