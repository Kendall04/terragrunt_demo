# DEV operation and infrastructure closure

**Preparation only; no closure operation executed.** Readbacks: 7 November 2026,
06:05–06:13 UTC, account `341936017254`, `us-east-1`. The reserve begins
**9-Nov 02:30 UTC**, with closure by **04:00 UTC** (8-Nov 20:30–22:00 Costa Rica).
There is no automatic shutdown. Permission expiry does not stop AWS resources.

The [native DEV lifecycle](native-dev-lifecycle.md) remains the execution procedure.
This page adds current dependencies, retention choices and permission findings;
it does not authorize its commands. E16 execution is retired. The
[technical audit](../../docs/ENGINEERING-REVIEW.md) retains evidence and security limits.

## Owners and current inventory

Terraform owns skeletons; delivery owns task revisions/counts and ALB forwarding.
ASG/E13 owns NAT repair. Security, shared alerts, portable Sentinel and static
CloudFront have separate owners/states. Never retire them through a runtime root.
V2 uses supervised native administration; historical CD callers remain inhibited.
The [replacement delivery design](../../docs/DEV-DELIVERY-DESIGN.md) is a proposal.

| Active component | Readback | Closure disposition, subject to authorization |
| --- | --- | --- |
| SQL | `i-010e3bf5edd05d11a`, `10.0.101.160`, AZ B, t3a.small | Quiesce, verify final backup, terminate through Data; preserve root disk initially. |
| NAT A/B | `i-05f144bae3b8671f0` / `i-00eeff5c609ca9f0f`, two ASGs desired=1, Healthy/InService | Retire ASGs and EIPs after private consumers finish; terminating instances alone causes replacement. |
| ECS | Blue revision 15, desired/running 1/1; green revision 9, 0/0 | Delivery drains actual tasks; Apps/Platform remove skeletons. Green is an unqualified placeholder. |
| Edge/network | API `4cjyis8dsa`, VPC Link `m4uprm` AVAILABLE, internal ALB, VPC `vpc-00faf317507b09b03` | Edge then network owners remove after quiescence. Liveness/readiness returned 200 during readback. |
| Sentinel | Scheduled worker/watchdog/cleanup/NAT and backup observation; journal healthy | Finish observation, inhibit dispatch at closure, preserve evidence. Private probe needs VPC detachment below. |
| Protected controllers | Release/deploy/cleanup concurrency 0; finalizer qualified `:1`; NAT handlers `:6` active | Preserve delivery inhibition; coordinate security-owned E13 inhibition before ASG retirement. |
| Static DEMO | CloudFront `E1PKEWJYYS672Q`, HTTPS 200 | **Retain** independent private S3/OAC/distribution. No API origin. |

State bodies were parsed in memory for serials/addresses; secret values and outputs
were not exported. Private receipts retain VersionIds/ETags/hashes. Complete bounded
listings found no `.tflock`. E2 ownership was `RELEASED`, generation 14; bounded
recent CodeBuild histories had no active build. Recheck both at execution.

| State | Serial | Managed / data resources | Treatment |
| --- | ---: | ---: | --- |
| Edge | 20 | 9 / 0 | Fresh native closure plan later |
| Apps | 12 | 9 / 1 | Fresh native closure plan later |
| Platform | 5 | 1 / 0 | Fresh native closure plan later |
| Data | 17 | 5 / 0 | Fresh native closure plan later; old host plans invalid |
| Global | 37 | 49 / 1 | Plan after external network dependencies are addressed |
| Shared | 3 | 5 / 0 | Retain alerts/key pending separate disposition |
| Security | 71 | 161 / 2 | Retain identities, keys, secret metadata and backend |
| Portable Sentinel | 44 | 88 / 5 | Selective inhibition/network retirement; preserve journal/archive |

These are inventories, **not approved destroy diffs**. Three historical recovery
states are empty. No Terraform init, plan, apply or destroy ran in this review.

## Network prerequisite

Sentinel probe `ecs-portable-r20261026p1-egress-probe-a` owns Lambda ENI
`eni-0c68d6b92efc3d7b9` in private subnet A and SG `sg-000d3d2d7216d5105`.
They belong to portable Sentinel, not Global. Their presence prevents subnet/VPC
removal. Only `$LATEST` exists in the current published-version list.

