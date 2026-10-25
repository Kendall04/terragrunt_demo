# ECS recovery: final local preparation and the remaining LIVE gate

This is the single forward checklist after the installed-bundle work at
`29120514c64f7c7b36b680e7251da96b19d849e2`. It replaces the earlier "next local
projection" item, not the historical receipts or the existing runbooks. No AWS,
image build, installation, approval publication or new budget was executed here.

## Preserved evidence and the projection's limit

`receipt_gaps.py` reads only three explicitly supplied, SHA256-pinned historical
host-action JSON files. It verifies their embedded receipt bytes using the
original `host.private_write` encoding, successful action results, source/target
identity, runtime host binding, backup/manifest version agreement and exact
100ns-capable event ordering using `host.event_order`. It exports selected fields
and fixed explanations, not arbitrary nested content, secret values or raw logs.
No additional evidence/approval schema or publisher is introduced.

The actual az6 source/quiesce/restore receipts match their original closure and
integrity addendum. The report maps only account, region, historical recovery ID,
source/target instance IDs and CHECKDB result: **6 known historical fields**.
The other **24 V2 fields remain UNKNOWN**, including schema/writer authority,
source termination, exact launches, request/restore epochs, fresh observation,
private endpoint/network, connection version, restored schema and bound proof
hashes. IMDS `pendingTime` is not substituted for EC2 LaunchTime, SSM invocation
start is not restore start, SQL inactive is not EC2 terminated, and retirement
after the experiment cannot retroactively fence it. A TextKeyArn in a backup
manifest cannot supply missing connection-version/schema evidence.

The report is deliberately **not** an `E1_SQL_RECOVERY_EVIDENCE_V2` object and
always has `EvidenceAuthenticated`, `AllowsCreation`, `AllowsActivation`,
`AllowsBindingPublication` and `NativeAcceptanceV2` false. External pins and hash
agreement prove retained local consistency, not AWS provenance, approval or
current state. It cannot be promoted to an approved binding even if someone
adds approval/current-state labels to the input. Historical measured 142.630783s
remains prepared-target recovery time, not full cold ECS RTO or a production RPO.

Run locally, with the existing Python (no AWS client):

```text
python -I -B operations/sql-backup/recovery/receipt_gaps.py --source SOURCE.json --source-sha256 EXPECTED_SHA256 --quiesce QUIESCE.json --quiesce-sha256 EXPECTED_SHA256 --restore RESTORE.json --restore-sha256 EXPECTED_SHA256
python -I -B -m unittest discover -s operations/sql-backup/recovery -p test_wp4_recovery_contract.py -v
```

Expected hashes must come from the independently preserved receipt inventory;
calculating a new hash after editing does not authenticate an input. The CLI
refuses inconsistent inputs and prints only a fixed failure code. It does not
write or amend any source receipt. Report output may be saved outside the repo.

## What is already covered — do not repeat it as another preparation cycle

| Coverage | Evidence and boundary |
| --- | --- |
| Cold source/target identities, fencing negatives, backup/time/endpoint/rollback plan, renderer/listener contracts | Previous 176-test, 12-suite recovery CI PASS; real Bash/jq rendering, runtime effects otherwise doubles |
| V1 authorization/delivery | Previous 20 + 98 PASS after shared contract changes |
| Emergency/cleanup/recovery | Previous 53 PASS; actual core, synthetic ports |
| Installed loader/factory/history/publication | Previous 40 WP4D PASS including 7 extracted-bundle cases; V2 opt-in, no V1 promotion, V1 emergency and bounded cleanup compatibility |
| Historical receipt projection | 8 new tests + the 13 existing V2 tests = **21 PASS**, zero skips; now included through the same explicit CI suite shim |
| Actual az6 retained bytes | Three original file hashes plus embedded receipts, closure and integrity addendum checked locally; 6 known/24 UNKNOWN, no native V2 acceptance |

The prior 387 local tests were not all rerun for this separate report-only change.
The affected suite was run; unchanged runtime/bootstrap/bundle bytes are verified
against the sealed 2912051 packet. There is no claim of a new full 184-test CI run
or hosted CI execution. Native az6 proof remains historical SQL/API on a prepared
target with two repairs. Sentinel b1 proved bounded synthetic notices (including
user-reported inbox delivery); b2/d1 did not prove the periodic observer working
on AWS, and total outbox draining was not established.

## Minimum ordered steps to an actual ECS test

1. **Resolve execution admission once, with evidence.** The intended operator and
   workload roles must pass the actual required transport contract. The b2/d1
   asynchronous SSM AccessDenied cause remains unproved; this report neither
   retries it nor authorizes another document, principal or transport. Review any
   new diagnostic separately if required. Before spending, read current identity,
   role/boundary/deny/context, document owner/version/hash and current deployment
   metadata; historical policy snapshots are not effective permissions.
2. **Admit one complete platform plan and immutable release set.** Reuse the
   existing global/data/apps/edge layers and WP4/E2 deployment owner, one active
   SQL instance and one new target at a time. Include the real Fargate/ALB/public
   route, SQL private network, S3/KMS/secrets, backup observer/Sentinel dependencies,
   implicit volumes/ENIs/logs and create/read/update/delete callbacks in the saved
   plan and permission packet. The earlier isolated 30-object/USD4 proposal does
   not cover reconstructing full ECS. All prior budgets are closed: calculate and
   approve the new total, exact IAM/secret writer scope and teardown together.
   Recommend a short run inside the 24h ceiling, reserve 90min for retirement and
   a 30min owner LIVE review window; neither is a billing auto-cap. Missing current
   plans/prices prevent an honest fixed resource count or cost for this full test.
