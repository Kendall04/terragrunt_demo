# ECS integrated recovery proposal — local preparation, not authorization

## Split cohost activation correction - local, not authority

Observer bootstrap no longer waits for SQL credential provisioning. Its false-default
opt-in starts only observation after approved external readiness, and can send UNKNOWN
heartbeats without claiming healthy backups. Producer has its own false-default flag,
target and repeated private credential handoff gate. Both timers retain integrity/expiry.
This adds zero AWS addresses: the 102-address forecast and USD6 proposal remain unapproved.
It does not resolve or retry SSM. The cold SQL seed/backup/fence/restore/CHECKDB/handoff
transport is still a separate admission blocker; do not create the full trial on the
assumption that cohost autonomy fixes it. New artifact SHA plus actual future S3 VersionId,
current policy/backend concurrency preflight, bounded owner LIVE review and a complete
create/test/retire permission packet remain required before any fresh cloud cycle.


Current wiring/access addendum: [actual SQL opt-in and original external watchdog](COHOST-WIRING-REVIEW.md), including exact SQS/artifact deltas, phase guards and revised grouped-decision wording. Historical sealed ZIP is unchanged; this does not admit theUSD6 cycle. Recommended finite trial observer cadence is300s/deadline1200s; the earlier60s paragraph below is historical, not an installed setting.

Placement update 2026-10-26: [cohost package/units and external UNKNOWN watchdog](../COHOST.md) now have local fixture acceptance. No separate observer EC2 is proposed; the102-address forecast already excluded it and is unchanged. This does not resolve SSM, install bootstrap or admit the cycle. The historical sealed proposal and native evidence remain immutable.

Local implementation update: [four wiring fixes and actual .NET10 image qualification](LOCAL-WIRING-QUALIFICATION.md). The preparation gaps described below record the original planning checkpoint; the four code changes and local image smoke have now passed. Native AWS/SSM/release installation gates remain. Original sealed proposal ZIP is preserved unchanged.

Prepared 2026-10-25 against source `bc57dc44ddf5dd60cfc4c38db5a5bb0fb6b404fa`.
Proposed run `r20261025i1`, account `341936017254`, region `us-east-1`.
**No AWS calls, builds, publication, installation or permission changes were made for this proposal.**
All earlier budgets/cycles are closed. This proposes **USD 6 new**, not a reset of them.

## Recommendation and the actual stopping point

Use the existing DEV platform and its single Terraform owner, one active SQL instance,
one Fargate application, and the existing Sentinel implementation. Run CROSS_AZ first;
SAME_AZ uses the same parameterized mechanism but is a later separately admitted scenario.
Terminate and positively fence the synthetic source before creating its SQL replacement.
Restore into the application VPC, activate the public Fargate route, then qualify the
periodic backup observer and notifications on that same SQL host. No separate observer
EC2, permanent second SQL, PKI, new business service or CloudFormation deployment.

This first reduced scenario measures **recovery request → first public ECS readiness
after a cold SQL restore**. It does not prove continuity of a public service that was
running before the failure. A full public pre-failure baseline requires additional
connection-version/bootstrap work; do not quietly count it as tested. Terminating an
instance is controlled source retirement, not a demonstrated AZ outage.

**Do not start the paid platform yet.** Three asynchronous Run Command failures remain
unexplained, and several small local wiring changes below are still required. Neither
a larger budget nor an IAM simulation makes those prerequisites pass. There is no new
SSM test or alternative command/transport/principal authorized by this proposal.

## Immutable inputs already qualified

