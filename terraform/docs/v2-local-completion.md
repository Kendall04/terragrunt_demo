# V2 local completion checkpoint - 2026-10-23

This is a bounded local implementation/evidence checkpoint, not deployment or
permission to reset the original aggregate USD 2. The owner asks to advance both
projects from their respective Pages. The [ECS Page](https://chatgpt.com/space/page_6ad2223a7ed88191be14aba8886d669d)
and [log](https://chatgpt.com/space/page_1b0bc56020908191a7d18292c70468c6)
were read successfully. Their seven phases and user-added criteria remain open
where evidence is missing; the Page itself was not edited by this worker.

## Implemented local increment

The actual remote-enabled Protocol.Check could return HEALTHY from a recent
remote backup after the same producer had recorded a later FAILED attempt.
The local failure was checked only when store was null. The correction checks
that existing configured local attempt before remote freshness, after the
expected-UP gate. It adds no schema, dependency, framework, emitter or IAM action.
Three new regressions first failed with expected FAILED/actual HEALTHY. Five new
signal tests now pass within the complete CLI suite: 56 PASS, 1 native SQL integration
skip. Maintenance preserves the failure file; a later verified backup naturally
clears it. Malformed/denied remote evidence still cannot become MISSING/HEALTHY.

Four separate production host.main entrypoint regressions pass on actual POSIX
private paths. SQL/API/AWS ports, identities, executables and timing are explicitly
synthetic. They exercise source -> quiesce -> restore from empty directories,
seven-digit manifest preservation, private parent/config/receipt permissions,
durable STARTED/no-replay after backup failure, wrong identity/hash refusal before
secrets/SQL, and refusal to repair/reuse pre-existing staging. These are entrypoint
contract tests, not native SQL, process-management, AWS authorization or recovery
acceptance. The earlier native backup/manual-restore component proof remains
separate, as does az6's actual prepared-target 142.630783 s RTO.

## Backup alert consumer contract

The existing CLI JSON Health(Status,Code,LastSuccessUtc) and exit code are the
implemented producer/checker surfaces. No Sentinel API or CloudWatch installation
is invented here. This table defines what the future alert wiring must preserve.

| Observed condition | Existing JSON status/code | Meaning for a consumer |
| --- | --- | --- |
| expected-UP=false | MAINTENANCE / NOT_EXPECTED_UP | Planned absence; do not erase failure evidence or fabricate heartbeat |
| Configured local latest attempt FAILED | FAILED / LAST_ATTEMPT_FAILED | Producer failure needs attention even while an older remote backup is recent |
| No committed remote manifest | MISSING / NO_REMOTE_COMMIT | Expected-UP backup missing; independent observation required |
| Latest verified remote start older than configured max age | STALE / REMOTE_BACKUP_TOO_OLD | Freshness limit exceeded; it does not measure production RPO |
| Verified recent remote commit | HEALTHY / RECENT_REMOTE_COMMIT | Backup freshness only, not proof of SQL/API readiness or absence of later unseen job failure |
| No remote storage checked and no local failure | UNKNOWN / REMOTE_STORAGE_NOT_CHECKED | Insufficient evidence; never convert to healthy |
| Denied/unreadable/malformed evidence | CLI failure/nonzero | Observer failure, not missing backup; retain typed sanitized failure |

The local-attempt file is visible only on its configured filesystem. An independent
observer using another staging path cannot see that producer failure and may
correctly find an older recent commit. The five tests explicitly preserve this
limit. A real producer failure signal plus an independent remote missing/stale
checker remain necessary; neither alarm delivery, periodic operation nor email is
implemented or accepted. No backup contents, rows, credentials or private keys
belong in those future events. Retain timestamps, stable subject identity and
UNKNOWN/maintenance distinctions without inventing an upstream event schema.

## Clean recovery cycle preparation

Artifact 65c7901 SHA256:
ece30607405bdaf65ea29d6396591bab7048b72b99e5d75f5cd8ea8c21846d6b.
Its 623 files remain untouched. It includes the actual private-parent and seven-
digit timestamp repairs, but not the subsequent backup-health change above.
That new compiled change is unit-tested only and needs a fresh pinned publish/
qualification before inclusion in a future artifact. No huge archive was rebuilt
or duplicated for this increment; do not label the old tar as the current HEAD.

1. Select one reviewed immutable artifact/source pair and a fresh owner-approved
   run/backend/lock/backup prefix. Preserve az5/az6 terminal states/evidence.
   Do not treat absent billing as remaining budget or reuse elapsed approvals.
2. Before first cost, bind normal runtime/security principals, actual effective
   create AND indirect-resource retirement capabilities, single writer, fences,
   exact security rollback inputs and a fresh full-root saved create plan. Same
   twenty logical resources do not by themselves certify new IDs/permissions.
3. Review that run's conservative aggregate budget/time/retirement reserve. This
   local checkpoint grants no new AWS calls, scope, spend, publication or access.
4. After an admitted create, observe both real SQL bootstrap/SSM readiness and
   verify all 623 artifact hashes/modes. Provision only private receipt directories;
   host.main must create its SQL staging itself. Do not pre-repair it manually.
5. Execute source once, require its successful receipt, quiesce that exact source,
   then restore the exact committed versions in the other AZ. The existing finite
   operator no-force-process guard remains required; no unconditional SIGKILL or
   unknown PID termination is authorized. Keep real event timestamps/markers and
   report the prepared-target RTO as such. If a failure requires a live repair,
   preserve its STARTED/failure receipt and report the repaired proof explicitly;
   do not call it unchanged-flow acceptance or blindly rerun uncertain effects.
6. Retire the owned NAT first, wait for native ENI/EIP release, review/apply the
   fresh full-root destroy, then verify volumes/ENIs/state/lock and reverse exact
   temporary grants. No denied DisassociateAddress replay, DeleteVolume fallback,
   state surgery, force cleanup or changes to EKS. Keep original 2+2 day retention.
7. Independent UP/DOWN observation, complete unchanged remote host workflow and
   owner-agreed general RPO/RTO remain open. Local tests do not check those boxes.

## PKI and Sentinel source availability

This bounded inspection covered task/projects, the preserved/migration project
roots, tracked ECS package/project references and the existing shared/qualification
NuGet caches. Only ECS and EKS checkouts/migration packages were found; no matching
ServiceIdentity.Pki package cache or PKI/Sentinel implementation checkout was
available in those reviewed roots. This is not a claim about every user disk.
The log's recovered original conversations restore requirements, not source files.
No private GitHub retry, source download, credential read or dependency install
was attempted. Historical KDD snapshots are evidence of earlier review, not
currently callable/consumable APIs.

| Required integration | Actual ECS connection points | Exact remaining gate |
| --- | --- | --- |
| Service Identity PKI/mTLS/rotation | Program.cs DI and IEncryptionService; a second real service/identity is needed for service-to-service mTLS, preserving SQL/KMS semantics | Obtain the real pinned upstream source or licensed packages and contracts; historical review names commit 29a3dfc and alpha 0.1.0-alpha.1. Confirm .NET 10 compatibility, remote authenticated enrollment/custody/revocation and AWS signer integration before implementation. Do not clone its CA/rotation framework, invent APIs or disguise LocalDevelopment as production |
| Reliability Sentinel alarms/logs/email | CLI health JSON, producer service exit/last-attempt, recovery receipts and existing native alarms/logs | Obtain real upstream source/contracts; historical review names commit 0e8fc55, nat-asg catalog and synthetic route only. Qualify us-east-1 host/region, real ECS/SQL/backup/PKI domains and notification/email implementation. Never label real events sentinel.synthetic or map them falsely to NAT; E13 remains the NAT remediator |

The [architecture review](v2-architecture-review.md#5-integración-service-identity-pki)
retains the earlier design/source boundaries. PKI needs real identity, invalid-
certificate rejection and continuous-load rotation/drain/recovery evidence.
Sentinel must classify existing HA coverage versus developer email, not general
auto-repair. With source unavailable, this increment makes no fake adapter, test
double public API or installed integration claim.

## Remaining Page scope

| Page phase | Current honest gate |
| --- | --- |
| 1 Architecture/pipelines | V2 availability and cost decisions plus actual pipeline changes still need their scoped disposition |
| 2 SQL recovery/alerts | Controlled az6 and local components accepted only in their stated scope; unchanged flow, independent UP/DOWN, general targets, real failure/missing/stale alert delivery remain open |
| 3 Security/PCI lessons | Inherited findings need concrete prioritized remediation; no compliance claim |
| 4 PKI | Required reusable upstream integration, two identities, AWS emission/rotation and rejection/failure tests remain open |
| 5 Sentinel | Required real alarms/logs classification and email/periodic-operation qualification remain open; no general repair authority |
| 6 Product Demo/Archify Explorer | Minimal UI and diagrams must distinguish live state from historical evidence; no new AWS admin console |
| 7 Repository/release | New repository preserving old, Kendall authorship for new commits, real CI/OIDC, README/screenshots remain required; no push/repository creation/identity change performed now |

The IAM auditor's prepare/apply/CI integration remains an open concrete task:
the manual structural auditor is not automatic prevention or effective AWS IAM
proof. This increment does not modify E16, its approved contracts or EKS.
