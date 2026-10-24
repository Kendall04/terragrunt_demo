# Proposed cold SQL/API trial — local source, NOT APPROVED

Base follows `bb7d88e` and the subsequent host/retirement adaptation. Existing USD1/USD2 trials are closed. No AWS, deployment, IAM change, role assumption, email or host service was executed while preparing this document. Do not present this proposal as approved or as full ECS recovery acceptance.

## Single cycle and ownership

Recommend candidate cycle `r20261024c1`: source root/trial `r20261024c1s`, target root/trial `r20261024c1t`, account341936017254/us-east-1. SAME_AZ and CROSS_AZ use the same host path; choose CROSS_AZ for the next native run, then SAME_AZ in a separately costed run if required. Only one SQL instance may remain active: create a synthetic source, verify backup, terminate exact source and confirm it, then create fresh target. No prepared replacement and no restoration over originals. Exact native AMI/AZ IDs/artifact versions/instance IDs remain admission inputs, not guessed values.

Each root derives 15 objects from `prepare.cold_target`; **30 creations total across the two phases**, with sequential EC2 lifetimes:

| Terraform type | Per root | Total |
| --- | --- | --- |
| aws_vpc | 1 | 2 |
| aws_internet_gateway | 1 | 2 |
| aws_subnet (public and private) | 2 | 4 |
| aws_route_table | 2 | 4 |
| aws_route_table_association | 2 | 4 |
| aws_eip | 1 | 2 |
| aws_nat_gateway | 1 | 2 |
| aws_route (public IGW/private NAT) | 2 | 4 |
| aws_security_group | 1 | 2 |
| aws_vpc_endpoint (S3 gateway) | 1 | 2 |
| aws_instance | 1 | 2 |

Implicit per root: encrypted30GiB gp3 root volume, primary EC2 ENI, NAT-managed ENI, VPC default SG/route-table/NACL. Capture their IDs and lifecycle; they are not additional Terraform owners. No new bucket, CMK, role, profile, Lambda, SNS, SQL replica, SSH ingress or EC2 public IP. NAT EIP is public; hosts have no inbound rules and API/SQL loopback only. Two network roots deliberately avoid importing history; after source termination its NAT can retire before target provisioning after preserving its evidence. Source termination must remain observable: if EC2 no longer returns the exact terminal incarnation, stop activation rather than treating NotFound as proof.

State: existing backend `e1-lifecycle-dev-341936017254-us-east-1`, isolated `e1/lifecycle/dev/recovery/r20261024c1s/terraform.tfstate` and `.../r20261024c1t/terraform.tfstate`, associated `.tflock` and workspace prefixes. No other state or workspace. Original history/backups/keys retained. Existing shared SQL role/profile are proposals to reuse, not presumed effective permission.

## Authority to group before live

Administrator `cnp-cert-admin` via existing profile prepares/reverts exact reviewed overlays; `TerragruntDemoDevOperator` creates/retires roots and terminates synthetic source. Workload `demo-dev-data-sql-ec2-role` restores and reads native fencing; no substitution with administrator on a workload denial.

| Capability | Proposed exact scope / limitation |
| --- | --- |
| EC2 create/network/read/delete/tag | Only above roots/tags/real IDs with complete provider callbacks. IAM multi-resource RunInstances, tagging, AMI/subnet/SG/profile and encrypted-volume controls need fresh evaluation. Regional Describe reads can expose unrelated metadata |
| Source termination | Exact source instance ARN once created; irreversible loss of synthetic source disk/data. No source stop/reboot fallback, no global termination permission |
| Instance-role fencing | `sts:GetCallerIdentity`, `ec2:DescribeInstances` under the exact SQL assumed role. EC2 Describe requires regional `Resource:*`; code requests only source+target IDs, binds OwnerId/LaunchTime/AZ/AMI/target Trial. This is a new read-scope proposal, not an installed allowance |
| PassRole | Exact existing SQL role to EC2, no new role content changes except the explicit temporary inline additions |
| Artifact/backup S3 | Existing bucket `terragrunt-demo-sql-backup-341936017254-fa48a32dc9`; exact versioned artifacts and two new trial prefixes under `terragrunt-demo/dev/sql-backups/ec2-20261016/`. Target gets original source manifest/backup GetObjectVersion, never unrelated historic prefixes. Publisher binding generated only after a new artifact hash exists |
| KMS | Backup CMK30f01bb6-03b5-4e5f-b7a8-e304fe607ced via S3 encryption context for those exact objects/prefixes; text CMK50d3fe36-8128-4d09-ac13-8f5536a230a7 for API Encrypt/Decrypt. No key deletion, unrelated context or plaintext secret export |
| Secrets | Workload reads only existing SQL SA/app secret ARNs already declared in prepare.py. Values remain inside EC2; no workstation export, state values or new credentials |
| Backend | Only above state/lock/workspace keys. Preserve state terminal and originals; check existing bucket policy/Deny and KMS requirements before any exception |
| Execution transport | Existing SSM custom-document route remains UNQUALIFIED after b2 denial. Do not substitute AWS-RunShellScript or another principal. Select/prove an authorized transport or separately reviewed immutable bootstrap action before admission; do not pay for EC2 while discovering this blocker |
| Reversal | Snapshot originals+hashes/version metadata; exact deltas and hashes must be generated from current policies. Shared role overlays affect all its sessions while active. No policy version eviction or wildcard write assumed approved |

