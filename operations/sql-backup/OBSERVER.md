# Backup observer - local implementation, uninstalled

Current placement for the next integrated proposal: [SQL host plus external watchdog](COHOST.md), selected by the owner on2026-10-25. The separate-host requirement below is preserved as the earlier design and superseded for that proposal. Independent periodic execution on SQL does not imply an independent failure domain. Historical qualifications remain unchanged.

`observer.py` supplies the missing finite observer around the existing read-only
`SqlBackup check`. It creates no backups, restores nothing and delivers no mail.
The producer timer remains separate. A future installation must run outside the
SQL host failure domain; this change installs nothing on the laptop or AWS.

## Local behavior

- `run` invokes one fresh `check --config ... --expected-up true --aws --ec2-role`
  each time, even if its last candidate was deduplicated. Existing CLI account,
  region, exact role, manifest verification and freshness rules remain authority.
  No SQL/profile credentials are acquired. Only process/runtime environment keys
  reach the child; inherited SQL/AWS credential values are not copied.
- Missing, stale, failed or unknown observations generate a local candidate on
  first observation or condition change. Repeated conditions are suppressed;
  an explicit positive reminder interval permits another candidate when due.
  Explicit zero disables reminder repeats. A newer healthy timestamp alone does
  not generate a notice. Healthy after an open incident generates RECOVERED once.
- Maintenance invokes no checker and generates no candidate; it preserves the
  prior incident instead of pretending recovery. Denied/malformed/failed checker
  results become UNKNOWN/REMOTE_STORAGE_NOT_CHECKED, never MISSING or HEALTHY.
- Optional `--producer-job-receipt` reads the existing sanitized host.py last-job
  format. A failed job later than the latest verified backup takes precedence,
  preserving its last-success timestamp. A newer verified backup supersedes that
  failure. ProducerFailureCoverage is NOT_PROVIDED or LOCAL_RECEIPT_ONLY. A local
  file is not an authenticated network channel; this wrapper cannot fetch it from
  a dead SQL host or prove absence of a later unseen producer failure.
- Output retains Status/Code/LastSuccessUtc, subject/time and Emit/Reason.
  Delivery=NONE, SentinelIntegrated=false, RemediationAllowed=false. Emit=true is
  a **local candidate**, never an assertion that an email or alarm was delivered.
  Replay is labelled LOCAL_RECEIPT_REPLAY; maintenance EXPECTED_UP_FALSE.
- Private state binds the exact config SHA256 and subject. Atomic replacement,
  single ownership, strict receipts and clock checks prevent cross-subject
  suppression. Interrupted lock/pending files require operator reconciliation;
  no PID kill, takeover or automatic state reset exists. State/last-notice time
  deduplicates generated candidates, not acknowledged delivery: stdout/state are
  not an exactly-once queue. Durable forwarding and acknowledgement are future
  integration acceptance, including crash/retry behavior.

Exit 0 means healthy/maintenance, 1 attention/unknown (even a suppressed repeat),
and 2 admission/state failure. Raw stderr, SDK/OS exceptions, configuration,
credential fields and SQL rows are never emitted.

## Inert periodic integration

The separate sql-backup-observer.service.in and .timer.in are proposals. They have
no SQL dependency/credentials and use a private StateDirectory. Health exit 1 is
an expected observation, preventing systemd failure/restart noise every tick.
The CLI native TimeoutSeconds remains unchanged; outer timeout is 660 seconds,
SIGTERM only and SendSIGKILL=no. A child that does not terminate needs operator
reconciliation, never force cleanup. Neither unit was installed or started.

Decide all placeholders before normal installation review:

