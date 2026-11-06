# Sentinel DEV: retention and controlled incidents

Owner scope: `bbd5c6fa0b425a35a2264033296a48396bb604f45316a62bf5e274c293eb19c8`,
approved on 2026-11-06. The new modeled ceiling is USD 20, separate from previous
work. Stop new experiments on November 9 at 02:30 UTC; closure is due at 04:00 UTC.
Approval is not retroactive and does not provide an AWS billing cap.

## Operational certification update — November 6, afternoon UTC

This update supplements the morning record below; it does not rewrite the
original experiments or turn their Unknown observations into network failures.

### Inbox evidence supplied by the owner

The owner reports that ChatGPT, through connected Gmail, read the full bodies
and verified IncidentId, DeliveryId and AuditId of these messages in **INBOX**:

| Domain event | Inbox reception UTC, November 6 | Revision |
| --- | --- | ---: |
| First NAT A recovery | 06:44:26 | 78 |
| Second NAT A recovery | 07:14:26 | 108 |
| Expired SQL backup escalation | 07:58:29 | 132 |
| SQL backup incident resolution | 08:30:27 | 141 |

The SQL messages share one IncidentId and match the original experiment.
This is **external ChatGPT/Gmail verification supplied by the owner**, not a new
AWS API or inbox inspection in this session. It closes the four inbox gaps in
the historical record below. Neither NAT message is a failure-detection notice.
The separate 06:47 CloudWatch health email remains infrastructure monitoring,
not a NAT domain notification. No old notice was resent for this verification.

### Detection correction and its boundary

The observer now retains independent `controlPlane` and `connectivity` verdicts.
Terminated/replacing members, EIP, route and SDC evidence remain visible if the
probe executor fails, but connectivity remains Unknown. A failed real HTTPS
request remains visible if an AWS read fails. A replacement event or an ASG
Healthy state alone never proves a failed or successful HTTPS request.