No private AWS preflight ran for this proposal. Existing policies/effective permissions are **UNKNOWN**, not a claim that all this is already allowed. Final IAM JSON/hash and saved plans cannot be sealed before permitted readback/native IDs. The old two-host retirement remains default and refuses this state; use `prepare.py bind-cold-retirement --trial <root-trial> --input <exported-state.json>` for one-root scope, followed by fresh native identity/generation/emptiness checks. This emits a proposal, not deletion.

## Test, budget and viewing window

1. New artifact must contain fix5110f5c and cold runner changes, immutable manifest/hash, existing local publish outputs only if source compatibility is verified. Do not overwrite az6 archives.
2. On each native disposable host, capture package metadata and APT recommendations before/after CLI install. Verify CLI installed, both Secrets Manager consumers, absence/presence of named graphical packages as observation, SQL active/enabled, authenticated SELECT1, memory/listener helper, backup, checksum and restore/CHECKDB. Do not claim zero graphics/CVEs from `--no-install-recommends`: other base/SQL packages still have their existing installation policy.
3. Source produces the pre-backup and post-backup markers through existing helper. Verify immutable backup availability. Operator terminates exact source; target performs its own native STS/Describe read before restore and at login/API write boundaries. Unknown/denied/missing/mismatched source stops without retry or activation. Existing `.started` files prohibit blind replay; retain `fence-N.json` summaries even when later steps fail. Correct only a demonstrated problem under the same approved authority, otherwise retire.
4. Target restores selected version from source prefix to a target-trial DB name. CHECKDB, decrypted pre-marker, absence of post-backup marker and fresh API read/write use existing helper. `RtoColdHostSeconds` includes target provisioning; `RtoWarmTargetSeconds` is null for cold. Full ECS acceptance remains false.
5. Reserve proposed30min owner viewing **after actual readiness** and notify Kendall before teardown. This isolated root exposes no public API: native host/API evidence can be shown through an already-authorized proven access mechanism, plus local demo and historical diagrams clearly labelled. If Kendall needs the real Fargate/public API live, this 30-resource proposal is insufficient and must be replaced by the complete ECS lifecycle plan rather than advertising loopback as live ECS. No new tunnel or browser access is assumed.
6. Export evidence, retire own NAT first with native wait/reconciliation, then saved complete destroy; source and target states remain separate. No DisassociateAddress retry, DeleteVolume workaround, state surgery or unrelated prune. Verify ENI/volume/EIP/network absence, preserve state/evidence and existing2+2 backups, revert every overlay and compare originals. Do not wait for inbox/user response to consume cleanup reserve.

**Budget proposal: USD4 NEW for this isolated host trial**, subject to exact tariff and ingress/download-size admission. Objective4h, plan no more than6 paid hours plus90min cleanup reserve, overall ceiling24h including any blocked cleanup; no extension of paid runtime just because ceiling is24h. Not approved and not an automatic billing cap.

Conservative planning arithmetic: assume EC2 <=USD0.10/h (upper-bound admission assumption, not a verified quoted t3.medium price), at most one running EC2; two NAT gateways/EIPs conservatively charged throughout7.5h; two30GiB disks conservatively charged throughout7.5h. Fixed allowance <=7.5*(0.10+2*0.045+2*0.005+60*0.08/720)=USD1.55. Reserve USD0.225 for <=5GB NAT processing, USD0.25 transfer allowance subject to actual route/rate, USD0.25 S3/KMS/requests, USD0.50 retained incremental storage and USD1 cleanup uncertainty: total aboutUSD3.78. This is an admission envelope, not actual billing; source setup is included, prior retained baseline spend excluded and disclosed separately. No free-tier/credit assumption, no new CMK baseline, STANDARD CPU credits.

Official consulted sources: [VPC NAT/IPv4 pricing](https://aws.amazon.com/vpc/pricing/) (NAT example0.045/h and0.045/GB; IPv40.005/h), [EBS pricing](https://aws.amazon.com/ebs/pricing/) (gp3 example0.08/GB-month; verify actual us-east-1 rate), [EC2 on-demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/) (actual Linux t3.medium rate must be bound; public page did not expose a reliably parsed exact rate in this review). Tax/exchange not included. If actual regional values, transfer bound, artifact size or retained data exceed the envelope, revise proposal before starting. Abort new test work at projectedUSD3 to retainUSD1 cleanup; retire earlier if projected completion/cleanup will exceedUSD4. Use conservative resource-hour accounting/readback, never infer budget remaining from delayed billing.

## Remaining admission blockers

This is executable/reviewable local source, not a sealed approval packet: (a) artifact qualification and AMI/native package graph, (b) proven permitted execution transport after b2, (c) current IAM/backend/KMS originals and exact deltas, (d) native plan/IDs and real fencing traces, (e) viewing method. Full Fargate cutover additionally requires application-network SQL reachability, connection-secret refresh, task replacement/readiness and public API receipt. Do not silently add those resources or use this estimate to fund them. A real zone failure still blocks if exact source termination cannot be confirmed; independent durable fencing authority would require a separate architecture decision. No mandatory-access bypass or new budget follows from this proposal.
