# ECS native trial prerequisites — 27 October 2026

Status: preparation only; no deployment authorization, executable integrated plan or total budget is claimed. Source baseline `dc6b2a62ab9aad0b5725e6303fa1b492a6b5774f`. This checkpoint supersedes the old 102/USD6 proposal as an admission description; it does not alter historical receipts or approvals.

## Verified state and ownership

Read-only receipts in `task-3/ecs-integrated-admission-20261027/` were recorded at 04:27–04:39 UTC on 27 October, account **341936017254**, region **us-east-1**. Every AWS command used `--profile cnp-cert-dev`. STS resolved that profile to `arn:aws:iam::341936017254:user/cnp-cert-admin`; there was no profile substitution or role assumption. A profile label is not an IAM identity. The recorded operator trust permits that user to assume the existing operator; this investigation did not exercise that permission.

The five original DEV state objects are versioned, empty (zero resources and outputs), and retained their same current VersionId/ETag across the read. The raw state values were not retained or exposed.

| Layer | Serial | Lineage |
| --- | ---: | --- |
| global | 33 | 15f72c18-daf4-151b-28fa-97a6129fde8c |
| data | 10 | ffb3006f-e76a-0ac5-8ae7-653ff1b701c0 |
| platform | 4 | e9f8d1c7-6744-4a97-6b67-266114c8c8a8 |
| apps | 11 | 263b0091-8a3c-96e0-31af-eb614bd37c42 |
| edge | 15 | 4342994c-bf67-e0db-5bdc-46ac3f99b33e |

Their keys remain `s3://e1-lifecycle-dev-341936017254-us-east-1/e1/lifecycle/dev/{layer}/terraform.tfstate`. Preserve them and their histories. Do not import/adopt the default VPC or the other project's VPC `vpc-05a8ec8d7de5a8271`. The inventory returned no EC2, EBS volumes, ECS clusters, ALBs, NAT gateways, EIPs or ASGs. This is coverage of those APIs in this account/region, not a claim of a zero AWS bill: buckets, images, logs, keys and other retained control-plane resources remain.

`state-and-policies-summary.json` records each exact state hash/version, launch-template identities and policy defaults. Reads succeeded without an AWS denial in those two saved inventories. A later prerequisite script exited at its local identity assertion before any prerequisite queries. It failed to retain the identity response/error. Therefore its cause is **unknown**, not evidence of AccessDenied or of a different principal. It was not retried; see `identity-check-limitation.json`. Current role/profile/KMS existence checks that would have followed that assertion were **not executed**.

## Concrete control-plane prerequisites

Scope correction: [bootstrap source reconciliation](BOOTSTRAP-SCOPE-20261027.md)
shows that absent infra/emergency compute is NOT a prerequisite of supervised E16.
It remains a final CI/CD delivery requirement. The four infra nodes use WP5; the
emergency pair has a WP4D implementation requiring verified cleanup dependencies.
Do not create the six merely to prepare original-root plans, and do not describe
the current full security root as a safe six-resource installation.


The complete project list contains `e1-controller-release` and `e1-controller-deploy-dev`, but not these three projects required by the protected design:

- `e1-controller-infra-dev`
- `e1-controller-infra-high-risk-dev`
- `e1-controller-emergency-dev`

The Lambda list contains `e1-gateway-release` and `e1-gateway-deploy-dev`, but not `e1-gateway-infra-dev`, `e1-gateway-infra-high-risk-dev` or `e1-gateway-emergency-dev`. Their absence is not permission to recreate them. Associated roles, policies, images, immutable bundles, log/queue/rule resources and installed-factory revisions must be compared with `terraform/infra/security/modules/controller_compute` and the authority publication before selecting a creation/update plan. The proposed strict recovery V2 cannot be claimed installed from local tests.

Both original NAT templates exist: `demo-dev-lt-nat-a` (`lt-04ab8d2ec1f975f96`) and `demo-dev-lt-nat-b` (`lt-0b3ed490a53f8dfe7`), each default version 1/latest 2. Their existence does not verify the image, effective profile or a particular template version's bootstrap. Do not silently select latest or adopt EKS templates. The three original NAT recovery Lambdas are present, but their installed compatibility remains a readback/admission requirement.

The historical TARGET expansion is 73 addresses (global49/data5/platform1/apps9/edge9) under its original options. Portable Sentinel has **62 mock-provider addresses**, AWS provider6.28 isolated from TARGET5.100. These are independently qualified source compositions. **73+62=135 is not a saved integrated AWS plan**, excludes missing control-plane restoration and strict-security prerequisites, and is not the final resource count. Empty states also mean downstream roots have no live global/data/platform outputs. A future staged plan must use actual admitted upstream outputs, not invented IDs substituted into a purported native plan.

## IAM changes that must be grouped before execution

`TerragruntDemoDevOperator` exists (RoleId `AROAU7HHZR5TGPL7QPJQV`); Part4's effective version is **v5**, Part7 **v3**. The current backend already has `E16ExclusiveDevRuntimeWriter` for the five original DEV state/lock paths. Preserve it and the state-retention denies.

