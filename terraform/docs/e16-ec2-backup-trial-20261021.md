# EC2 SQL backup trial and partial retirement - 2026-10-21

## Observed outcome

The owner approved one private EC2 SQL/backup trial in account `341936017254`,
profile `cnp-cert-dev`, region `us-east-1`: USD 3 incremental, four hours, normal
data/global retirement including the retained DEV network. This was a new
envelope; the old USD-10 approval was not reused. Trial source was
`b1f506329a30c96bd134134ea1d4d1297256becc`. The existing Linux package came from
`8009b2126d90fd43a09ecf6cadd728d5b4a64347`, SHA-256
`a83aedcc2c955c891b984f1385fd5ca3ce81ef577c0ea67a9059796f0cbb3e40`.
No EKS/RDS work, application reconstruction, push or CI deployment was performed.

Conservative window: 04:10:51 UTC; first billable resources independently observed
04:11:59; retirement target 07:10:51; absolute deadline 08:10:51. Retirement began
06:01:07 and the controlled abort was independently checked at 07:23:18, without
extending the window. No future AWS operation was scheduled.

The EC2-role CLI acceptance passed on private SQL `i-0382d6b731ee71276`:

| Activation | Actual systemd start/end UTC | Result |
| --- | --- | --- |
| Manual | 04:51:55.472 / 04:51:58.729 | REMOTE_VERIFIED_CLEANUP_VERIFIED |
| First real hourly | 05:00:00.537 / 05:00:03.973 | REMOTE_VERIFIED_CLEANUP_VERIFIED |
| Second real hourly | 06:00:00.536 / 06:00:04.479 | REMOTE_VERIFIED_CLEANUP_VERIFIED |

These were real hourly timer activations, not accelerated runs. Three distinct
receipts contain native-checksum verification, hashes and exact S3 versions;
independent HEAD reads matched version, size and KMS metadata. Additional
administrator GetObject was denied by backup-key Decrypt policy and was not
retried or used to justify new access. The service role's existing verification
receipts are the content-integrity evidence, not independent administrator
decryption. No cross-AZ restore, application recovery, RPO or RTO was qualified.

Original cloud-init ended with a SQL login timeout and absent `demodb`, despite
the engine becoming active. Only the originally intended database creation was
repeated after absence/readiness checks; application-login creation and the full
bootstrap were not replayed. This is qualified backup acceptance with bounded
bootstrap recovery, not proof of unattended bootstrap reliability.

## Retirement and remaining authorization boundary

Timer disabled and host inhibited/idle at 06:01:07. Normal E16 inhibition passed,
SQL stopped, NAT capacities became zero and their members terminated. Native
supervised review passed; executor finality remained NOT_CERTIFIED and historical
UNKNOWN/late-effect risk was not rewritten. Data DOWN plan
`b92361f5-a4e9-426f-9e17-deb18b30b2d1` completed with empty data state.
Global plan `819c61b2-c7ac-4c3c-a128-753d9b4ef76d` ran once, deleting 36 of 49
objects and retaining a consistent 13-object state after AWS authorization errors.