| Input | Exact value and limit |
| --- | --- |
| Local CodeBuild image manifest | `sha256:48b67dff2fb9b936975b73adfb15957522519f49928f9a34f68a5182a10fbba8` |
| Image config | `sha256:c5869d49e9731dd03701b73f21f0d94cd105542ba64dadfdc8879df706af5a83` |
| Official base | `docker.io/library/python@sha256:4cea12ab7d78a3312c85f8cab19b6971d4fe9704da25443986c0bc20a6678850` |
| Toolchain | Python 3.13.17; AWS CLI 1.42.76; Boto3/botocore 1.40.76; jq 1.8.2 |
| Protected DEV bundle | SHA256 `dc91ab31610de2b050ee077f3c55b6e29ffd06da1065609840c04d2ca90e9406`, 446,912 bytes |
| Image review ZIP | `ecs-wp4-local-image-review-bc57dc4.zip`, 47,690 bytes, SHA256 `c078a55f2c69db958119d7cf76356ac0807f44c1b26a97821bf1d69e01ffc1c3` |
| Existing evidence | Actual local image: 44 PASS/0 skipped, including extracted-bundle loader; other AWS ports are doubles. Identical LF context/cache replay reproduced the manifest. This is not an independent uncached build, hosted CodeBuild execution, SQL acceptance or AWS installation. |

The Python controller image is **not** the .NET 10 application image or the WP3 release
worker. Its prospective repository is `e1-wp4d-normal-delivery-deploy-dev`; it has not
been pushed. The app must separately use a qualified same-account regional digest from
the protected release path. Do not substitute an old .NET 8 image or host API binary.
See [image source/qualification](../../../scripts/wp4d/CODEBUILD-IMAGE.md) and
[existing cutover contract](SERVICE-CUTOVER.md).

## Inventory and one owner per resource

This is a **source-expanded forecast of 102 managed Terraform addresses**, not a saved
AWS plan or 102 separately billed services. It assumes both protected NAT slots,
enabled data alarms, disabled optional capacity-provider resource, and dispatch enabled.
Current existence/reuse must be read back before admission; unknown retained control
plane resources are not permission to recreate them.

| Existing TARGET layer | Addresses | Exact type/count forecast |
| --- | ---: | --- |
| global | 49 | VPC1, IGW1, subnet4, route table3, association4, public default route1; SG5, SG rule10; ALB1, listener1, candidate rule1, target group2; flow log1/log group1; EIP2, ASG2, metric alarm8; terraform_data1 |
| data | 5 | SQL EC2 instance1, metric alarm3, terraform_data1 |
| platform | 1 | ECS cluster1 |
| apps | 9 | task definition2, ECS service2, log group2, metric alarm2, terraform_data1 |
| edge | 9 | HTTP API1, integration1, stage1, access log group1, VPC link1, route4 |
| Sentinel | 29 | table1; S3 bucket/properties/policy/code object7; queues2/policies2; topic/policy/subscription3; logs2, boundaries2, roles2, inline policies2, Lambda2, mapping1; dispatch rule/target/permission3 |
| **Total** | **102** | Includes three terraform_data addresses; source-to-target replacement adds one EC2 incarnation at the same data address, not a second permanent DB resource. |

Source: `terraform/modules/target/dev/{global,data,platform,apps,edge}` and
`terraform/infra/sentinel-backup/main.tf.json` and its modules. E16 is confirmed to
materialize these TARGET sources: `scripts/practical_dev.py:215–251`; it does not run
the retired legacy roots. Empty protected NAT launch slots initially reduce global
to 43; the full configured global graph is 49. Saved plans must verify this expansion.

Native subordinate objects also need receipts: ASG EC2/root volumes/ENIs, two NAT
private routes and EIP associations owned by the existing NAT controllers, replacement
SQL root volume, ALB/VPC-link/task ENIs, WP4 registered task revisions and short-lived
second-color task, VPC default objects and three embedded DynamoDB indexes. These are
not hidden free resources. The NATs here are **EC2 NAT instances**, not NAT Gateways.

