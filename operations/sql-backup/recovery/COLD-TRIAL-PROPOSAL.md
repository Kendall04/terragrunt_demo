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

## Focused preflight completion — local, 2026-10-24

The four previously Windows-skipped POSIX host-main tests now **PASS4/4** using existing Ubuntu-24.04 root/Python3 and `/opt/codex-artifacts`, temporary fixtures cleaned normally. No package installation, AWS, SQL engine, agent, host service or credential access. These are filesystem/main-entrypoint tests with fake ports, not native SQL or SSM proof. The earlier Windows skip result remains historical, superseded only for this POSIX gate.

### Exact small artifact and preserved binary inputs

Local delivery directory: `C:\Users\PC-2024-01\Documents\Codex\2026-10-22\task-3\cold-c884930-preflight`.

- `cold-helpers-c884930.zip`: **27111 bytes**, SHA256`c5cb8ddecd2439192399da8eca73ba112298a74bcfc7313164d9caf6a1fe5db3`. Deterministic Git blobs from c884930: host.py, prepare.py, verify_effective.py, bootstrap.sh (includes5110f5c).
- `artifact-lock.json`, `api-payload-manifest.json`, `backup-payload-manifest.json`: bind all helper hashes and existing383 API files /237 backup files. Each actual file was rehashed and size-checked against its preserved qualified manifest. API source diff6b2ea75→c884930 and backup compiled-input diffb2bf8d8→c884930 were empty. Backup embedded build identity remains b2bf8d8; do not relabel it as freshly compiled c884930.
- The compiled sources and existing caches were reused: no rebuild, install, extra binary payload copy or large archive. Original recovery tar and receipts remain untouched. This is an exact **composite input lock and helper overlay**, not a materialized all-in-one deployment archive or native qualification of this composition. Final assembly/installation must validate these manifests before any future use; do not promise an upload-ready approved runtime from this ZIP alone.

### Offline IAM deltas anchored to saved originals

`access-review.json` binds raw/canonical hashes and original paths under `observer-host-work/access-delta`. Originals were read at b2 admission around05:40UTC and its closure07:01:54UTC attests restoration; no fresh AWS read was performed. Current policies/attachments/boundaries/key versions remain UNKNOWN.

| Local proposed file | SHA256 | Exact change |
| --- | --- | --- |
| backend.proposed.NOT-INSTALLABLE.json | ffb2c2f163b5fe28ba50b9b8ca8c158e396aade69764bbe0bc267fe20b821ffd | Four exact exceptions in E16NoOtherDevObjects for the two trial states+locks; additive own Get/Put, lock Delete and exact List prefixes. Every other original statement preserved |
| backup-key.proposed.NOT-INSTALLABLE.json | 0f9047e8262704bf40cfa4bac8f4138fdcddb6f1346ba37321eb2b9a9c1abf5b | Append SQL role GenerateDataKey/Decrypt through S3 for only source/target new prefixes; original statements unchanged |
| sql-role-read-addition.NOT-INSTALLABLE.json | 371a63e6cf9c0ca993d86cd8d557f94a76e0ab9d6ee091182b0093f6924c8eeb | DescribeInstances, Resource*, regionus-east-1; regional metadata exposure, not resource mutation |

Part4v5 and Part7v3: **no modification proposed** for these deltas; their existing IAM/bucket/key-delete denies are not removed. Workload role changes are administrator preparation, never operator PutRolePolicy against its existing Deny. No policy-version eviction assumed. Default workspace only for this cycle: contrary to the broader initial candidate description, non-default workspace prefixes are NOT excepted. State deletion remains ungranted; only lock deletion.

Local assertions verified preservation of all other original backend/key statements, exactly four new backend exceptions and no wildcard/workspace object exception. The three files intentionally have no bound approved expiry and are labelled NOT-INSTALLABLE: timed identity/resource-policy conditions, originals freshness and reversal must be completed before any install. No claim of automatic exception removal at expiry. Missing source snapshots: complete current SQL role inline/boundary and application text-key policy; fetch metadata only in a separately authorized read-only admission, never infer Allows from these additive documents. Operator create/delete/pass-role/SSM and quota checks also remain necessary. These deltas do not solve b2 authorization.