In the [portable runtime](https://github.com/Kendall04/terragrunt_demo/blob/528a583d4f74ccd0368cf00929b7315d582cdb35/operations/integrations/portable/trial/runtime/main.tf),
`enabled=false` inhibits scheduled/mapped work; it does **not** remove the probe's
VPC configuration or SG. `nat_observer=null` changes probe resources and monitor
configuration. A blanket portable destroy would also target retained evidence.

Closure needs a reviewed owner-specific operation to detach this exact probe from
its VPC and retire its empty SG, retaining the function, logs, journal and archive.
Prefer a small explicit retirement configuration in its existing owner, with a full
plan proving preservation. That configuration is **not implemented by this review**.
A native administrative alternative must record/reconcile Terraform drift before
later applies; do not invent an input or edit state.

AWS can take [up to 20 minutes to release the Hyperplane ENI](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html).
Keep its execution role/ENI permissions until release; these expire at 04:00 UTC.
Start detachment near 02:30, alongside quiescence, not at the deadline. Verify ENI
disappearance before SG/subnet removal. Never directly delete a service-owned ENI.

## Permission readiness

Actual operator policies and conditions were inspected. Principal-policy simulations
used current resource ARNs/tags and **9-Nov 03:00 UTC** as context. They do not
prove every session/resource policy, SCP or eventual service check. No destructive
dry run or mutation occurred.

| Operation / owner | Evidence and remaining condition |
| --- | --- |
| Runtime operator | Simulated Allow for termination of all three actual EC2s, both ASG Update/Delete, both ECS Update/Delete, both EIP releases, IGW detach and managed route/subnet disassociation. Review the complete fresh plan's actions; not every provider delete API was simulated. |
| Global retirement delta | `EcsNativeGlobalRetirement20261107` restricts IGW/VPC and route-association coverage to real DEV resources/tags; expires **9-Nov 06:00 UTC**. This does not extend operations beyond 04:00. |
| Protected inhibition | Operator has no matching Allow for `autoscaling:SuspendProcesses`, `events:DisableRule` on `e1-wp4-dev-nat-launch`, or `lambda:PutFunctionConcurrency` on the three E13 handlers; simulations return implicitDeny. |
| Security/portable owner | Designate the legitimate administrator explicitly for protected inhibition and probe retirement in the closure authorization, or approve an exact temporary operator delta first. Do not substitute admin credentials after an unexpected operator denial. |
| Expiries | Older SQL recovery/TLS and launch/tagging grants expired 7-Nov; installed EC2s keep running. Backup/observer/worker KMS and probe ENI authority expires **9-Nov 04:00**. Finish their work before expiry; no renewal here. |

Initial simulation throttles were preserved and reconciled once after backoff.
The untagged VPC main route table is not a managed association to disassociate;
its denied simulation does not justify widening the operator policy.

## SQL retention decision

All three 30-GiB gp3 SQL roots use AWS-managed `alias/aws/ebs` encryption:
current `vol-0689370df179cdd95`, detached `vol-0235be4922f977c92` and
`vol-02ba613d809942381`. Current root `DeleteOnTermination=false` preserves it
when EC2 terminates; recheck before apply. NAT roots instead delete on termination.

| Option after separately approved closure | Monthly storage model | Recovery value / loss |
| --- | ---: | --- |
| Keep all three SQL disks | **USD 7.20** | Historical OS/master/login state and current host; stale historical disks are not safe writer rollback targets. |
| Keep current disk plus verified S3 backup | **USD 2.40** + S3 | Preserves current host state; loses direct attachment of two historical roots. Recommended temporary compromise, with separate deletion approval. |
| Snapshot then remove retained volumes | Up to **USD 4.50** for 90 GiB, or **1.50** for 30 GiB | Actual stored blocks may cost less; requires consistent capture and new restore volume. No snapshots were created. |
| Keep logical S3 backup/package only | Current bucket ~**USD 0.01**, plus keys/secrets/requests | Lowest storage cost; loses OS/master/logins outside `demodb`. Recreate/remap principals and host/TLS through the recovery runbook. |

Models use [gp3 USD 0.08/GiB-month](https://aws.amazon.com/ebs/general-purpose/)
and [standard snapshots USD 0.05/GB-month](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/ebs-migrate-ebs-snapshots.html).
No storage deletion, snapshot or archive tier is authorized by this comparison.

Backup bucket `terragrunt-demo-sql-backup-341936017254-fa48a32dc9` contained
75 versions, zero delete markers and 302,964,931 bytes including historical/packages.
Latest 05:00/06:00 pairs on 7-Nov had exact VersionIds, SSE-KMS and no Lifecycle
eligibility tag. Existing observer receipts verify exact-version hashes. This
administrator's manifest read was denied `kms:Decrypt`: this review verifies
metadata, **not independent backup contents or restoration**.

Seven-day rules cover only `terragrunt-demo/dev/sql-backups/v2-20261106/` with
`ecs-retention=verified-superseded-v1`; noncurrent expiration is one day.
Preserve historical prefixes, both latest verified pairs, and restore holds outside
that lifecycle prefix. Tagged older versions continue expiring after compute stops.
Lifecycle is asynchronous and pair deletion is not atomic. Before closure, verify
and retain the selected exact pair with the admitted backup/hold procedure; removing
a tag does not prove cancellation of already queued expiration.

Keep **both** cryptographic dependencies: backup/archive CMK
`30f01bb6-03b5-4e5f-b7a8-e304fe607ced` for S3 objects, and application CMK
`50d3fe36-8128-4d09-ac13-8f5536a230a7` for SQL column ciphertext and secrets.
Keep required secret versions, public trust fingerprint, confidential TLS material,
recovery source/package and VersionId/checksum evidence. No values belong in state,
documentation or command arguments. Logical user-database backups do not preserve
master logins/services; recreating an alias cannot replace a deleted KMS key.
The backup-key administrator can manage policy but cannot decrypt backups; runtime
read grants expire at closure. A later restore needs separately authorized exact
read/decrypt authority. See [native recovery](../../operations/sql-backup/recovery/NATIVE-RECOVERY.md).

## Execution order to review at closure

1. **Preflight:** confirm approved scope/identities, time, actual IDs, E2 ownership,
   backend versions/locks and remaining authority. Finish independent Sentinel
   continuity collection before inhibition. Old Data plan `8534f41f…` names a
   replaced host and is invalid; no saved historical plan may substitute for review.
2. **Quiesce/preserve:** delivery stops new writes and drains actual tasks/SQL
   sessions. Verify the admitted final backup/hold while SQL/NAT and KMS permissions
   work. Inhibit the host producer only after final evidence is durable.
3. **Stop observation deliberately:** portable owner inhibits schedules/ingress,
   lets bounded in-flight work finish, captures final checkpoints/backlog and prevents
   further invocation. Do not replay historical effects or purge queues. Start probe
   VPC detachment early and wait for ENI/SG release.
4. **Fresh native plans:** original roots/backends, admitted inputs/provider locks,
   normal locking; review actual diffs/preservation, save binary/JSON/SHA and obtain
   execution authorization. Sentinel retains its separate provider contract. No
   target, refresh bypass, imports, forced locks or manual state surgery.
5. **Remove runtime dependencies:** native **edge → apps → platform → data → global**.
   Export needed logs before owning plans delete groups. Wait for service-created
   ENIs after edge/ALB/task removal. Preserve SQL roots and retained storage.
6. **NAT prerequisite for Global:** after private work finishes, designated security
   owner inhibits E13 and coordinates the native ASG replacement freeze, keeping
   Terminate available. Set capacity zero through its approved owner; verify no
   pending replacement. Global then releases both EIPs and removes network children.
7. **Independent readback:** no project EC2, active tasks/services, NAT ASGs,
   ALB/VPC Link, runtime EIPs or service ENIs; reconcile states/API absence/locks.
   Verify CloudFront HTTPS remains. Record all retained assets and residual costs.
   Stop/reconcile uncertainty; never repeat an apply blindly.

These steps require the probe-retirement change and designated administrative
actions to be reviewed. **Execution is not yet authorized or fully admitted.**
If backup or release cannot finish in time, report exact residual resources/cost
before 04:00; do not silently extend the window or permissions.

## Evidence and residual charges

Retain journal/checkpoints/four compensated failures, archive, backups/holds,
backend versions and private receipts. The operations DLQ has approximately
14 messages and **14-day retention**: keeping the queue does not freeze expiry.
Keep available historical diagnostics; no ReceiveMessage, purge or replay occurred.
Log retention also continues after inhibition.

Latest short readback remained `HEALTHY_ACTIVE`: four historical failures/four
compensations, zero active permanent failures, one due check and three recent
archives. It corroborates, but does not extend into a new continuous claim, the
[11h36m interval](../../docs/ENGINEERING-REVIEW.md#automatic-monitoring-actually-observed).
The independent 12–24h collection remains uninterrupted.

Last lab model: **USD 14.73/20**, including the earlier cost query. No second Cost
Explorer query was purchased. Its **USD 9.3261 account-wide estimated/incomplete**
result includes unrelated services; it is not laboratory spending or budget balance.
Disk models exclude CMKs (~USD 1/key-month before rotations/usage), five SQL/app
secrets (~USD 2/month plus API calls), ECR, logs, DynamoDB, S3 requests and shared
alerts. Two unreleased IPv4 addresses alone model USD 7.20 per 30 days. Retention
needs a separate duration/budget decision.

The [public DEMO](../../portfolio/product/HOSTING.md) stays independent: CloudFront
PAYG, private S3/OAC, **USD 1/month reserve**, modeled USD 0.10–0.20/month at low
traffic. No service-side cap is implied. Static release/rollback survives runtime
retirement. This preparation changed no AWS infrastructure, IAM, timers or evidence.