Keep existing runtime names, e.g. `demo-dev-data-sql-instance`, cluster
`demo-dev-main-cluster`, and the blue/green application family. Terraform owns the
skeleton; WP4/E2 alone owns delivery revisions, counts and routing. E16 and WP5 cannot
write the same runtime states concurrently. Security/control-plane IAM is reused only
after identity/hash/existence checks, never created by an indiscriminate security apply.
In particular, protected launch templates, the gateway/CodeBuild factory and NAT
controllers are not included as new objects in 102. If missing or incompatible, stop
and revise the packet/count rather than presenting this conditional forecast as complete.

New Sentinel prefix **R = `ecs-sentinel-r20261025i1`**:

- Bucket `ecs-sentinel-r20261025i1-341936017254`; table R; queues `R-ingestion`, `R-dlq`.
- Functions `R-ingest`, `R-dispatch`; log groups `/aws/lambda/R-ingest`, `/aws/lambda/R-dispatch`.
- Topic `R-notices`; dispatch rule `R-dispatch`.
- Roles `R-ingest-role`, `R-dispatch-role`; boundaries `R-ingest-boundary`, `R-dispatch-boundary`.
- No observer role/profile/network/document: sender is the existing SQL role on the replacement host.

Existing backend `e1-lifecycle-dev-341936017254-us-east-1` keeps its five keys
`e1/lifecycle/dev/{global,data,platform,apps,edge}/terraform.tfstate`, locks and existing
workspace contract. New Sentinel state is `sentinel-backup/ecs-sentinel-r20261025i1/terraform.tfstate`
plus `.tflock`, default workspace only. Preserve terminal states and historical versions.

## Small local changes still needed before an installable packet

These are code-backed gaps, not 17 more configuration decisions for the owner:

1. **Emit protected V2 opt-in.** `scripts/tests/security_root/wp4d.py:761` builds the
   closed installed configuration without `delivery_contract`. The runtime factory
   already supports V2. Add the explicit protected DEV-only selection and regression;
   leave V1 default/emergency unchanged. No caller environment/buildspec override.
2. **Place the replacement in the app network.** `data/ordinary-main.tf` uses
   `private_subnet_ids[0]`. Add a reviewed, membership-checked SAME_AZ/CROSS_AZ selection
   through that owner, not the isolated 15-resource cold-target network or state surgery.
3. **Make local backup clients match the private SQL listener.**
   `operations/sql-backup/ec2_credentials.py:112` currently emits loopback connections;
   its SQL bootstrap client also uses loopback. Preserve the old default, but explicitly
   bind recovery clients to the authenticated own private IP when private-listener mode
   is selected. Otherwise the periodic backup path fails after listener cutover.
4. **Finish the existing host-side connection-version action.** The service plan
   currently validates metadata, not secret publication. Use the same admitted host
   runner, existing CLI and a private file on EC2; emit only ARN/version/key/hash receipts.
   No connection/password values in Terraform, Windows, command arguments or logs.
5. **Select/qualify the .NET 10 application digest through normal release.** Reuse an
   existing qualified digest if current metadata proves it; otherwise complete the
   normal WP3 release path and its admitted source/worker. Controller-image success
   cannot fill this gap.

No workflow deployment, live factory replacement or these patches were implemented by
this planning change. Re-run only their affected suites after implementation; do not
repeat all already qualified tests without a change.

## Identity, access changes and reversal contract

The following is an exact **proposed action/resource delta specification**, not an
installable policy or claim about current effective access. Original snapshots in
`observer-host-work/access-delta` are historical. Admission needs current documents,
PolicyId/default/version metadata, aggregate inline size, boundaries and saved-plan
actions. Bind real ARNs/IDs before one grouped access approval; no policy expansion
after denial without new relevant authority.