### Transport: specific preflight instead of an execution promise

Retain the planned same-principal, exact custom SSM document/instance route. No AWS-RunShellScript substitution, new principal, wildcard admin, retry of a denied command or alternate bootstrap control path is introduced here. b2 accepted SendCommand but terminal AccessDenied/−1 had no script start; the approved context supplement failed to resolve it. The exact policy evaluation cause is still not demonstrated.

Minimum future read-only admission: compare identity/account/role and all effective role policies/boundaries/session constraints with originals; retrieve exact custom document owner/ARN/version/hash; correlate preserved SendCommand and invocation details (name/version/plugin/target/error/times) with **existing** CloudTrail/agent authorization evidence if available and already permitted. Inspect only sanitized metadata/errors, not credentials, command secret output or application values. IAM simulation may corroborate supplied context but cannot discover the actual denied context or prove asynchronous agent authorization. Do not enable logging/services or change agent settings as an incidental read.

If those reads cannot demonstrate the denied evaluation and a specific approved correction, **stop before creating paid resources**. Required next action is obtaining the exact denied authorization trace (or an administrator review using existing logs), followed by a narrowly reviewed fix. A healthy SSM registration or successful static simulation does not clear this gate. One retry would require new relevant evidence that addresses the known non-executed rejection. This proposal therefore remains NOT ADMISSIBLE for live rather than promising that the transport works.

### What the two phases are, and what full ECS LIVE adds

30 creations are **two sequential phases of one scenario**, not two successful recovery scenarios: source15 creates a new synthetic DB, writes markers and commits a versioned backup (not a new EBS snapshot); then exact source termination; target15 creates from zero and restores. SAME/CROSS are modes; the next candidate runs one mode, not both for the price of one. Retained originals outside those two new prefixes, states and tagged IDs are never source teardown targets. The disposable source is expressly included in the proposed destructive consent, not an ordinary historical/production DB.

The isolated runner never reports full ECS recovery. Minimum full-service integration plan, to implement/review separately without expanding this candidate:

1. Use the existing application's private SQL networking contract, with SQL1433 allowed only from the application task SG. A replacement in a different isolated VPC with ingress empty cannot serve those tasks. Prefer restoring into the application VPC/subnet under one Terraform owner; do not add peering or import resources merely to preserve the disposable test template.
2. Preserve a single SQL writer and obtain exact source fencing; restore/check schema and decrypt markers before promoting application traffic. Keep app-text KMS and SQL credentials distinct from backup encryption. Change the connection reference outside Terraform secret values.
3. Through WP4/E2 delivery ownership, create fresh candidate task revision(s)/connections, verify each candidate SQL/KMS `/ready` and public API write/read/decrypt, then move ALB traffic. Terraform must not compete for task/count/listener fields. Existing image rollback cannot rewind DB/schema.
4. Show the actual public API/web to Kendall and the existing Archify views with honest historical labels during the reserved window; signal LIVE only when the public deployed service responds. Static local demo or loopback evidence alone cannot satisfy that request. Measure total request→publicAPI readiness and separately record cold-host time.
5. Produce the complete infrastructure/delivery plan including currently-down application/network layers, actual resource counts, policies and a new costed envelope before asking consent. The 30-object/USD4 estimate excludes this full-service reconstruction and cannot fund extra Fargate/routing resources silently. Until that plan and transport proof exist, prefer the local gates and do not request approval for an incomplete LIVE promise.

### Transport investigation result superseding the earlier evidence gap

Real read-only AWS investigation is now recorded in [SSM b2 diagnosis](../../integrations/SSM-B2-DIAGNOSIS-20261024.md): the exact updated inline was installed, a fresh operator session had no passed session restrictions, both document reads/API sends were accepted, and the target authorization still failed before execution. The next action is obtaining the **service-side per-target authorization decision for the two command IDs**, not another guessed permission or new instance. Existing CloudTrail has no actual asynchronous condition-key evaluation. Current Part4v5/Part7v3 match snapshots and inline is absent; remaining policy state is not inferred. This new evidence narrows causes but does not unblock paid creation or authorize retry.