Part4v5 explicitly denies `iam:CreateRole`, `iam:PutRolePolicy`, `iam:AttachRolePolicy`, `s3:PutBucketPolicy`, `s3:DeleteBucket`, `kms:ScheduleKeyDeletion` and `secretsmanager:DeleteSecret` on `*`. Another Allow cannot override this Deny. For the portable resources, the minimum reviewable design is:

1. Split the existing deny by action/resource and exempt only the four admitted portable role ARNs for CreateRole/PutRolePolicy, and its exact archive bucket for PutBucketPolicy/DeleteBucket. Keep managed-policy attachment denied unless the final plan actually requires it; keep KMS deletion and secret deletion denied. No broad removal of Part4's guardrail. Exact JSON, concurrency hashes, version-slot effects and reversal must be part of the future access packet, not inferred from this recommendation.
2. Provide the operator's scoped lifecycle Allows for four roles, four mirrored boundaries and inline policies; PassRole only to their four Lambda workloads; and the table/queues/EventBridge/Lambda/logs/alarms/SNS/private archive resources. The reviewed source policies already exist in `operations/integrations/portable`; they are not installed permissions. Disclose regional Get/List/Describe and the known Lambda mapping callback wildcard where AWS cannot enforce the intended UUID scope. Workloads retain no NAT, EC2, SSM, IAM, SQL secret or original-backup permissions.
3. Add only the exact portable state and `.tflock` paths to the operator/backend exceptions. Its new prefix is not currently admitted by the five-state E16 policy. Preserve existing state versions, encryption, locking, EKS and all unrelated prefixes. The portable root must have one owner and its own provider lock; do not force provider6 into the original TARGET roots.
4. SQL-role delta: PutEvents only to the admitted bus, exact `events:source=sentinel.report.sql-observer` and `events:detail-type=Sentinel Observation v1`, real expiry; exact versioned cohost artifact GetObjectVersion and corresponding S3-only KMS context. Existing proposal fixture times/VersionId are not current authority. No extra BAK access is justified by the observer.
5. Strict SQL requires an explicitly supplied, separate migrator secret reference and narrowly scoped SQL-host read grant. The three known DEV secret metadata references are not a new migrator credential. No secret value was read/generated, and no certificate key upload/distribution, SQL grants or trust installation is authorized by this preparation.

Current readback of published SQL/task roles and both KMS key metadata remains unconfirmed after the later identity gate. Those are exact remaining metadata prerequisites, not findings that the roles/keys are missing. Reconcile their identities and policy contents once an admissible read session is available; do not switch principals to overcome a refusal.

## SQL transport and strict runtime boundary

Local update after this preflight: [strict recovery wiring](STRICT-DATABASE-RECOVERY.md)
has now been implemented/tested. The historical TrustServerCertificate=True builder
is limited to loopback compatibility; strict restore/handoff uses validated TLS and
separate migrator/runtime identities. The following initial findings remain context,
not a claim that this local wiring is still absent. Native transport, trust/grants
and protected installation remain pending.


Cohost observation now starts independently of SQL credentials through the reviewed bootstrap and opt-in timers; this removes its unnecessary Run Command dependency. It does **not** authorize or prove a replacement route for the rejected commands.

The recovery host runner still requires admitted execution for synthetic seed/backup, source fencing, destination restore/CHECKDB, principal adoption and handoff. Local private-listener automation and task-definition preparation do not execute those operations. b2/d1 Run Command was accepted by the API but returned AccessDenied/-1 without proven command execution; the cause remains unknown. No retry, SSH, Session Manager or alternate principal is proposed as a workaround. Before billing resources, define and admit the exact recovery document/content hash, destination binding and command scope; a new transport test requires its own explicit evidence/authority.

The new API can validate certificate chain/name using its qualified lab-trust image, with runtime/migrator separation. There has been no SQL handshake. `operations/sql-backup/recovery/host.py` still has an explicit historical `TrustServerCertificate=True` connection builder, and the old recovery tar contains the historical API. Neither qualifies strict external API TLS. The final trial must select the strict app/config and verified public trust image through the protected release owner; it cannot silently treat the old host helper/archive as the new strict path. Supplying/configuring the existing private key on the SQL node needs separate concrete approval; it never belongs in Terraform state, image context, logs or Git.

## Bounded sequence and viable exit to approve together