| Parameter | Required decision |
| --- | --- |
| OBSERVER_ON_CALENDAR | Independent cadence/window, not the producer backup interval |
| REMINDER_SECONDS | Explicit reminder interval or 0; controls local candidates only |
| EXPECTED_UP | Authoritative UP/DOWN source and its future update mechanism; no automatic discovery exists |
| OBSERVER_USER/CONFIG/SUBJECT and BACKUP_EXECUTABLE | Separate failure domain, stable subject, metadata-only config and exact reviewed component |
| IAM and producer evidence | Approved read-only EC2 role for existing S3/KMS reads and authenticated producer-job/log ingestion; none installed |
| Delivery | Real Sentinel source/API, approved email destination, durable forwarding/acknowledgement and integration tests |

Replace every placeholder and validate rendered units before enabling anything.
Persistent=true catches up one check, not every missed interval. The observer's
staging directory must be independent of the SQL host's producer files. Package
and pin the new Python/unit sources with the selected existing component through
the normal artifact process before future publication. Old recovery archives and
component manifests remain immutable and do not contain these new observer files;
no large replacement archive was built.

The producer's one-hour backup interval, existing two-hour freshness threshold and
2+2-day retention remain unchanged. No RPO/RTO target or observer cadence is chosen.

## Offline validation and remaining acceptance

Tests use synthetic health/job receipts and a fake checker subprocess port, plus
actual isolated Python CLI replay and persistent-state runs. Native Linux covers
private permissions/symlink refusal. They do not run the AWS-enabled checker,
install systemd, establish host independence, run a real timer or prove delivery.

```text
python -I -B -m unittest discover -s operations/sql-backup -p test_observer.py -v
```

Replay requires absolute synthetic config/receipt/private-state paths, a captured
health exit code, explicit UTC timestamp, subject, expected-UP and reminders:

```text
python -I -B operations/sql-backup/observer.py replay --config <absolute-synthetic-config> --state-directory <absolute-private-state> --subject dev-sql-backups --expected-up true --repeat-after-seconds 0 --health-receipt <absolute-health-json> --health-exit-code 1 --observed-at 2026-10-23T18:00:00Z
```

Replay refuses AWS flags. Future run mode requires both --aws and --ec2-role;
real AWS execution remains unqualified by this local increment.


Current local qualification: native Linux **24 PASS** (15 observer cases plus nine
existing signal/component-binding regressions). Windows observer **14 PASS / one
POSIX-only skip**. The real Python replay entrypoint passed missing -> suppressed
repeat -> healthy recovery. Knowledge links/immutable E1 checks and diff checks
passed; hosted CI, real AWS checks and actual timer/notification operation did not
run. The pre-existing provider-lock and 30 source-inventory findings remain scoped.


## CI source integration

The repo-hygiene source now runs the exact observer and existing local signal/
component-binding suites before provider reproducibility and optional tool installs.
No dependencies, SQL server, AWS credentials, service installation or real cloud
checker are required. This closes the missing source-level CI coverage for this
local observer; hosted workflow execution remains unrun and full hygiene retains
its independent provider-lock/source-inventory blockers. Focused wiring tests keep
both explicit commands and conservative change selection in place.

## Real Sentinel consumer qualification — 2026-10-23

The [pinned consumer adapter](../integrations/README.md) now exercises the actual
Sentinel in-process ingress, reducer, receipts/audits and pending outbox with 34
checks. Suppressed observations bypass it; recovered candidates are recorded
without inventing NAT recovery. Upstream memory persistence is a test fake.
Backup-specific recovery policy, authenticated transport, durable delivery and
real email remain open; no timer/service is installed or artifact replaced.

## Local incident policy follow-up — 2026-10-23

The [real consumer policy](../integrations/README.md#backup-observer-incident-policy)
now qualifies opening/persistence/recovery/UNKNOWN and recurrence with 54 checks
through original Sentinel components. Escalation/resolution are pending outbox
intentions; no delivery, worker or durable database is claimed. A second genuine
healthy observation may confirm AUTO_RECOVERED; normal suppression stays.
Explicit test parameters change no installed cadence/freshness/retention.
AWS installation, backup-check worker routing and real email remain open.