| Actor/change | Proposed scope, exposure and reversal |
| --- | --- |
| Existing administrator | `arn:aws:iam::341936017254:user/cnp-cert-admin`, existing Windows `cnp-cert-dev`; prepare/reverse exact deltas only. No switch to admin to execute a denied workload command. |
| Lifecycle operator | `arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`; same E16 lifecycle/saved plans. Existing five-layer permissions must be checked rather than inferred from snapshots. |
| Part4 explicit Deny | Exception only for CreateRole/PutRolePolicy on the two new Sentinel roles and PutBucketPolicy/DeleteBucket on the exact new bucket. Preserve other-role restrictions, AttachRolePolicy Deny, KMS deletion Deny and original-secret deletion Deny. Exception bounded to the approved window; restore original effective document at closure. |
| Managed-policy history | Last retained Part4 snapshot had v5 effective and five slots, including recreated historical v7. If still full, save exact nondefault content before replacement. Restore content, but version ID/creation date cannot be restored. **Fresh version inventory decides whether this irreversible loss is needed.** No silent eviction. Part7 has no proposed blanket relaxation. |
| Operator temporary inline | Only pipeline create/read/update/delete/tag for the exact R resources, own archive/code objects and versions, own table/indexes, exact queues/topic/rule/log groups, two roles/boundaries and PassRole only to Lambda. Compute complete aggregate size before installation; do not attach an eleventh policy to escape a size limit. Remove only this run's inline/deltas after readback. |
| Mapping callbacks | Create/Update mapping constrained by non-optional exact ingest FunctionArn where supported. Get/DeleteEventSourceMapping need regional Resource `*` with the observed provider callback: **real ability to read/delete other mappings in us-east-1**, although execution uses only the recorded trial UUID. Explicitly disclose, expire and remove; do not assert UUID/tag isolation or use permissive IfExists as protection. |
| Regional inventories | Necessary EC2/SSM/Lambda/logs/metrics Get/List/Describe may reveal other regional metadata. No new SendCommand, SessionManager or reboot grant is proposed. SSM remains a separate unresolved admission prerequisite. |
| Backend policy | Add only exact new Sentinel state/lock access to existing operator/backend restrictions. No extra workspace prefixes, deletion of prior states or access to EKS. Preserve/read back current document and reverse own delta with concurrency check. |
| SQL role | Existing `arn:aws:iam::341936017254:role/demo-dev-data-sql-ec2-role`; profile `demo-dev-data-sql-ec2-profile`. Add exact queue SendMessage, exact new backup prefixes, and regional DescribeInstances/DescribeSubnets/DescribeSecurityGroups for positive source/target generation and network checks. The latter exposes regional metadata; code must select the two recorded IDs. |
| Backup S3/KMS | Bucket `terragrunt-demo-sql-backup-341936017254-fa48a32dc9`; prefixes `terragrunt-demo/dev/sql-backups/ec2-20261016/r20261025i1s/runs/*` and `.../r20261025i1t/runs/*`. List only those prefixes; versioned backup read/write required by source/restore. CMK `arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced`: GenerateDataKey/Decrypt via S3 and exact encryption context. Check actual BucketKey context first; no silent bucket-wide fallback. Reverse only run-specific statements. Original prefixes/retentions unchanged. |
| Connection secret writer | Resolve existing name `demo/dev/app/db-connection-string` with DescribeSecret to obtain the actual suffixed ARN. SQL role temporary PutSecretValue/DescribeSecret on that ARN only, private EC2 material only. Protected UUID/version token and custom stage `ecs-recovery-<Trial>`; require an existing AWSCURRENT first. **IAM ability affects all sessions of that role and could write other values/stages on that secret; code's one-version rule is not an IAM guarantee.** No CreateSecret/DeleteSecret. |
| App roles/keys | Existing `demo-dev-app-api-{blue,green}-exec-role`: GetSecretValue on that exact connection secret and actual secret CMK decrypt if required. Task roles keep application-text Encrypt/Decrypt with `arn:aws:kms:us-east-1:341936017254:key/50d3fe36-8128-4d09-ac13-8f5536a230a7`. Backup CMK is distinct. No task secret writes or backup-bucket access. Review current policy before adding only a demonstrated missing grant. |
| Publication/factory | Existing protected publisher only: immutable controller image in `e1-wp4d-normal-delivery-deploy-dev`, versioned bundle in `e1-evidence-341936017254-us-east-1`, key `bundles/sha256/dc91ab31610de2b050ee077f3c55b6e29ffd06da1065609840c04d2ca90e9406.json`. Real VersionId and ECR digest readback precede protected opt-in. No requester ECR writer or runtime override. Existing gateway/cleanup identities preserved. |
| Existing controllers and NAT binding | Reuse `e1-controller-deploy-dev` / `e1-controller-deploy-dev-exec`, `e1-gateway-deploy-dev`, `e1-cleanup-recovery-cleanup-dev`, and `e1-nat-recovery-nat-dev-{assign-eip,change-rt,disable-sdc}` with their existing dedicated execution roles. Bootstrap network plan first; admin binds only actual new EIP/SG/route/instance/launch-template identities to the protected NAT slots before ASG creation. Preserve original bindings for reversal. Current controller permissions and generation ownership must be read back; this is not a grant for arbitrary NAT changes or use of another controller to bypass a denial. |
| Sentinel runtime | Ingest/dispatch boundaries follow existing Terraform: own table namespace, archive and logs; ingest consumes own queue; dispatch queries own indexes and publishes only own topic. **No EC2/NAT/IAM/Secrets/KMS and no NAT dispatcher.** Existing source pinned Sentinel `0e8fc55333ddde3b9816885915310a7e69f3de45`; package the actual current integration, not an old b1 binary. |