1. Reconcile only the above control-plane/role/key metadata; seal current source/artifact identities, exact variables, backend ownership and reversible IAM deltas. Admit the required SQL control path before starting the whole paid platform.
2. Prepare protected control-plane installation/review; then staged original TARGET and isolated portable plans. Compare actual addresses and native outputs; stop on unknown owners or incompatible factory/profile. No authority approval is generated from hashes.
3. After grouped approval: publish immutable artifacts, install scoped deltas, create the synthetic source/platform and portable runtime disabled. Confirm the new SNS subscription before notices. Establish strict SQL/API baseline, real COPY_ONLY/checksummed backup and receipt.
4. Run SAME-AZ and CROSS-AZ sequentially, one active SQL: positive source non-writer evidence before target activation; create a cold target; restore/CHECKDB; strict runtime permissions and TLS; Fargate/public read/write/decryption; measure the whole request-to-public-readiness time. Stop activation when fencing, identity, restore or endpoint proof is uncertain. A stopped/terminated host is not a simulated AZ outage proof.
5. Exercise actual backup age and host heartbeat expectations, incident/deduplication/recovery and readable inbox notices. Sentinel does not restore SQL. Give Kendall a proposed 30-minute LIVE review within the 6–8-hour window, then retire without waiting indefinitely for a reply.
6. Reserve at least 90 minutes for retirement: disable producers/schedules, reconcile attempts/outbox/probes honestly, export sanitized receipts, use the original owners to plan retirement in dependency order, empty only new trial object versions, retain required backups 2+2 days, remove own temporary grants and verify native absence/explicit residuals. Preserve original states, roles, keys, historical backups/images and external resources. The prior rejected broad EKS/RDS retirement is not this objective; no execution/admission guarantee is claimed for a future ECS retirement plan.

The durable publisher's current cap is **20 attempted entries, three per pending entry**. Two entries every 300 seconds imply 144–192 entries over 6–8 hours before retries/initial observation. Do not approve full-window monitoring while pretending the 20-entry profile covers it. The final packet must explicitly choose bounded observation phases or review a different durable test cap; two-hour backup freshness and twenty-minute telemetry deadlines must not be silently weakened. Old USD6/102 and serverless USD2 proposals authorize neither option.

## Cost model and what prevents a total

Use actual planned instance/template sizes and billed durations, including replacements, setup and retirement; no free-tier assumption. Existing TARGET defaults are SQL t3a.small STANDARD/30GiB and two Fargate task definitions of 0.25vCPU/0.5GiB. Actual running task counts, NAT template sizes/disks and any control-plane rebuilding minutes remain unbound. Retained data has a cost after compute retirement.

Verified official public rate components for a conditional 6–8-hour model (USD, before tax/credits):

| Component and assumption | 6h | 8h |
| --- | ---: | ---: |
| One ALB base, $0.0225/hour | 0.135 | 0.180 |
| ALB at one LCU throughout, $0.008/LCU-hour (assumption, not a traffic cap) | 0.048 | 0.064 |
| Two continuously running Linux/x86 0.25vCPU/0.5GiB tasks | 0.1481 | 0.1975 |
| Two NAT EIPs at $0.005/address-hour | 0.060 | 0.080 |
| **Only this conditional subtotal** | **0.3911** | **0.5215** |

The ALB is internal in the current source; no ALB public IP charge is assumed here. This subtotal is **not the trial budget or an upper bound**. Add actual SQL/NAT EC2, root volumes and any retained snapshots, API Gateway/transfer, S3 object/version retention and requests (including 2+2 days), ECR/artifact storage, CloudWatch logs/alarms/metrics, portable Lambda/DynamoDB/PITR/SQS/EventBridge/SNS, KMS/Secrets Manager, CodeBuild and any paid Actions. No current billing/free quota or completed action-minute allowance was read. EBS charge is provisioned GiB-month prorated by lifetime; retained storage must have an explicit expiry/cost reserve. No new total is justified until the missing native-control and strict-security scope is closed.

Official sources checked on 27 October 2026: [ALB](https://aws.amazon.com/elasticloadbalancing/pricing/), [Fargate](https://aws.amazon.com/fargate/pricing/) (N. Virginia Linux/x86 example: $0.000011244/vCPU-second and $0.000001235/GiB-second), [public IPv4](https://aws.amazon.com/vpc/pricing/), [EBS billing method](https://aws.amazon.com/ebs/pricing/). Reprice exact final SKUs before requesting a spend ceiling. This packet requests no new AWS budget and does not reuse old budgets or EKS funds.

## Local correction completed

`Session.initialize` in `scripts/practical_dev.py` previously omitted the principal helper, compressed payload and cohost template referenced by the materialized SQL root. It now copies only those explicitly named tracked files alongside the original sources, records their hashes, and fails if required input is absent. It does not copy arbitrary adjacent files or alter identity/backend/approval gates. The hermetic suite completed **80 tests / 0 failures / 0 errors / 0 skipped** (136.218s), including three new source-copy/tamper/missing-input regressions. These are local doubles, not SQL or AWS acceptance. Source freshness entries remain UNVERIFIED and approvals are unchanged.

This closes the inventory/state reconciliation and local materialization bug. The remaining blockers are concrete control-plane installation scope, current workload metadata/admission, strict SQL provisioning/delivery binding and admitted SQL execution; a total resource count and spend request are not ready. No AWS writes, remote locks, role assumptions, secret reads, SQL installation, paid Actions, publication or teardown execution occurred.