3. **Create authentic cold-recovery evidence, not a warmed receipt.** Start a
   disposable synthetic source, verify a versioned/checksummed S3 backup and KMS
   usability, record the recovery request, then terminate the exact source
   generation and positively verify no continued old-endpoint writes/connections.
   If fencing is uncertain, stop before enabling target SQL/writes. Create the
   single target from zero after that request/fence, in SAME_AZ or CROSS_AZ mode,
   and restore/validate CHECKDB. The second AZ mode can be a later sequential
   scenario; no permanent second SQL or claim of a real AZ outage is needed.
   Capture native launch/state/request/fence/restore timestamps and identity-bound
   proof hashes as the actions occur. Missing evidence stays UNKNOWN.
4. **Activate through the existing service owner only after data/route proof.**
   Observe the exact private SQL listener and task-SG network, publish/verify the
   connection-secret version through the separately approved secret writer, and
   independently approve compatible image/restored-schema and migrations-off
   evidence. Select V2 only through reviewed protected installation/configuration.
   New candidate tasks must fetch that version; existing tasks do not refresh it.
   Run E3, switch through WP4/E2, then public `/ready`, old-marker decrypt/read and
   fresh write/read. Measure request-to-public-ready including create/bootstrap,
   restore and any repair time. A loopback API or rendered task cannot close this.
   Rollback means a newly approved compatible image against the SAME restored DB,
   never the terminated endpoint or an assumed rollback of DB migrations.
5. **Close the useful observer/Sentinel path and let Kendall inspect LIVE.** Use
   the existing TF/TG Sentinel module and producer/observer, no CloudFormation in
   the final path. Establish authenticated ingestion, durable state/receipts,
   ACK/cancellation, supported probes versus explicitly unsupported pending work,
   and reconciled outbox status. Agree the periodic cadence/staleness policy if
   not already fixed. Use a confirmed subscription for bounded readable failure
   and recovery notices; SNS acceptance is not inbox proof. Notify Kendall when
   web/API/diagram navigation is actually ready and keep the agreed window within
   budget/retirement reserve. The final joint observability diagram remains
   deferred until E2E; PKI and extra business microservices stay out of ECS.
6. **Export, retire and verify without waiting indefinitely for a response.**
   Preserve original states/backups and their 2+2-day policy. Save identities and
   teardown scope at creation, reconcile unknown outcomes, remove only owned
   resources/data via a fresh reviewed destroy plan (own NAT first if created),
   verify native absence and reverse exact temporary IAM/backend/KMS deltas with
   concurrency checks. Preserve terminal state and evidence. Unsupported probes
   or residual/UNKNOWN outbox work must remain visible in the final result.

These are execution gates, not six more local frameworks. Local design is ready
for review; missing native provenance/current installation/transport and a full
platform admission are the remaining blockers. No further broad audit or repeat
of unaffected local suites is needed before addressing those gates.

## Image/bootstrap/config — concrete local candidate, 2026-10-25

The inputs are no longer an unspecified base/image proposal. The versioned
[CodeBuild image recipe, lock and reproduction steps](../../../scripts/wp4d/CODEBUILD-IMAGE.md)
pin the official Python amd64 base, 13 verified wheels and existing jq. The image
was built with RUN network disabled, repeated from the identical LF context with
the same manifest digest, and passed **44 local-image tests / zero skips**. Its
manifest is `sha256:48b67dff2fb9b936975b73adfb15957522519f49928f9a34f68a5182a10fbba8`.
The historical Lambda base is separately identified from repo evidence; it is
not confused with CodeBuild or asserted to be currently installed. No registry
push, image tar, AWS call, IAM/runtime installation or new budget occurred.

The remaining 24 unfilled acceptance slots are now separated, not blindly called
24 unknown inputs: **2 reserved contract labels are known**, **5 historical
metadata values are available locally**, and **17 actual-run values are absent**.
The five are the retired target private address, VPC, subnet, DB SG and hash of
its loopback precheck projection. Their state/native-readback sources agree, but
they do not prove an application listener, current membership or fresh authority.
The original gap report/receipts remain unchanged; no historical value is promoted
to a current approved binding.

### Exact 17 missing values and their required source

| Fields | Required evidence in the next admitted native run |
| --- | --- |
| `source_launch_epoch`, `target_launch_epoch` | EC2 LaunchTime with exact instance/generation/account/region; never IMDS pendingTime |
| `source_state`, `target_state`, `source_terminated_at` | Fresh exact-host control-plane readbacks; source terminated before enabling target writes, with confirmation time and old-writer/connection checks |
| `recovery_requested_at`, `restore_started_at`, `restore_completed_at`, `observed_at` | Captured request, actual restore start/end+CHECKDB and final fresh observation; retain original precise UTC before epoch projection; never SSM dispatch times |
| `task_security_groups`, `network_sha256` | Current protected membership plus native task/DB listener, VPC/subnet/SG/route observations, bound in the network receipt |
| `source_fence_sha256` | Exact identity-bound native fence/write-inhibition receipt; no synthetic assertion or teardown-after-restore substitution |
| `secret_arn`, `secret_version_id`, `secret_key_arn`, `connection_receipt_sha256` | Approved writer's exact connection-version metadata/readback and correct application key purpose; no secret values in state/logs and no substitution of backup CMK or SA/app password secret |
| `restored_schema_sha256` | Native restored-schema fingerprint and independently qualified compatible migrations-off image; no guessed fingerprint or assumed schema rollback |

These fields must be captured during the real run, not filled by more retrospective
local JSON. The five available historical values also need fresh validation for
the new run. The next action is to resolve execution admission/current metadata
and review one complete platform plan, budget and withdrawal window. The built
image is ready for that review; it supplies no new execution or approval authority.