**Secret-version residual is a material decision.** AWS cannot delete an individual
secret version. Removing this run's custom label deprecates it but does not guarantee
immediate garbage collection; do not delete the original secret to force cleanup.
The encrypted new connection version can remain after resources retire. Original
AWSCURRENT/AWSPREVIOUS and all original versions must stay unchanged. Administrator
removes only the own custom label after verifying version/stages; see
[PutSecretValue API](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_PutSecretValue.html)
and [version deletion semantics](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html).

## Single execution sequence after the gates are genuinely met

1. **Before paid creation:** current identity/account, concurrency, originals/hashes,
   actual source/AMI/app digest, dependencies and policy/lock/version availability;
   compare the five E16 plans plus Sentinel with this inventory. Resolve all local
   gaps and SSM admission first. Save destroy dependencies and ownership; no source
   receipt or policy snapshot substitutes for current authorization.
2. Create only the own network and source in the common DEV VPC. Two NAT EC2 slots,
   private SQL **t3.medium STANDARD**, encrypted 30GiB gp3 root, no public SQL/SSH.
   Verify the corrected `--no-install-recommends` SQL/CLI recipes natively, installed
   package inventory, SQL active/listener/query and required Secrets Manager use.
   Never purge required ODBC/CLI packages to make an inventory look clean.
3. Seed synthetic encrypted API data, take a fresh versioned/checksummed backup and
   verify S3/KMS/native SQL backup facts. Record recovery request. Terminate the exact
   source generation via the reviewed owner; prove terminated state and fail-closed
   old-endpoint write rejection. Stopped SQL or timeout alone is insufficient.
4. Create target **from zero after the request and fence**, in the chosen other AZ
   within the same VPC. Select the verified source backup/version, restore, CHECKDB,
   decrypt/read and write synthetic data; capture all ordered timestamps and schema.
   Any ambiguous fence/identity or unknown outcome prevents activation and blind retry.
5. Establish the own private SQL listener and task-SG-only TCP1433 path, publish the
   custom-stage connection version on EC2, capture metadata, bind authenticated V2
   evidence, and use the protected WP4 delivery for the qualified .NET image. No
   automigration. Verify task definition's exact VersionId/image/key, task readiness,
   ALB/routing and public HTTP API read/decrypt/write. No traffic/latency claims from
   local fixtures. Record total cold request→public success; report measured RPO only
   from actual final acknowledged writes and backup contents, not a desired target.
