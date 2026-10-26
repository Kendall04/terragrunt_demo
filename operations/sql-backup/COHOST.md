# SQL-host backup observation with external telemetry watchdog

Current actual TARGET/bootstrap and exact IAM proposal: [wiring review](recovery/COHOST-WIRING-REVIEW.md). Initial boot stages only; post-restore native handoff and external readiness gate activation.

Owner selected this placement on 2026-10-25 (local preparation only). This supersedes
OBSERVER.md's original requirement for a separate observer host for the next integrated
proposal. No service, role, credential, infrastructure or budget is installed/approved here.

The existing SQL EC2 runs `host.py` for hourly backups and `observer.py` through
`sentinel_publish.py` for independent periodic *execution*, sharing SQL's failure domain.
The finite cohost unit caps all SQS send attempts at20 across restarts, with a durable
config/queue-bound budget and <=3 attempts per pending observation. A crash or unknown
transport outcome consumes a slot; exhaustion retains pending data and becomes externally
UNKNOWN, never silent deletion or authority to restart the budget. A20-slot limit also
means this cannot run indefinitely: choose the cadence/window in the next admitted cycle.
Each tick executes a fresh `SqlBackup check`, reads the same host's sanitized producer
receipt, and durably spools the observation before sending to the existing SQS ingress.
Even a suppressed HEALTHY candidate is sent as telemetry; maintenance sends nothing.
No separate EC2 observer, role/profile, public observer network or SSM document is needed.
The historical optional `modules/observer` stays off and is preserved for provenance.

Sentinel's original ingress/store/outbox, readable SNS notices and scheduled watchdog
remain outside SQL. A committed heartbeat reports arrival of an authenticated observation,
not SQL availability, a newly successful backup, .bak integrity or recoverability.
Missing heartbeat produces **UNKNOWN/OBSERVER_HEARTBEAT_EXPIRED**, never MISSING backup
or automatic recovery. Unknown health after the host returns restores telemetry but does
not heal the incident; a fresh later verified healthy observation is required. Replayed
old health cannot refresh the monotonic heartbeat or resolve the episode. No NAT worker
is connected. Unsupported probes remain visible; this does not promise an empty outbox.
This design does **not** independently inspect S3 while SQL is down and does not monitor
failure of Sentinel itself. Those are deliberately narrower guarantees than a separate
observer. The d1/b2 RunCommand AccessDenied remains unresolved, with no alternate SSH,
principal or document authorized. Autonomous boot is a future declarative installation,
not a retry of those rejected commands. Recovery orchestration's SSM gate stays separate.

## Existing package, explicit opt-in

`package.py build --with-observer` adds the current observer/publisher/signals/cohost
sources and existing unit templates to the same deterministic hash-inventoried SQL
package. A normal build/install keeps its backup-only behavior. No old tar, component
manifest, protected pin, approval or native receipt is rewritten. Current binary inputs
must be freshly qualified when packaging for a real cycle; fixture executables are not
native SQL acceptance. No large binary archive was assembled for this local increment.

`package.py install --sentinel-config <absolute-json>` validates all metadata before
writing. The regular backup config supplies the **existing SQL role**, staging and
S3/KMS bindings. The optional config accepts exactly these fields (example is synthetic,
expired and not an installable authorization):

```json
{"SchemaVersion":1,"Placement":"SQL_HOST","Account":"341936017254","Region":"us-east-1","RunId":"ecs-sentinel-example","Subject":"dev-sql-backups","StartsAt":"2026-10-26T00:00:00Z","ExpiresAt":"2026-10-27T00:00:00Z","CadenceSeconds":300,"ReminderSeconds":0,"PublishAttempts":3,"WatchdogSeconds":1200,"ExpectedUp":true}
```

No credentials, recipient or arbitrary command/endpoint are accepted here. The current
finite-sandbox contracts still require <=24h. Cadence/reminder/watchdog/expected-UP are
explicit inputs, not changes to installed policy or retention. The 300s/1200s example
is a recommendation for a trial, not an approved operational SLA. Watchdog must exceed
cadence +840s (660s check bound, 120s transport allowance, 60s jitter). Longer throttling,
a stuck process or queue delay can still produce UNKNOWN; never relabel it SQL failure.
Hourly backup, proposed2h freshness and2+2-day retention are unchanged.

The installer returns `ExternalWatchdogBinding`, a partial mapping of existing Terraform
`config` keys: mode, run/subject, SQL sender ARN, times, watchdog deadline and expected-UP.
Merge it into the reviewed Sentinel inputs, with `enable_observer=false`, external dispatch
schedule enabled and ingress enabled only after native subscription/preconditions pass.
Compare runtime readback against the mapping at admission. The partial mapping creates no
Terraform backend, role, subscription, watchdog or authority by itself. Existing input
requirements (recipient, archive, retention, artifact hashes, principal) remain mandatory.

## Declarative start and ownership

