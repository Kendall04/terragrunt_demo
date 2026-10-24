# V2 local completion checkpoint - 2026-10-23

> Actualización de diseño del 24 de octubre: [arquitectura y pipelines V2](v2-architecture-pipelines-20261024.md). Recomendaciones locales con evidencia az6/b1/b2; no cambia la historia ni autoriza operaciones.

This is a bounded local implementation/evidence checkpoint, not deployment or
permission to reset the original aggregate USD 2. The owner asks to advance both
projects from their respective Pages. The [ECS Page](https://chatgpt.com/space/page_6ad2223a7ed88191be14aba8886d669d)
and [log](https://chatgpt.com/space/page_1b0bc56020908191a7d18292c70468c6)
were read successfully. Their seven phases and user-added criteria remain open
where evidence is missing; the Page itself was not edited by this worker.

## Consolidated acceptance summary

These are scoped completed increments; ECS and the Page's seven phases remain
partially complete. Historical AWS evidence is not a fresh live inventory.

| Deliverable | Measured evidence | Acceptance boundary |
| --- | --- | --- |
| Controlled cross-AZ SQL/API experiment | az6 backup, quiesce, restore, CHECKDB, decryption and read/write passed with live repairs; prepared-target RTO **142.630783 s** | Does not prove an unchanged artifact/host lifecycle, cold AZ replacement, full ECS availability or general RPO/RTO |
| Runtime retirement and temporary access reversal | Native resources absent at **04:48:29.371929Z**, security reversal at **04:48:54.620428Z**, closure **04:49:25.460974Z** on 2026-10-23 | Recorded az6 closure; no new AWS cycle or budget reset. Conditional reboot policy was never installed and no reboot occurred |
| Corrected backup component and release binding | Source b2bf8d8 local Linux publication; CLI unit suite **62 PASS / 1 native SQL integration skip**; actual local CLI receipt replays cover FAILED/MISSING/STALE; old recovery tar rejected by payload guard | Captured stale metadata is historical; failure/missing inputs are synthetic. No live scheduler, Sentinel transport, alarm or confirmed email |
| Product Demo and custom explorer | **14** isolated Chrome checks; **10** portable Node tests; **35** CI-selection tests and **2** focused wiring checks; loopback-only, synthetic/historical status | Browser proof is bounded; Node source guards do not certify accessibility. Explorer is hand-authored, five Archify diagrams now generated in the later increment |
| Reproducibility investigation | Five DEV/PROD differences are one native Windows h1; all **15** published release zh values verified and installed cache h1 reproduced. Existing lock tests **1 PASS / 1 FAIL** | Original authenticated receipt/verified archive missing in inspected evidence; canonical package review required. Full prior reproducibility suite **26 PASS / 1 FAIL**, not green CI |

Artifact lineage remains explicit: immutable 65c7901 recovery tar SHA256
`ece30607405bdaf65ea29d6396591bab7048b72b99e5d75f5cd8ea8c21846d6b`
contains 623 files and the staging/timestamp repairs. The later b2bf8d8 backup
component manifest SHA256 is
`b0a98b236d25fa2d0bcc72269ac42e294276c53603f48945bc99ecfb3664c978`.
They are distinct inputs; no combined new recovery tar or new AWS execution is
claimed. az6 closure SHA256 is
`988d7917f9e2bf92129a7cd9ca3aad91b4b01b6591ea42aeb9019b224e5ffdbb`;
its separate integrity addendum preserves the disclosed mutable checkpoint issue.

The concrete blockers are:

- **Integration:** real pinned PKI and Sentinel sources are now available after
  owner-completed GCM login. The local Sentinel ingress increment below is
  qualified; mTLS rotation/rejection, backup-domain policy and real alarms/logs/email
  delivery remain open. IAM auditor prepare/apply/CI integration,
  V2 availability/cost choices and inherited security findings remain open.
- **AWS acceptance:** a clean unchanged systemd/remote backup/restore/API cycle,
  independent UP/DOWN and real alert delivery remain unqualified. A next cycle
  needs concrete artifact/plan, create-and-retire access and budget review;
  the original aggregate USD 2 is not renewed by local progress.
- **CI/release:** the lock equality failure and 30 existing source-inventory
  findings remain; no hosted workflow/actionlint result is claimed. New repository,
  actual CI/OIDC release and remaining Page delivery are pending.

The [lock provenance review](e14b-toolchain-reproducibility.md#native-lock-provenance-follow-up---2026-10-23)
and [portfolio checklist](../../portfolio/ACCEPTANCE.md) identify the narrow next
gates. The bounded migration search found no matching provider ZIP/receipt among
815 source ZIP members or nine selected evidence entries. All eight existing
protected lifecycle package identities still reproduce; their generator's lock
input remains historical. Dependent normalization is stopped pending the exact
missing evidence and canonical package review; no operation was denied or left
with an uncertain outcome. Do not repeat broad searches or silently weaken tests.

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
The subsequent b2bf8d8 component now has a pinned local Linux publication and
captured-receipt signal qualification; see the current local release checkpoint
in the backup README. It still needs inclusion in an inspected future artifact
and live acceptance, and must not be attributed to the old65c7901 tar. No huge archive was rebuilt
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
| 4 PKI | OUTSIDE ECS SCOPE by owner decision 2026-10-23 19:07:56 UTC; historical experiment preserved, not accepted or a completion gate |
| 5 Sentinel | Required real alarms/logs classification and email/periodic-operation qualification remain open; no general repair authority |
| 6 Product Demo/Archify Explorer | Local Product Demo, five authentic Archify views and a separate custom inspector: 15 Chrome checks and 14 Node tests; historical/local/future scopes explicit. Release/live scope remains pending. See portfolio/ACCEPTANCE.md |
| 7 Repository/release | New repository preserving old, Kendall authorship for new commits, real CI/OIDC, README/screenshots remain required; no push/repository creation/identity change performed now |

The IAM auditor's prepare/apply/CI integration remains an open concrete task:
the manual structural auditor is not automatic prevention or effective AWS IAM
proof. This increment does not modify E16, its approved contracts or EKS.


## Authentic Archify portfolio increment - 2026-10-23

[Five generated diagrams](../../docs/interactive/README.md) now complement the
hand-authored inspector: V1 application, V1 networking, historical az6, local backup
signals and future integrations. Official Archify 3.1.0 from pinned upstream
1c2b42d passed all four finalizer gates for every original. Integrated Chrome
qualification passed 15 checks (all five maps on desktop/mobile, visible SVG nodes,
zoom/reset, keyboard focus, opaque iframe, zero external requests/errors); Node
contracts passed 14. Browser/server closed normally. Representative captures were
visually inspected; mobile text uses zoom. The [acceptance checkpoint](../../portfolio/ACCEPTANCE.md)
links source/HTML hashes and screenshots. This replaces the earlier custom-only
Archify gap, without accepting PKI/Sentinel, unchanged cloud recovery, hosted CI or
release. No EKS resources/processes, AWS, pushes or workflows changed.


## Independent backup observer — local implementation 2026-10-23

The [observer](../../operations/sql-backup/OBSERVER.md) performs a finite fresh
existing check independently of backup creation, validates health/job receipts and
persists change/reminder/recovery deduplication. Inert service/timer templates leave
cadence, reminders and expected-UP explicit; producer interval, freshness and 2+2
day retention are unchanged. This closes the missing local implementation only.
Deployment outside the SQL failure domain, real role/config, producer ingestion,
periodic operation and durable Sentinel/email delivery remain unqualified. Emit
means a local candidate; it is not a delivery ACK. No AWS or service installation;
original archives, component manifests and Archify captures are intact.


## Upstream access and observer CI checkpoint — 2026-10-23

A single bounded laptop check found no PKI/Sentinel checkout in known project,
migration or worker integration locations. Git Credential Manager lists existing
account Kendall04; gh is not installed. One noninteractive ls-remote per exact repo
failed: service-identity-pki authentication/access failure, reliability-sentinel no
available noninteractive credential. No login, token read/copy, new access setup,
other-principal retry, private connector retry or source clone occurred. This does
not prove that either repository is absent.

Both sources remain required. Minimum unblock: renew the existing Kendall04 Git
session and allow read access to those two repos, or provide their versioned source
bundles locally; never send credentials. No repeated access search is planned.
First bounded integration after source availability: inspect the pinned Sentinel
actual input types, map existing observer FAILED/MISSING/STALE/RECOVERED candidates
with UNKNOWN/dedup semantics and test its real local ingress without sending email.
Then inspect the actual PKI .NET compatibility/DI/enrollment and two-identity mTLS
contracts; preserve existing KMS encryption and SQL semantics. No APIs are invented
while upstream types remain unseen.

Independently, repo-hygiene source now invokes the existing observer and signal/
component-binding tests before known provider reproducibility/tool-install steps.
This closes their missing source-level automatic coverage, without running a remote
workflow, changing E11 gate selection, installing anything or accepting full CI.

## Actual Sentinel ingress qualification — 2026-10-23

Source access is resolved: Sentinel 0e8fc55333ddde3b9816885915310a7e69f3de45 and
PKI 29a3dfc70a0b1646388c0229212898b4be164afe were read/cloned through the renewed
existing Kendall04 session. Earlier unavailability sections are historical.
Origins and pins are recorded in [upstream-sources.json](../../operations/integrations/upstream-sources.json).

The [consumer adapter](../../operations/integrations/README.md) connects real observer
candidates to ISourceNormalizer and actual Sentinel ingress/reducer/receipt/audit/
outbox components. 34 focused checks pass; build has zero warnings/errors, with
no package download or cloud call. The upstream memory store is explicitly fake.
A recovered candidate is audited, not falsely treated as NAT recovery/resolution.
A backup-specific evaluation policy, authenticated transport, persistent delivery,
region qualification and a real notification provider remain unimplemented. No
AWS, email, timer, upstream source change, archive rebuild or remote workflow.

## Owner scope clarification and useful local policy — 2026-10-23

ECS has **one application**: blue/green release slots of the same .NET API.
[Current topology](architecture.md#current-contract--topology-and-networking) and
Program.cs show API-to-SQL via EF/SQLClient and AWS KMS SDK; no business HTTP
service-to-service peer exists. Backup CLI/observer/library do not create one.
PKI runtime is paused pending a genuine need/scope decision; the requirement is
not silently cancelled and no microservice is invented. Unique experimental
code/material and failed receipts remain in the [unaccepted compatibility
experiment](../../operations/integrations/PKI-EXPERIMENT.md); existing API/IaC unchanged.

The [backup policy](../../operations/integrations/README.md#backup-observer-incident-policy)
replaces the earlier unqualified guard using actual IRecoveryEvaluator.
**54 checks** pass through original ingress/reducer/receipts/audit/pending outbox:
open/persistent/recovered episodes, UNKNOWN, reminders, deduplication across
reconstruction/recurrence and refusal of old/tied/expired positives.
Observation parameters are explicit fixtures, not installed contracts. No NAT
repair/evaluator; legacy shape has unused compatibility values and backup-scoped
read-probe intents, never executed. Upstream source remains intact.

This supersedes the earlier 34-check guard's inability to assess observer recovery,
not AWS/delivery gates: independent host/role/config/cadence, authenticated input,
backup worker mapping, durable storage/ACK, actual alarm/log ingestion, region
support and real email. No cloud spend/IAM/timer/workflow/push/archive rebuild.
Native SQL/API recovery acceptance remains unchanged.

## Superseding owner decision — 2026-10-23 19:07:56 UTC

PKI is **outside ECS scope**, not pending integration or completion. Earlier
sections preserve history and are superseded on that requirement. One API and
blue/green release slots remain; no business HTTP microservice is added. The
unaccepted PKI experiment stays preserved and outside the public demo route.
See the [owner decision](decisions-and-limitations.md#owner-scope-revision--ecs-portfolio-2026-10-23).

The bounded no-NAT regression now passes 58 Sentinel checks. Altered legacy
NAT bindings are rejected before any transaction/outbox enqueue; an actual
NAT-only catalog rejects backup work before its provider (zero calls). No
operational dispatcher is configured. The isolated rejection test is not an
installed dispatcher, notification transport or durable-persistence qualification.

## Historical deployment evidence for the portfolio

The [qualified DEV delivery record](deployment.md#protected-delivery-rollback-and-automatic-cleanup)
records A-to-B-to-A using two different application image digests (lines 774–812).
Both images passed readiness and SQL/KMS POST/GET; after rollback A read and
decrypted text written by B. Promotion/rollback and automatic cleanup have native
protected success receipts. This is historical unchanged-schema application/key/
database compatibility, **not rollback of migrations or database backup/restore**,
and not a claim of currently live infrastructure. The portfolio's guided tour
keeps memory-only DEMO, V1 architecture, deployment history, prepared-target az6
with two repairs, local observability and real pending installation distinct.

## Bounded regression closure — 2026-10-23

Observer 15 and signals/release binding 9 Linux tests pass; Sentinel 58, Node 16,
CI source-wiring 4 and isolated Chrome 16 pass. Poisoned legacy NAT bindings are
refused before state/audit/outbox persistence. A real NAT catalog/worker negative
case rejects backup work before its provider; no operational dispatcher is wired.

The fifth authentic Archify map now represents local backup/Sentinel and pending
installation. PKI/second-service proposal is preserved privately in Git history,
not the current tour. UI adds only guided presentation and qualified historical
A→B→A evidence, no API features. The [small source/recipe manifest](../../operations/integrations/local-regression-manifest.json)
includes no large binaries. These are local acceptance scopes, not durable
storage, real email, live AWS observation or hosted CI. Deployment/unchanged
recovery require their admitted plan, IAM create+retire and budget; original USD2
is not renewed. No cloud, timer install, remote workflow, push or EKS change.

## Observer b2 outcome — 2026-10-24

[Native b2 postmortem](../../operations/integrations/NATIVE-TRIAL-2026-10-24.md):43
resources created/retired,28 native absence checks and all temporary access reverted.
AL2023 bundle bootstrap and durable empty Lambda cursor passed. SSM pre-execution
authorization failed twice;0 events/0 notices. Offline receipt regressions do not
qualify the periodic observer. Original b1 synthetic inbox proof stays valid and
separate; no complete ECS acceptance or new AWS authority follows.

## Local cold-path preparer — 2026-10-24

See the [executable offline commands, fencing limit and next-trial gates](../../operations/sql-backup/recovery/RUNBOOK.md#cold-recovery-preparation--local-increment-2026-10-24). SAME_AZ/CROSS_AZ preparation now derives one fresh target and 15 resources from the az6 generator. Metadata review refuses uncertain fencing and prepared-target timing; it never authorizes activation or authenticates AWS evidence. Seven new hermetic tests and 30 existing recovery tests passed. Live host adaptation, native source fencing, full ECS cutover, exact IAM/retirement and a new costed approval packet remain open. The owner's LIVE review window is part of that future packet; no new cycle was started.

## Cold restore write barrier and single-target retirement

The subsequent local implementation adds native-read adapters (not executed against AWS), restore checks before write enable and one-target retirement binding. See [trial scope/cost and admission blockers](../../operations/sql-backup/recovery/COLD-TRIAL-PROPOSAL.md) and [small source manifest](../../operations/sql-backup/recovery/cold-local-manifest.json). Local tests3+7+30 PASS, POSIX entrypoints4 SKIP on Windows. Proposed30 creations/USD4 is isolated SQL/loopback API recovery, not an approved cycle or full deployed ECS cutover. Shared-instance-role DescribeInstances scope, b2 execution transport, native source generation/fencing, actual plan and viewing access remain to qualify. No AWS trial was started.

## Explicit cold recovery CI

Local workflow diff now invokes `scripts/tests/run_recovery_ci.py` from repo hygiene. Existing WSL unprivileged execution:71 PASS/0SKIP, including four POSIX tests; CI selector/runner contracts38 PASS with empty/skip/failure rejection. [Evidence](../../operations/sql-backup/recovery/cold-ci-qualification.json) contains actual discovered test IDs and hashes. No remote CI, push, install, SQL/AWS execution or root requirement change. Full hosted CI and inherited gates remain separately unverified. Support console required login; stopped without login, plan remains unknown.