6. Qualify Sentinel on the active target with existing producer/observer and pinned
   ingress/store/outbox/dispatch. New subscription to `kendallffernandez@gmail.com`:
   owner confirms, then native SNS readback before enabling. Trial cadence recommended
   60s, maximum 20 event attempts, one incident episode and at most three attempts per
   notice. A target-prefix MISSING observation then a **real fresh post-restore backup**
   supplies failure/healthy transitions. Stale/failed-attempt/UNKNOWN cases must be
   labeled honestly; use local fixtures for supplemental combinations rather than
   claiming deliberately injected data is a native failed backup. Do not alter 2+2
   backup retention or make the 60s trial cadence a production contract.
7. Verify durable ingestion/ACK, receipt/archive, incident/dedupe/recovery and effect
   persistence. Probe effects have explicit supported/unsupported terminal-policy or
   pending classification; do not silently discard them or call the whole outbox
   drained if any active unsupported check remains. Watchdog/host-loss acceptance
   requires an actual external observation; a replacement-host signal is not proof
   that the old host's death was detected. SNS Publish acceptance differs from inbox;
   preserve owner receipt if available, but do not wait for it to clean up.
8. Notify Kendall when public service is actually ready; reserve **30 minutes LIVE**
   inside the existing run envelope for web/API/diagrams review. Static demo remains
   synthetic; final combined observability diagram stays deferred until E2E. Do not
   hold expensive resources indefinitely if the owner does not respond.
9. Stop producer/dispatch/ingestion, export bounded sanitized evidence and native IDs,
   then retire through the actual owners as below. No extra diagnostic loop while
   resources accrue cost. Failures can be diagnosed live within the budget if safe;
   denied/uncertain operations are not permission for a workaround.

## Exactly 17 new-run native values — no synthetic substitution

| Needed fields | Required evidence source |
| --- | --- |
| `source_launch_epoch`, `target_launch_epoch` | EC2 LaunchTime plus immutable instance/generation IDs; not IMDS pendingTime |
| `source_state`, `target_state`, `source_terminated_at` | Fresh EC2 observation, termination transition and bounded source write/fence proof |
| `recovery_requested_at`, `restore_started_at`, `restore_completed_at`, `observed_at` | Authentic ordered owner/host events; not SSM invocation start or later cleanup |
| `task_security_groups`, `network_sha256` | Actual target/task network, VPC/subnet/SG membership and exact reviewed network receipt |
| `source_fence_sha256`, `restored_schema_sha256` | Bound native fencing receipt and restored-schema measurement |
| `secret_arn`, `secret_version_id`, `secret_key_arn`, `connection_receipt_sha256` | Actual exact secret metadata and protected EC2 writer receipt; not a backup TextKeyArn |

The old az6 six-field projection and five additional historical network metadata
values remain historical. No conversion to current authority or V2 acceptance.
Existing az6 142.630783s is prepared-target SQL/API recovery with two repairs, not cold
platform RTO. b1 proved synthetic notices including owner inbox receipt; b2/d1 did not
prove periodic observer execution. Original receipts and packages remain immutable.

## SSM blocker: precise evidence, still unknown cause

| Trial | Accepted command IDs | Result |
| --- | --- | --- |
| b2 | `a3894787-1d3d-430a-9d6d-900578376935`, `e5d894d1-1ce7-4d49-8c4f-bd8a72f5ede3` | Asynchronous AccessDenied / ResponseCode -1; no script-start proof; retired target `i-009e213ec6cf1e3cb` |
| d1 | `b6b92a7d-7dcb-4077-8079-f058add01d02` | Same unresolved outcome; retired target `i-0fbd02588ae2d8e8c`; accepted around 2026-10-24 21:19:45/46UTC |