CloudTrail at 06:57 identified missing companion-resource authorization:
`ec2:DetachInternetGateway` on the VPC and `ec2:DisassociateRouteTable` on four
subnets. The same dependency had been recorded in the
[14 October teardown](first-real-dev-teardown.md#live-teardown-progress-and-partial-global-reconciliation).
The preflight did not catch its recurrence in the installed E16 operator policy.
No denied operation was retried; APIs/administrator credentials were not used to
bypass that denial. The owner declined further IAM expansion for the night.

Remaining objects, all represented by global state serial 32, version
`PTkX9xn6vXQDslqYcv1Fyg735KPuskKv`:

- VPC `vpc-017f50f3b40b21785`; IGW `igw-0d4e248e82c640617`.
- Subnets `subnet-002441433be4b18c5`, `subnet-02931eb49d10fe92d`,
  `subnet-0bf6f0d075c7be656`, `subnet-0dd74a8d746d82537`.
- Route tables `rtb-0bc770d688d1aafca`, `rtb-0fc1395d7f92b8b21`,
  `rtb-05bc1ed5492fe9c13`.
- Associations `rtbassoc-02edc81951b5d7b0b`, `rtbassoc-048eae820401c66f8`,
  `rtbassoc-0416f8ef9803d15ba`, `rtbassoc-046e7ba84a3525c91`.

At final readback no trial live instance, known root volume, ALB, EIP, ASG, ENI,
endpoint, alarm or network log group remained. Data/platform/apps/edge states
were empty. The result is **backup PASS; retirement PARTIAL/BLOCKED**, not full
network closure or zero AWS cost.

## Security close and retention

The SQL backup inline and all three temporary backup-key Sids were removed.
`EcsSqlTrialShutdown20261021` was removed and absence verified at 07:22:30.
Operator policy defaults returned to Part5 v2 / Part6 v6; trial versions were
deleted. Original E13 role/config/target bindings were restored, own Lambda v5
and NAT launch-template v3 versions removed. All final restoration checks passed.
The NAT rule remains DISABLED, five executor concurrencies remain zero, and the
two deployment workflows remain disabled. Restoring configuration after the
abort closes the old E16 proof/session; it must not be replayed as current proof.

Backend, backup bucket, original roles, both CMKs and three secrets were retained.
Old backup-prefix retention was preserved. New backups have current/noncurrent
2+2-day lifecycle rules; the package has 1+1-day rules. Lifecycle is asynchronous,
not an exact-time deletion guarantee. The planning estimate was USD 1.35 with
contingency, under the USD-3 limit; final billing was not verified. Retained
S3/KMS/secrets/backend/evidence still have costs.

The external execution evidence is in the 2026-10-20 `task-4` workspace:
`ecs-trial-abort-closure.json`, `ecs-final-inventory.json`,
`ecs-global-denial-summary.json`, and the three service receipts. No credential,
secret value, raw diagnostic, backup payload or state body is committed here.

## Next boundary and offline prevention

Only five missing-resource ARNs are proposed for a future temporary operator
grant: DetachInternetGateway on this exact VPC and DisassociateRouteTable on these
four exact subnets, with RequestedRegion us-east-1. It is **not installed**.
The minimal future proposal is `ecs-future-residual-authorization-minimal.json`;
do not reinstall the old trial policy, stopped-instance/ASG privileges, optional
DeleteVolume/DisassociateAddress grants, failed binaries or old session proof.
Future authorization needs fresh identity/state/policy/inhibition review and a
new remaining-resource plan. The 07:10 IAM simulation predates policy restoration
and is neither current authorization nor proof that every future prerequisite holds.

Before any later billable creation, use the
[offline companion-resource audit](../../scripts/retirement_preflight.py) on current
exported operator policies, then review actual ARN bindings and complete live IAM
multi-resource results. The focused audit catches this known missing resource-type
pair; it does not evaluate IAM conditions, Deny, boundaries/SCP or installed drift,
and never authorizes creation. Existing E16 guards and limits remain unchanged.

## Residual-only follow-up - 18:10 owner approval

The owner subsequently authorized both the exact missing-resource grant and the
six-file local patch. This did not renew a spending envelope or permit runtime
creation. The original global root was copied from clean b1f5063 and used with
the same operator, backend and lock scope for a fresh residual-only destroy;
the closed E16 session/proof was not resumed or rewritten. Current control
fences, E2 RELEASED/no schedule and inactive protected builds were read back.

Temporary `EcsSqlResidualNetworkCleanup20261021` contained only the two approved
actions on the exact VPC/four subnets, region us-east-1, with a fresh restrictive
19:05:20 UTC expiry. Per-resource simulations covered both resource classes and
the remaining deletes. New plan SHA-256
`c83ab931c806932ace51bf9f381d44394326a3bbf79f4b46b65719ea9cac54f9`
contained exactly the 13 deletes, no creation/replacement. Apply completed at
18:28:12 UTC; global state serial became 33, lineage unchanged, S3 version
`HiyXH2DxSvGIaH.S_XY1Mvl2nOHn4wG1`. The temporary policy was removed and absence
read back at 18:29:42, before its expiry.

Readbacks at 18:30:54 found no VPC, subnets, route tables/associations, IGW, ENI,
live instance, known root volume, EIP, ASG or ALB. All five runtime states were
empty and all five state lock objects absent. Original trial/SQL temporary
policies remained absent, the rule remained disabled and five concurrencies
zero. Backup bucket, original keys/secrets/roles remained retained. An additional
operator DescribeVpcEndpoints observation was denied once; it was not granted,
retried or queried with another identity. Terraform did not need that observation
for this 13-object plan; VPC absence was independently verified.

This supersedes the *current* residual-network blocker, preserving the morning
partial outcome above as history. Evidence: `ecs-residual-20261021-1810/` in the
same external execution workspace (plan/apply, permission removal, final states
and locks). Retained resources still incur costs; final billing was not audited.
The local audit remains manual. P2 integration before paid deployment is still
pending; neither this patch nor its structural result grants creation authority.
