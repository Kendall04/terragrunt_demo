# DEV operation and infrastructure closure

The [native DEV lifecycle](native-dev-lifecycle.md) owns the five runtime roots.
E16 execution is retired. The [technical audit](../../docs/ENGINEERING-REVIEW.md)
records the latest read-only inventory; dated V1 inventories are not current state.

## Ownership

Terraform owns network, SQL compute, cluster, service skeletons and edge.
Delivery owns task revisions/counts and ALB forwarding; E13 repairs NAT EIP,
private routes and SDC. Security, shared alerts, portable Sentinel and static
CloudFront hosting have separate owners/states. Do not destroy them through a
runtime root or let a skeleton reset delivery-owned fields.

V2 delivery is supervised native administration. Automatic `cd.yml` and
`cd-terragrunt.yml` are disabled in GitHub. The current manual callers fail closed;
the historical protected release/deploy installation is bound to an earlier
branch/workflow identity. See the [CI/CD audit](../../docs/CI-CD-REVIEW.md).
Do not dispatch a historical workflow as a current deployment instruction.

## Authorized window and retained assets

The laboratory reserve starts **2026-11-09 02:30 UTC**, with closure by **04:00 UTC**.
There is no automatic teardown. Expiring IAM conditions do not terminate compute,
release EIPs or remove storage. The laboratory's USD 20 ceiling and the static
hosting's USD 1/month reserve are independent models, not service-side billing caps.

Before a separately authorized closure:

1. Read actual resource IDs, backend versions/locks, operation ownership and
   permission expiries. Older Data retirement plans refer to replaced instances
   and are invalid. Review fresh native plans; never force locks or edit state.
2. Quiesce application writers through the delivery owner. Verify actual task and
   SQL session termination, not only desired counts. Preserve a verified final
   backup and the exact connection/key/backup metadata needed for restoration.
3. Preserve the two historical encrypted SQL disks, current retained SQL root,
   protected backups, keys, secrets and Sentinel journal/archive unless their
   individual disposition is authorized. Do not purge DLQs as cleanup evidence.
4. Review the reverse dependency order in the native runbook. Coordinate Sentinel
   observation/dispatch inhibition before retiring its observed network or its
   time-bound permissions. This audit authorizes none of those mutations.
5. Verify actual retirement and residual cost inventory afterwards. ASGs can
   replace terminated instances; deleting an instance alone is not retirement.

Retained 30-GiB gp3 SQL disks model USD 2.40/month each; all three total USD 7.20/month
while retained, excluding snapshots/requests. S3 versions, ECR layers, CMKs,
Secrets Manager, logs, alarms and residual network resources also need explicit
cost/retention decisions. An empty ECS cluster does not prove a zero-cost account.

## Independent public DEMO

[CloudFront hosting](../../portfolio/product/HOSTING.md) uses its own stack,
private S3/OAC and sealed static releases. It has no API origin and survives
runtime retirement. Keep it outside the laboratory teardown. Its reproducible
version/rollback and separate eventual removal procedure remain in that guide.

Historical [V1 A→B→A evidence](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback)
and [V2 cold recovery](../../operations/sql-backup/recovery/NATIVE-RECOVERY.md)
prove different capabilities. Restarting an old SQL disk after new writes is not
a safe rollback without data reconciliation.