b2 document `ecs-sentinel-r20261024b2-observer-control` v1 SHA256
`29b383c0a0a1731781ab6c3f828d5945de4afdbbc8912b17f2f495b52a3a66fe`;
d1 document v1 SHA256 `f935d2594162584d9b42e0638ea196330eb7627705076919a1fe565528a6e8bb`.
API acceptance, Online state and static policy equivalence do not prove asynchronous
per-target authorization. The decisive missing evidence is the evaluated asynchronous
principal/session, action, resource/document version and context (including tags/FAS),
and a denying statement or correlated service/agent authorization trace. No encoded
authorization message was captured to decode. Pagination/correlation export defects
were fixed locally; deleted raw logs cannot now be reconstructed. See
`operations/integrations/SSM-B2-DIAGNOSIS-20261024.md` and retained d1 limitation addendum.

AWS Basic Support was observed; included technical-case access was unavailable. No
support purchase, case transmission or another experiment is implied here. A future
explicitly approved diagnostic must first state how it will capture the missing trace;
another status with broader IAM and the same evidence loss is not an adequate proposal.
Session Manager is a different diagnostic option, not permission to run a denied command.

## Budget and stop rules — proposal USD 6 new

Target 2–4h; calculate up to **6 paid hours plus 90min cleanup reserve** (7.5h total).
Absolute authorization ceiling proposed 24h including cleanup, not permission to run
the full platform 24h for USD6. No approval-by-the-minute cutoff. Recalculate committed
charges throughout; begin retirement early enough that remaining worst-case cleanup
fits USD6. No automatic AWS bill cap is claimed.

| Increment, conservative 7.5h allowance | USD |
| --- | ---: |
| SQL t3.medium STANDARD, sequential source/target, conservative .0418/h allowance | 0.3135 |
| Two NAT t3.micro STANDARD, matching protected launch contract | 0.1560 |
| Two public NAT IPv4 addresses | 0.0750 |
| Internal ALB, allowance one LCU | 0.2288 |
| Fargate .25vCPU/.5GiB, conservatively two tasks all 7.5h | 0.1851 |
| gp3, conservative 76GiB full window (both SQL incarnations + NAT roots) | 0.0633 |
| Normal CodeBuild/release allowance, including optional independent phase <=0.50 | 1.0000 |
| Logs/alarms/metrics allowance | 0.5000 |
| Network/transfer allowance | 0.5000 |
| API/Lambda/DynamoDB/SQS/SNS/S3/KMS request allowance | 0.2500 |
| First-month incremental retained image/state/evidence allowance | 0.5000 |
| Cleanup/rate/usage uncertainty reserve | 2.2283 |
| **Requested maximum new spend** | **6.0000** |

These are estimates, not an invoice. Bound the trial to <=2,000 public requests,
<=1GiB transfer, <=0.25GiB logs and <=4GiB incremental retained ECR artifacts for its
first month. Existing retained KMS/secrets/images baseline continues separately; no
free-tier/credits assumed. Beyond-month retained-storage cost needs review, not silent
deletion of historical evidence. Check current regional prices and actual CodeBuild
compute type before admission. No NAT Gateway charge is included because none is proposed.