Installation stages root-owned files/config, a `sql-backup-cohost.target`, the existing
hourly backup timer, a separate observation timer and a producer integrity drop-in. It
never runs systemctl. Idempotent reinstallation verifies identical config/package/files;
drift, foreign paths, symlinks or changed inputs require explicit replacement review.
The observer runs under the existing SQL service user to read its private last-job receipt;
it receives no LoadCredential or SQL connection environment. Its state directory remains
separate from SQL staging. Existing ephemeral credential provisioning for the backup
service is unchanged; none is created by this extension.

A future reviewed SQL bootstrap stages the hash-verified package/config through the
normal artifact path, checks required runtime/CLI and the two existing ephemeral backup
credential files, verifies `ExternalWatchdogBinding` against the external deployment,
and then executes these fixed actions under its already approved host authority:

```text
python3 -I -B /opt/terragrunt-demo/sql-backup/cohost.py verify
systemctl daemon-reload
systemctl enable --now sql-backup-cohost.target
```

These actions were **not executed**. Each service has the same startup integrity/expiry
gate, so restart/reboot cannot silently use changed files. The gate verifies the installed
receipt (<=1MiB), exact files/hashes/modes/root ownership, config and finite window. This
is local integrity under root trust, not attestation against compromised root. The target
starts both timers; observation has OnBootSec90/OnUnitActiveSec with no SQL dependency,
so unavailable SQL does not inhibit metadata checking. Target/timer active is not health.
No repeated boot downloads, service restarts, force-kill or ownership takeover is added.
Enabling through user data still requires a reviewed bootstrap diff and fresh artifact;
this local change does not edit the protected data user_data or claim it is installed.

Shutdown remains owner-controlled: inhibit the backup with existing lifecycle tooling,
wait for known idle/outcome, disable the two own timers and cohost target, reconcile any
active job/pending delivery, export bounded sanitized evidence, then retire only the own
host/run. Do not remove pending files, steal locks or kill a PID. Expected-DOWN must be
explicitly reviewed in the external watcher before planned teardown; silence alone does
not prove safe shutdown. Expiry blocks new jobs; it does not cancel an already running
remote backup or automatically delete resources. Preserve original backups/states.

## Acceptance and proposed footprint

The existing integrated proposal already forecasts **102** managed addresses including
29 Sentinel addresses and no separate observer. This change adds **zero cloud addresses**
to that forecast, not a subtraction from102. The earlier standalone43-address b2 inventory
is historical and is not the integrated graph. Removing its optional observer module avoids
its14-address host/network/profile branch (plus implicit volume/ENI), its dedicated hourly
EC2/IPv4/disk charges and SSM trial controls. It does not eliminate the active SQL host,
Sentinel calls/storage or the platform's existing network costs. No new numerical quote,
spend authority or reset of old budgets is implied; the previous USD6 remains unapproved
and must be refreshed from actual saved plans/prices and current resources before admission.

Future access delta: exact `sqs:SendMessage` on the run's ingestion queue for the existing
SQL role, plus its entry in the queue policy; retain reviewed existing backup S3/KMS access
and exact package version read if needed. Do not grant the observer SQL secrets just to
check metadata. The shared EC2 role means SQL-host processes can use that queue grant;
Unix users do not partition IAM. Sentinel roles retain their own table/archive/log/SNS
scopes, with no SQL/EC2/SSM/NAT/secret/KMS access. No IAM statement was installed or widened.
Exact principals/ARNs/expiry and teardown reversal still belong to the next cycle packet.

Local tests cover real fixture staging/idempotence/tamper/expiry, rendered timers, actual
observer/publisher state logic with checker/SQS doubles, and real original Sentinel
watchdog/store/outbox/notice logic with SDK doubles. They do not run systemd timers,
SQL backup, S3 reads, native scheduling, notifications or AWS permissions. Native acceptance
must show boot without manual repair, one fresh backup receipt and metadata check, external
persistence/ACK and notices, loss of host telemetry -> UNKNOWN, return UNKNOWN -> still open,
fresh healthy recovery, bounded owner LIVE review (proposed30min) and full retirement.
Observe this from preserved native receipts, not a JSON fixture labelled CHECK_COMMAND_RESULT.
The cold restore, fencing, private listener and public Fargate API chain remain distinct gates.

Run focused Linux fixture checks with the existing Python (no package downloads):

```text
python3 -I -B -m unittest discover -s operations/sql-backup -p test_cohost.py -v
python3 -I -B -m unittest discover -s operations/sql-backup -p test_host.py -v
python3 -I -B -m unittest discover -s operations/sql-backup -p test_observer.py -v
python3 -I -B -m unittest discover -s operations/sql-backup -p test_sentinel_publish.py -v
```

The managed regression uses the existing pinned Sentinel source/SDK cache and its original
SDK doubles. The source workflow was not edited or executed remotely for this increment.