The fixed HTTPS operation runs in a child process without inherited credentials
or caller-selected destinations/commands. The parent enforces a six-second
deadline and kills/reaps the child; two seconds remain for termination and the
Lambda response. This covers native DNS/TCP/TLS work that could delay Python's
signal handler. Child startup/runtime failure remains Unknown, not network Fail.
The endpoint stays `https://checkip.amazonaws.com/`, redirects are rejected,
response bytes are bounded and success must match NAT A's EIP.
See [Python subprocess timeouts](https://docs.python.org/3.13/library/subprocess.html)
and [signal-handler execution](https://docs.python.org/3/library/signal.html).

The existing one-minute observer and two-minute incident evaluation are sampling
limits. An outage shorter than those intervals can be missed or resolved before
escalation dispatch. Auto Scaling events can provide supplemental timestamps,
but are [best-effort control-plane events](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-event-reference.html),
not proof of HTTPS loss. No extra event pipeline or lifecycle hook is installed
by this correction. A third disruptive experiment requires separate approval;
the original two authorizations are consumed. Local deadline tests and healthy
AWS probes do not establish outage-detection PASS.

Readable domain notices now identify NAT A, SQL backups or the actual monitor in
their heading; both escalation and resolution subjects retain the monitor ID.
The synthetic/laboratory label and immutable incident/delivery/audit fields remain.
No historical message is rewritten or resent. Source corrections initially
passed 64 Python tests and 88 CLR checks; five additional continuity-report tests
verify gaps, unhealthy cycles, duplicate rejection and non-extrapolated duration.
Installation and any later AWS trial must be recorded separately below.

### Current health versus retained debt

The expanded readback found one genuine **STALLED** cycle at 09:51:04.759:
`OldWorkRemainsDespiteOtherProgress`. The oldest pending archive dated
09:46:55.790; four archive executions completed at 09:51:27–31 and the next
watchdog sample was healthy. This was bounded backlog delay, not a missing
checkpoint, new permanent failure or permission denial. The four-minute age
threshold is retained; the incident is not erased to claim continuous health.

The next independently exported interval has **406 healthy watchdog samples**
from **09:52:05.519 to 16:37:04.930**, exactly **6h44m59.411s** between first/last
samples, with no gaps exceeding 90 seconds. There are 812 worker ticks:
427 Completed, 385 BudgetYield, maximum 58/64 requests, zero reported failed jobs.
This is sampled automatic progress, not 12 or 24 hours of demonstrated health.
The previous 07:37 start cannot be extended across the 09:51 incident.

The operations DLQ still has approximately 14 retained messages, no inflight
messages, 14-day retention, zero new sends and zero deletions since 07:37 in the
inspected metrics. Historical inspections account for receives. No receive,
redrive, purge or deletion was performed in this update. Its alarm remains
visible. Current health still verifies all four append-only compensations;
the original four permanent failures remain in the journal.

CloudWatch logs/metrics, DynamoDB checkpoints/audits and SSE-KMS archives already
collect evidence independently of this computer. The read-only exporter
`operations/integrations/portable/collect_continuity.py` can capture up to 26 hours
to a new private file. It fails on incomplete pagination/unexpected records,
separates missing visibility and unhealthy samples, and never extrapolates a
sample into future uptime. Reconcile deployment/manual-invocation intervals
separately. Repeat at 12/24 actual hours; do not keep an interactive session open
as a substitute for persistent evidence.

At 16:20 `/ready` returned 200; SQL, blue ECS and both NAT ASGs remained healthy.
All eight state serials in the morning inventory were unchanged, without locks.
Cost Explorer then reported account-wide **USD 2.3664246464 for November 5** and
**USD 0.617863946 for November 6**, both estimated/incomplete, not attributed trial
charges. The approved USD 14.60/20 model and November 9 closure boundary remain.
The small code deployment/readbacks fit the existing Lambda/logging allowance;
they do not authorize new infrastructure, an extended window or another fault.

### Installed correction and third, separately authorized trial

The owner subsequently approved exactly proposal
`320025463ed22d9089efaa5544a1318054639a335c34479a8cdf696aa7db49ce`:
one final NAT A termination, 15-minute maximum, and an independent local guardian
allowed to route private A through the existing B ENI after 12 minutes if needed.
The guardian depended on this PC remaining online; normal ASG/E13 recovery did
not. Neither ASG launch nor the recovery handlers were suspended or delayed.
SQL and the blue task were verified in private B before the fault; `/ready` was
200. The experiment was not an interruption of SQL or the application.

Source `75d04c703f0ba78f81e8a19ee82019a38b9656be` passed PR #34 Push/PR checks
before installation. Saved plan
`c2e650913ffb50b3180b7849cbfcb19a3e8399386fbff36331412d6c530a69a1`
applied ten in-place updates: four runtime packages and their four aliases,
the existing observer and the existing private probe. No creates, deletes,
replacements, IAM, monitor-policy or resource-identity changes occurred.
All four live aliases now use version **11**; runtime ZIP SHA256 is
`fe8dd47475ea09ff2093f6840925a99da168292d0f319919a1bc366fa8484ecb`.
Sentinel state is **44**, 88 managed resources, five data sources, no locks,
VersionId `dmTaUYbqJRUdJhiTi13La25QOURJaUMq`. Other roots were unchanged.
The first scheduled healthy probes verified the installed child-process path
before the disruption; no new IAM permission or probe concurrency was needed.

| Authentic event, November 6 UTC | Time | Meaning |
| --- | --- | --- |
| One TerminateInstances dispatch | 17:01:02.357 | Target `i-0f9b28ceebd2ed3ef`; authenticated response confirmed shutting-down |
| Scheduled HTTPS failure | 17:01:55.069 + 6.008s | `HttpsTotalDeadline`; response returned within Lambda's 10-second limit |
| Incident persisted | 17:02:01.473 | Revision 783, epoch 3, RESOLVED → RECOVERING |
| ASG replacement launch completed | 17:02:46 | `i-05f144bae3b8671f0`, LT A:4; this alone did not prove egress |
| First successful guardian HTTPS confirmed | 17:03:31.549 | Same EIP `98.85.209.220`; observed recovery bound **2m29.191s** after dispatch |
| First scheduled healthy probe | 17:03:54.915 + 1.486s | Control plane and HTTPS both Pass |
| Incident resolved | 17:03:56.771 | Revision 785, **2m54.414s** after dispatch |
| Guardian finished normally | 17:04:03.917 | Two successful probes/new Healthy member; **zero fallback writes** |
| Resolution SNS effect confirmed | 17:04:30.597 | One attempt; **33.826s** after durable resolution |
| Gmail INBOX reception | 17:04:30, second precision | Full body and correlated IDs read through the connected Gmail tool |

The scheduled failure was independently accompanied by a terminated member,
blackhole route and unassociated EIP. It persisted after approximately **59.115s**
from termination dispatch. The actual physical outage onset is bounded by samples;
it is not assumed to be identical to the EC2 API call. Post-recovery readback
verified ENI `eni-0d1127364cc1eabcc`, EIP association, active private A default route,
SDC=false and ASG desired=1/Healthy/InService. All three E13 :6 invocations appear
in their logs; their configured versions remain unchanged. B, SQL and `/ready`
remained healthy. There was no manual recovery or fourth fault.

One intermediate scheduled observation at **17:02:53.758** was **Unknown**:
the guardian's diagnostic invocation overlapped the one-concurrency probe,
producing `TooManyRequestsException`. Its control-plane failure evidence remained
visible. This is a real test-harness interference, preserved in the journal,
not a second proven HTTPS failure or a Lambda timeout. The preceding scheduled
probe proved failure and the following scheduled probe proved recovery.
Future read-only observation should consume scheduled results instead of racing
the same constrained probe. No concurrency/budget increase or extra disruption
was used to hide this limitation.

This short incident resolved before an escalation was generated. It produced
one recovery notice, not a fall-detection email. The persistent SQL-backup incident
already demonstrates escalation and resolution. The NAT result proves genuine
failure detection, persistence, automatic recovery and recovery notification;
it does **not** prove delivery of a NAT escalation before recovery.

Correlation retained in private evidence:

- Incident: `616d5db03503ac6914dc759d0637c6c3e815576fccc58f4db380c7297712009d`.
- Detection audit: `b9622c7358701de8445edcfcafe55e4319f9065d2f735584fa0ef23bc5219c54`;
  SSE-KMS VersionId `0ZfEAEfEzD3HcPii9W3KXFkkdaciWPgX`, confirmed 17:03:27.033.
- Resolution audit: `481d4f6831c84b83d716300978ea567d9b412f78cc66a03cdb597fb7bcbe483c`;
  SSE-KMS VersionId `ZPTeeG7AHwMQ_igBPb1.W3x2YtG6CRsW`, confirmed 17:04:31.113.
- Delivery: `c938923c47d3bade3c2a64b7eb8290b969ee691eac486e30b16082560beb87a5`;
  SNS message `5198ee4a-2270-5c9b-83ac-8d2228ae739c`.

Unlike the four historical inbox confirmations supplied externally by the owner,
this fifth domain message was verified directly in connected Gmail in this
session. Its subject names `nat-a-egress` and its heading says “Salida privada
NAT A”; the laboratory label remains. The metadata matched the complete body,
INBOX label and durable resolution. Personal addresses and unsubscribe links
were omitted from evidence exported to the repository. SNS totals at 17:07 were
**11 published, 11 delivered, zero failed**; these include historical CloudWatch
emails and must not be treated as eleven distinct domain incidents.

### Continuous operation: measured interval and remaining observation

The final pre-installation export extends the healthy interval to
**09:52:05.519–16:49:05.453 UTC: 6h56m59.934s**, 418 healthy watchdog samples,
836 worker ticks (440 Completed/396 BudgetYield), maximum **58/64** requests,
zero reported failed jobs and no visibility gaps over 90 seconds. The installation
and supervised third trial are separate interventions, not extra unattended hours.
At 17:07 the consistent checkpoint was revision **5124**, owner null, consecutive
failures zero, two recent due checks, no pending effects/archives and one buffered
reference. All four historical failures and their four verified compensations
remained intact; no new active permanent failure was reported.

The external observer has 32 successful storage receipts for the eight distinct
hourly backups from 09:00 through 16:00. Each verifies the exact S3 version, full
SHA256 and SSE-KMS; none is a new restore/CHECKDB claim. Historical DLQ debt remains
visible, with no purge, redrive or rewritten journal. Its alarm is not hidden by
the current worker-health assessment.

Automatic AWS logging continues after this session. Two read-only follow-ups on
November 7 at **06:00 and 18:00 UTC** are configured to export actual intervals and
separate gaps, failures and interventions. Desktop follow-ups require this PC and
Codex to be running; AWS evidence collection does not. These follow-ups authorize
no new fault, invocation, email, deployment, permission or window extension.
**12–24 hours of uninterrupted healthy operation remain pending elapsed-time
evidence**, not declared PASS in advance. Current functional NAT detection and
recovery pass with the explicit transient-observation limitation above.

The additional approved experiment allowance is at most USD 0.10: modeled total
**USD 14.70/20**, leaving USD 5.30 modeled contingency. Cost Explorer's latest
estimated account totals remain distinct from these allowances. The new NAT A
replaces the old one; there is no extra permanent instance. Closure remains
November 9, reserve 02:30 UTC and completion 04:00 UTC, with protected disks,
backups and Sentinel evidence retained unless separately authorized otherwise.

## Implementation and evidence boundary

This page records the installed implementation and its supervised AWS validation.
Local tests and actual incident evidence are distinguished below.
The existing SQL and API run in private subnet B. Experiments target NAT A only;
neither SQL data nor retained disks/backups may be destroyed.

The private Lambda probe makes one HTTPS request to `checkip.amazonaws.com` from
private subnet A. The existing regional observer reads the ASG, EC2, route and EIP
and correlates the probe response with its invocation ID. A healthy ASG alone is
insufficient. A failed observer is **Unknown**, not a proven network outage.
The probe has no ingress and only HTTPS egress. Its Lambda service ENI permissions
require Resource `*`; a `lambda:SourceFunctionArn` Deny prevents function code
from using those EC2 permissions. The observer and Sentinel stay outside the VPC.

NAT uses its own content-derived monitor catalog. The two installed SQL monitor
definitions and their catalog identity remain unchanged. Both groups use the
existing journal, worker and **64-request/four-job** operational profile. NAT's
condition assessment reports actual evidence; it does not infer application or
SQL availability. Recovery notices require the existing resolution semantics.

## Historical failures

Four permanent ArchiveDecision failures refer to original November 5 audits.
Their exact effect/audit byte hashes are pinned by `ArchiveCompensation`.
The explicit compensation mode reads these records, conditionally creates archive
objects with `If-None-Match: *`, verifies full bytes, SSE-KMS and real VersionIds, then appends separate
`AC#` receipts. Any ambiguous write stops. It never changes O#/T#/A#/OP# records,
resets attempts, queues old effects or sends SNS messages. A 412 leads only to
readback of existing bytes; any other write failure stops. This avoids requiring
ListBucket merely to distinguish a missing object's 403 response from absence.

The watchdog checks original hashes and append-only receipts. It reports raw
historical failures and verified compensations separately. Only verified archive
compensations are subtracted in its in-memory current-health view. New failures,
old stuck work, missing progress and missing heartbeat retain their original
failure semantics. No healthy journal is fabricated.

## Remote backup retention

The new prefix is `terragrunt-demo/dev/sql-backups/v2-20261106/` in the existing
SQL backup bucket. Historical prefixes and existing Lifecycle rules remain intact.
The bounded retention admission verifies exact manifest and backup versions,
full SHA256, length, SSE-KMS and the producer checksum receipt. The newest two
verified pairs are never tagged for expiry. A bad newest pair fails closed.

Only older verified pairs receive `ecs-retention=verified-superseded-v1` on both
exact versions. Native S3 Lifecycle expires eligible current versions after seven
days, their noncurrent versions after one additional day, and removes empty
delete markers. Incomplete multipart uploads in this new prefix are aborted after
one day. Invalid/uncommitted objects are quarantined, not automatically deleted.
Enrollment of previously untagged data older than six days requires review.

The manifest is tagged first. A partial tag operation may retain an extra backup;
it cannot make the protected newest two eligible. No application DeleteObject is
used. S3 expiration is asynchronous, based on object age rather than tag age, and
is not an atomic pair deletion. Neither an exact deletion time nor seven-day
maximum physical retention is guaranteed. If production stops, the last two
verified pairs remain indefinitely and continue to incur storage charges.

Before relying on an eligible object for restore, run `backup_restore_pin.py` to
copy and fully verify the exact pair into the excluded
`terragrunt-demo/dev/sql-backup-restore-holds/v2-20261106/<operation>/` prefix.
The original manifest is retained; the restore manifest binds genuine destination
VersionIds. Its receipt must exist **before fencing the source or provisioning a
replacement**. A failed pin does not authorize continuing recovery. AWS documents
that Lifecycle re-evaluates current tags before executing expiration, so removing
the triggering tag can prevent a queued expiration. It cannot restore a version
already deleted or by itself prove a stable restore input. This implementation
therefore requires the independent verified copy. Restore holds have no automatic
deletion and require a later explicit disposition.

References: [S3 expiration behavior](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html),
[Lifecycle rules and versions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html),
[Lambda VPC permissions](https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html).

## Controlled experiment limits

At most two A replacements, each with a 15-minute recovery limit; never disrupt B
simultaneously. The optional delayed-launch experiment requires a native timed
resume armed first. A producer-only backup failure lasts at most 150 minutes and
requires a native rollback timer before injection. Worker schedule pause is at
most three minutes, watchdog stays active, and restoration must be prearmed.
No fault begins without healthy SQL/API/B readbacks and baseline A egress evidence.

At most 20 notices go to the existing confirmed destination. Publication, SNS
delivery metrics and inbox confirmation are separate facts. Each experiment must
record fault, detection, journal, archive, publication and recovery timestamps,
including unsuccessful attempts. These are supervised DEV trials, not an SLA.

## Current health versus retained history

The four authenticated archive failures retain their original effect, attempt,
audit and operational records. Separate `AC#` receipts identify the exact
create-only SSE-KMS versions and verified bytes; the watchdog deducts only these
four dispositions in its in-memory health view. A fifth failure remains visible.

Continuous observation exposed two additional issues: a four-entry work page
could take several invocations, making its completed sweep stale; and the JSON
health value was not extracted by the installed metric filter from Lambda's
text-prefixed log events. The worker now queries at most 32 authoritative work
pointers and reads their current effects in one transaction, inside its unchanged
request budget, then checkpoints that observation normally. A continuation means
incomplete visibility, never healthy. The watchdog retains only its existing
GetItem permission. The metric uses an explicit bounded numeric log line;
the detailed structured health event is retained. Missing metrics still breach.

Worker dispatch admission distinguishes a source-evaluation job from a smaller
archive/effect dispatch. The hard 64-request/four-job profile remains unchanged.
Independent smaller work can progress in the
same invocation; uncertain results still use the original lease/idempotency rules.

Live continuous reports exposed redundant queued timer checks: their due slot had
already been evaluated by a newer durable monitor decision. Only a noncritical,
cancellable `ScheduleRecoveryCheck` in the same continuous monitor/epoch/policy
can now be superseded. The existing transactional cancellation still conditions
on the exact head revision and records the disposition. Equality/future slots,
notifications, archive work and non-monitor recovery are excluded. No old journal
rows are rewritten manually. Dispatch admission measures this shorter path within
the same 64-request/four-job bound; per-work request deltas are logged without
payloads. This is a code correction, not approval to discard pending notices.

The first real A replacement recovered its EIP, private route, SDC and private
HTTPS in approximately 2m40s. Detection remained partial: DescribeInstances for
the terminated member omitted network fields, causing two honest `Unknown`
observations. The observer now treats missing fields on that member as an
unrecovered configuration and still runs the private HTTPS probe. The owner
explicitly approved the second and final replacement without suspending ASG
Launch; B remains untouched.

The three monitors also exceeded the sustained throughput of one worker
admission per minute. A second target on the same rule admits two serialized
invocations per minute (120/hour within the existing 128/hour profile), retaining
concurrency one, 64 requests/four jobs per invocation, exact input, no transport
retries and the existing DLQ. One-time manual catch-up is recorded separately;
it is not evidence of unattended throughput. The trial preparer copies the
maintained consumer runtime so these reviewed settings survive re-preparation.

The second A replacement recovered private HTTPS at 07:11:55 UTC on November 6,
but detection remained partial for a different reason: socket timeouts applied
per connection/address allowed the private probe to reach Lambda's ten-second
timeout. The observer correctly reported Unknown. A six-second Linux process
timer now bounds DNS, all connection attempts, TLS and response reading together;
its exception is deliberately not an OSError, so urllib cannot retry an address
after expiry. The timer is removed and its handler restored on every exit. Local
tests interrupt an actual blocked socket without public network access. They do
not retroactively certify either AWS fault or authorize a third replacement.
That test does not prove every native resolver/library call is interruptible;
an eventual Lambda timeout remains Unknown rather than a fabricated NAT failure.
See [Python signal timers](https://docs.python.org/3/library/signal.html) and
[Lambda invocation timeout](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtime-environment.html).

A later readback proved one false current-health alarm: audit `9954cd82…` was
archived and confirmed at 07:16:29.854 UTC, but the 07:17 watchdog evaluated the
queue photographed just before that work. The worker now observes authoritative
pending rows after dispatch, immediately before its durable checkpoint. Ten of
the same 64 requests are reserved for the two observation reads and up to seven
CAS/readback requests; no invocation or job limit increases. An observation
failure records missing visibility and a failed completion, never an empty queue.
Tests cover that ordering, failure path and two CAS conflicts plus an ambiguous
write readback. Existing historical failures and all journal identities remain.

## Actual NAT trials, November 6 UTC

| Evidence | First replacement | Second replacement |
| --- | --- | --- |
| Termination response | 06:40:15.472 | 07:09:55.525 |
| Replacement | `i-08508c86ca29bfe29` | `i-0f9b28ceebd2ed3ef` |
| Private HTTPS restored | 06:42:54.899 | 07:11:55.114 |
| Observed restoration latency | 2m39.426s | 1m59.589s |
| Sentinel detection | Unknown: terminated member omitted network fields | Unknown: probe reached its Lambda timeout |
| Durable resolution | Revision 78, 06:42:55.651 | Revision 108, 07:11:55.846 |
| Resolution notice accepted by SNS | 06:44:26.576 | 07:14:26.404 |

Both replacements used LT A version 4. Readbacks verified ASG membership, EIP
`98.85.209.220`, the private default route and disabled source/destination
checking. HTTPS was executed from private subnet A and returned that EIP.
NAT B, SQL and the running blue task in B were not disrupted. The recovery path
passed; **the complete NAT incident-detection experiment remains PARTIAL**.
Neither Unknown result proves a failed HTTPS request, and neither later correction
retroactively changes those observations. Both authorized replacements are used.

The first incident's escalation was legitimately cancelled as obsolete before
dispatch (zero attempts); it was not replayed. Its resolution effect
`3d25b82095f3b9b1e7962706d231473d33fc458194067055036ef80e14b4b951`
was confirmed in one attempt. The second resolution effect
`9325dd89369776a6512d487929345545bb17b928fcc5128279f81cb1aa275bf0`
was also confirmed in one attempt. Original audits and exact-version SSE-KMS
archives remain in the private experiment record. SNS Standard may still
duplicate or reorder deliveries; an effect's single confirmed attempt is not an
exactly-once inbox guarantee.

The owner-confirmed 06:47 email was the **CloudWatch Sentinel-health ALARM**,
not the `nat-a-egress` domain notice. Domain-notice inbox receipt remains
unverified. The owner authorized read-only inspection of the open email tab,
but the browser automation kernel failed to initialize; no browser credentials,
cookies or private email links were extracted as a workaround.

## Retained failures and operational visibility

The four original permanent archive effects are distinct from the operations
DLQ. The former have four verified append-only archive compensations. The DLQ
also retains failed version-2 worker deliveries from November 5 and version-7
watchdog deliveries from November 6 (the temporary unauthorized Query path).
Those versions are no longer the live aliases. Queue readback is approximate
and may redeliver the same message: it is not a count of unique failed effects.
No message was purged, replayed or deleted to turn an alarm green. The
`operations-dead` alarm therefore remains visible even when current worker
checkpoints and watchdog health are healthy.

The current fixes preserve the original operational scope/profile identity,
64-request/four-job ceiling, retry limits and immutable audit history. Local
validation includes 61 portable Python checks and 83 CLR checks, including real
Linux socket deadline interruption and checkpoint failure/conflict paths. These
checks are separate from the live AWS observations.

## Actual backup-producer fault

Only the producer service received the temporary failing `ExecStartPre`; SQL,
credentials, previous backups and the application remained available. The fault
began at **05:51:15.719 UTC**. An independently armed persistent systemd timer
removed that exact drop-in at **08:20:15**, restarted the producer and wrote its
success receipt at **08:20:21.611**. Duration to verified recovery was
**149m05.893s**, within the 150-minute limit. This was native experiment rollback,
not a claim that Sentinel repairs the producer itself.

The last pre-fault backup started at 05:51:13.744. Sentinel detected its genuine
two-hour freshness breach at **07:51:30.415** (revision 131), approximately
16.7 seconds after that data deadline. It escalated at **07:57:29.930**
(revision 132); SNS accepted the escalation at **07:58:29.952**, in one attempt.
Detection-to-publication latency was **6m59.538s**, including evaluation cadence
and dispatch. This policy detects an expired backup, not the first failed host
service execution: fault-to-detection was about two hours.

The escalation audit is
`4fb86642b01e5771703a855fd02d4a78766e9a63543adbdf9a3c32fe76a077e6`;
its SSE-KMS archive version is `HXmQ5lqFgrmdqL7hJBhNzk.nKOWK3DTD`.
Both the archive effect and notification effect were confirmed with one attempt.
The archive receipt includes verified full bytes; an independent administrative
HEAD confirmed the version/key/metadata. Inbox confirmation remains separate.

Native recovery created run `8fcba7ab5aeb49e0a900c555e368214f`, 4,612,608 bytes,
with native checksum verification and SHA256
`9151bfb21f550f6d5de1f475cc51f5b806f74cebccc62d5408541981269e7631`.
Manifest version: `_UzstbpAGRMGi0SsxvceqfnCVBhpjl.J`; backup version:
`Fs_twTymJBN64Ycr8FrBB.H62TW3GakR`. The producer receipt reports
`REMOTE_VERIFIED_CLEANUP_VERIFIED`.

The scheduled external observer independently read that exact pair, verified its
full hash and SSE-KMS, and delivered the observation without a manual invocation.
Sentinel resolved epoch 2 at **08:28:28.817** (revision 141), **8m07.205s** after
the producer's recovery receipt. Its recovery notice was confirmed once at
**08:30:27.342**, **1m58.525s** after the durable resolution. The recovery audit
`ef893b832990ced7438d73bf5455de2341faf51d68cb3aefc4ef8e7263f6e2ab`
was archived and verified at 08:29:27.698; authentic SSE-KMS version:
`nemjAIUTdesAvJmOrp1VgNZ.9oVZbVwg`. This proves fault/staleness, detection,
escalation, native restoration, verified backup, durable resolution and SNS
acceptance. Domain-notice inbox receipt is still unverified.

At 08:28:31 the same scheduled observer admitted only the oldest new-prefix pair
for Lifecycle. Readback at 08:33 found both exact versions tagged, four objects
of the two newest verified pairs untagged, versioning enabled and no delete
markers. All 22 historical versions present at initial inventory remained;
the historical prefix contains 24 versions after two additional pre-cutover
writes. All three original Lifecycle rules were preserved. This is real automatic
eligibility/tagging evidence, **not** a claim that seven-day expiration ran.
The hourly producer remains enabled/persistent, with its next run at 09:00 UTC.

## Automatic observation window and verdict

`CONTINUITY-085155.private.json` covers **05:51:15–08:51:55 UTC**: 180.68 minutes
including the actual backup fault and restoration. It contains 329 worker reports
and 173 watchdog reports. This whole interval was not healthy or unattended:
early corrections, 33 successful manual catch-up invocations at 06:35–06:37,
20 Unknown and 47 Stalled watchdog results remain in the evidence. The latest
unhealthy result was at 07:36:06.881. No manual worker invocation followed 06:37.

After the final checkpoint correction, **07:37–08:51:55** contains 150 automatic
worker invocations (74 Completed, 76 BudgetYield), maximum **58/64** requests,
zero reported failed jobs and zero new active permanent failures. All 75 watchdog
reports were healthy (72 active, three idle); no Stalled/Unknown occurred in that
interval. BudgetYield is a bounded rescheduling outcome, not completed work or a
raised budget. Current pending work and its timestamps remain in each checkpoint.
The final watchdog saw a complete authoritative view of four recent pending
items, four historical failures, four verified compensations and zero active
permanent failures. This demonstrates continued progress, not an always-empty
queue or an unobserved multi-day availability guarantee.

The subsequent consistent DynamoDB read at **08:52:49** found checkpoint revision
**2160**, no lease owner, last completed/progress at 08:52:30.134 and zero
consecutive failures. Its complete backlog contained two recent due items and
one buffered work reference. The original `unresolvedFailures=4` field and four
separate compensation receipts were still present; progress did not reset them.

At 08:51, SNS metrics showed **10 publications, 10 deliveries and zero failures**
for the approved topic since the authorization began. These totals include
CloudWatch health alarms as well as domain notices and are not ten distinct
incidents or inbox confirmations. All Sentinel alarms were OK except the retained
operations DLQ alarm. No extra worker-pause experiment, SQL recovery or third NAT
fault was performed: the real producer failure and two NAT replacements already
exercised the selected scope.

**Result:** installed retention rules/admission, historical archive reconciliation,
automatic checkpoint progress, backup incident/resolution and AWS-side delivery
are demonstrated. NAT infrastructure recovery passed, while exact outage
detection and current domain-notice inbox receipt remain **PARTIAL/UNVERIFIED**.
The overall chaos qualification is therefore **PARTIAL**, with the functioning
platform and automatic monitoring preserved. No simulated result is promoted to
real outage evidence and no historic error is removed to obtain a passing label.

## Closing inventory and retained evidence

Read-only inventory at **08:25 UTC, November 6** found the API `/ready` returning
200, one running blue task (revision 15), green at zero, and both NAT ASGs with
one Healthy/InService member. SQL `i-010e3bf5edd05d11a` remains in private subnet B
at `10.0.101.160`. Current NAT A is `i-0f9b28ceebd2ed3ef`; B is
`i-00eeff5c609ca9f0f`. SQL, NAT, the internal ALB, API Gateway/VPC Link, two EIPs,
ECS, Sentinel/probe Lambdas, storage and observability resources remain installed.
There is no additional observer EC2 or permanently active recovery SQL instance.

| Root | Serial | Managed resources | Data sources | Persistent locks |
| --- | ---: | ---: | ---: | --- |
| security | 71 | 161 | 2 | None |
| shared | 3 | 5 | 0 | None |
| global | 37 | 49 | 1 | None |
| data | 17 | 5 | 0 | None |
| platform | 5 | 1 | 0 | None |
| apps | 12 | 9 | 1 | None |
| edge | 20 | 9 | 0 | None |
| sentinel | 41 | 88 | 5 | None |

The four Sentinel live aliases point to version 10; their installed package SHA256
is `cac4262c15561bca09022d39fa654292998fdc3778d69ca13675f1acb3c43c81`.
The probe's version-2 deadline correction is installed. The later source comment
clarification about Lifecycle does not change installed behavior. The final
Sentinel state VersionId is `Gw4szHkHPBETRNW3ZS54S1gigrcXGyLd`.
Worker/watchdog/cleanup and NAT observation remain scheduled; backup observation
is every 15 minutes. This readback does not establish availability after its time.

Private evidence resides in the approved `sentinel-chaos-retention-20261106-01`
session directory, including `FINAL-INVENTORY-082505.private.json`,
`BACKUP-AFTER-NATIVE-ROLLBACK.result.private.json`,
`BACKUP-FINAL-SCHEDULE.result.private.json`,
`BACKUP-OBSERVER-RECOVERY-083147.private.json`,
`RETENTION-READBACK-083305.private.json`,
`HISTORICAL-ARCHIVE-RECHECK-0755.private.json`, the timestamped continuity and
checkpoint readbacks, and both original NAT journal/probe records. The original
four audit/effect hashes still match; all four compensation receipts remain.
No secrets, inbox links or full journal payloads are published in this document.

## Cost and closure boundary

The approved 72-hour model is USD 14.60 against a USD 20 ceiling: SQL/two NAT
instances 2.852, blue Fargate 0.889, ALB/one-LCU allowance 2.196, two public IPv4
addresses 0.720, EBS/S3/ECR 1.200, KMS/secrets 1.000, CloudWatch 1.800,
Lambda/DynamoDB/EventBridge/SQS/SNS 1.800, and traffic/CPU-credit contingency
2.143. These are allowances, not attributed charges or service quotas.
Cost Explorer is delayed and labels recent daily totals as estimated; an empty
current-day total does not establish zero cost.

The 08:25 Cost Explorer read returned **USD 2.149914289 for November 5** and
**USD 0 for November 6**, both marked `Estimated=true`, account-wide. The latter
is incomplete billing data, not free operation; neither number is attributable
cost for this experiment. The model remains USD 14.60/20, leaving USD 5.40 of
modeled contingency. Ten SNS publications/deliveries had been observed after the
backup recovery; the 20-notice experiment allowance is an operational limit, not
a new service-side quota. No further faults or manual notice retries are planned.

The active SQL host, two NAT ASGs and blue Fargate service continue to cost money.
The existing native closure procedure must be reviewed against current states;
pre-recovery Data destroy plans and pre-installation infrastructure plans are
obsolete. Closure reserve starts **2026-11-09 02:30 UTC**, with execution complete
by **04:00 UTC**. Runtime grants expire at 04:00; the narrowly scoped retirement
delta lasts until 06:00. Expiring permissions do not stop EC2, ASGs or Fargate.
There is no automatic infrastructure teardown or AWS billing cap.

Closure must quiesce application writes, verify/preserve the final backup and
retained encrypted disks, stop the deployment-owned ECS workload, and use the
native owners to retire chargeable compute/networking. Sentinel journal/archive
and protected backup disposition remain separate from compute retirement.
The two previously retained 30-GiB disks alone model approximately USD 4.80/month
after closure until their disposition is expressly authorized. An additionally
retained current SQL root disk also continues to incur storage charges.