Primary pricing sources: [EC2 on-demand](https://aws.amazon.com/th/ec2/pricing/on-demand/)
and [official T3 table](https://aws.amazon.com/ec2/instance-types/t3/) (.0104/h micro; .0418/h conservative medium allowance; verify actual regional quote), [Fargate](https://aws.amazon.com/fargate/pricing/)
(US East example .000011244/vCPU-second, .000001235/GB-second),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/) (.0225/h + .008/LCU-hour),
[VPC IPv4](https://aws.amazon.com/vpc/pricing/) (.005/IP-hour),
[EBS](https://aws.amazon.com/ebs/pricing/) (gp3 .08/GiB-month example, verify region),
[CodeBuild](https://aws.amazon.com/codebuild/pricing/) (allowance, exact worker not yet priced).
The remaining lines are explicit usage reserves, not asserted unit tariffs.

## Retirement prepared as part of the same decision

- Retain exact IDs/ARNs/generation/owner and saved plans from creation. Export evidence
  before deleting queues/table/archive/logs; distinguish AWS-native absence from a
  Terraform state assertion. Reconcile uncertain operations before another call.
- Stop host producer/observer and dispatch, disable mapping/schedule; export pending
  effects and terminal classifications. Explicitly set own DDB retirement flag to
  remove deletion protection, then create/review fresh destroy plan. Empty only own
  Sentinel bucket including versions/delete markers/code. Delete own pipeline and
  roles/boundaries via Terraform; no CloudFormation role/bootstrap objects here.
- WP4/E2 retires candidate/active tasks and dependencies before original edge→apps→
  platform→data→global owner plans. Terminate SQL/root disks through EC2 lifecycle;
  verify both incarnations. No standalone DeleteVolume or state removal workaround.
- For the **EC2 NAT** topology, withdraw/retire own ASGs/instances and reconcile
  controller-owned routes/EIP associations before EIPs/network. Honor ASG health/
  replacement controls so cleanup cannot create replacement NAT hosts. This is not
  a NAT Gateway DeleteNatGateway workflow. Never retry the previously denied
  DisassociateAddress as an alternate path; stop and report exact dependency if blocked.
- Retain originals, all prior states and backup objects under unchanged **2+2-day**
  policy. New SQL backup prefixes use that existing retention, not an immediate purge.
  New Sentinel synthetic archive/table/log/queue contents are exported then deleted.
- Remove only the own connection custom stage; acknowledge retained deprecated-version
  residual above. Restore only own protected V2 configuration/image selection under
  its owner; preserve immutable publication/version evidence and original settings.
- Remove run-specific operator/SQL/key/backend statements, restore original effective
  managed-policy documents and archived historical content where replacement occurred;
  verify concurrency before each write and read back hashes/versions. Preserve other
  workers' changes. Record any irreversible policy version metadata loss honestly.
- Native final checks: no own EC2/volumes/ENIs/EIPs/ASGs/routes, ECS tasks/services,
  ALB/listener/TGs/VPC link/API, Lambda/mapping/rule, queues/topic/subscription/logs,
  table/bucket/versions/roles/boundaries remain. Existing retained control plane, original
  keys/secrets/backups/backend are KEEP, not unowned leftovers to delete. Preserve
  terminal states, receipts, explicit retained images/evidence and secret residual.

## What can finish now, and what really needs a decision

**Can conclude today:** local CodeBuild image/bundle compatibility and reproducible
LF cache replay; actual local renderer/contract negatives; historical SQL and synthetic
notice evidence with their limits; this integrated resource/permission/cost plan.
Complete the four bounded local wiring patches above and app-digest metadata selection
without provisioning a platform or inventing new runtime evidence.

**Native work independent of RunCommand, proposed only:** qualify the .NET10 application
through the existing WP3 release/CI pipeline and publish/verify the already built
controller image/bundle through their existing protected owners. This tests code/image
and deployment factory prerequisites, not the denied host command. Allow <=USD0.50
within a future USD6 decision, with **no EC2/network creation until SSM is cleared**.
If source publication, CI-admitted commit, .NET10 worker or protected installation is
missing, name that prerequisite; do not create a parallel diagnostic build service.
No remote workflow or push is authorized by the current local-preparation instruction.

**Real future decisions, grouped once:** (1) approve any evidence-grounded SSM diagnostic
or obtain the missing trace; (2) after local wiring/current read-only preflight, approve
the actual saved-plan resource count, USD6 envelope, exact temporary access/publication
and install changes together; (3) accept secret-version residual and any required loss
of historical IAM version metadata; (4) confirm the new SNS email subscription when it
exists and choose a practical 30min LIVE review time. Recommended technical defaults
above do not need separate cosmetic questions. **There is no installable approved
integrated packet or native E2E PASS yet.** Do not request a blind deployment approval
before the stated gates are concrete.
