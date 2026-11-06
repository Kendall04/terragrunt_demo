# Native DEV cold recovery

This procedure uses the existing Data Terraform owner and portable SQL backup
package. It does not introduce a second recovery controller. The host steps are
implemented and tested; **cold SAME-AZ/CROSS-AZ AWS execution is still pending
the owner's interruption/cost approval**. Local tests are not an RTO result.

## Preconditions and evidence

Keep one active SQL writer. Select the actual public/private AZ mappings from
Global outputs and AWS; never infer an address from an earlier receipt. Use the
approved SQL AMI, existing instance profile/SG and `validated-v2` TLS. The Data
input `recovery_preserve_root_volume=true` must already be reflected in AWS.
Record the current EC2 ID/launch time, encrypted root volume ID, state
serial/VersionId/ETag, active ECS revision, connection-secret VersionId and E2
status. Request explicit permission for interruption and replacement, including
cost of retained volumes. A dry run or plan does not supply that permission.

Private request fields for `native_step.py` are `trial`, `instanceId`,
`sourceInstanceId`, `sourceLaunchTime`, `targetAz`, `expiresAt`, `sourceFence`,
`backupReceipt`, `expectedRows`, `expectedDataHash`. For an initial **inspect**,
the last four fields may be null. Persist the authentic inspect result before
populating the row count and ciphertext hash for mutating steps. No raw rows or
passwords belong in the request. The dispatcher requires the LF SHA256 of the
reviewed `native_host.py` and defaults to preflight without dispatch.

```text
python -I -B operations/sql-backup/recovery/native_step.py inspect \
  --request <private-request.json> --source-volume <actual-volume-id> \
  --host-sha256 <reviewed-LF-SHA256> --evidence <private-directory>
```

Only an authorized operation adds `--dispatch --confirm-step "inspect <trial>"`
(or the exact `fence`/`restore` step). It records an exclusive intent and the real
SSM command ID. Existing intents and uncertain results require reconciliation;
changing an ID is not permission to repeat a mutation.

## Ordered operation

1. Start the RTO clock before draining writers. Acquire the existing operation
   exclusion, record the blue/green desired counts and scale them to zero through
   native delivery. Verify zero running/pending tasks and no other writers.
2. Run `fence` once on the source. It checks data and migrations, stops the backup
   timer, disables runtime/migrator logins, sets `demodb` READ_ONLY with NO_WAIT,
   verifies no sessions, and produces a new remote-verified backup. An old success
   file cannot satisfy this step. Capture its exact manifest/backup VersionIds.
3. Apply only the reviewed **full Data plan**, using the same owner/backend and
   normal locking. CROSS-AZ selects the other real private subnet; SAME-AZ uses
   an explicitly reviewed compute replacement plan. Preserve encrypted disks.
   No target, import, manual state surgery or automatic corrective apply.
4. Positively verify the exact source EC2 ID is **terminated**, and its original
   encrypted disk is available/detached. Stopped, unreachable, timed-out or an
   inaccessible SSM agent is not accepted as this procedure's final fence.
5. Wait for fresh EC2 bootstrap and SSM Online. Deliver only the existing public
   installer and metadata through SSM. Run `install_native_tls.py` with the exact
   existing TLS transport Secret ARN/VersionId, then `probe_native_tls.py`.
   Renew only the previously reviewed exact-secret read grant if required. Do
   not put the private key in commands, user data, Terraform, artifacts or logs.
6. Run `install_native_backup.py --instance-id <new-id> --private-ip <new-ip>
   --config <private-config-path>` on the new host. It authenticates the instance
   role, downloads the already-published exact package version, checks the entire
   archive and manifest before executing helpers, and prepares strict backup
   credentials. It neither starts a timer nor enables the application runtime.
7. Run `restore` once with the authentic fence receipt and backup. The dispatcher
   re-reads the original SSM result and current EC2/volume APIs. The host restores
   into a new database, runs the existing CHECKDB verification, compares row count,
   ciphertext hash and both migrations, preserves the empty bootstrap database,
   remaps approved users and keeps runtime disabled. No database DROP or WITH
   REPLACE is used. Any uncertain step stops before activation.
8. Execute the existing reviewed `sql_principals_activate_runtime` handoff using
   its strict-TLS client, verify runtime SELECT/INSERT plus EF-metadata SELECT and
   absence of administrative/DDL grants. Write one new connection-secret version
   via the authenticated in-memory SDK path, retaining the old version. Register
   the native task revision with the current qualified image and exact secret
   version; restore the recorded desired count only after all gates pass.
9. Verify `/health`, `/ready`, pre-recovery records, a new POST/GET/decrypt round
   trip, actual task placement and SQL destination. End the RTO clock only here.
   Re-enable the existing hourly timer on the new host; verify a real backup and
   external observation. Record the new Data state and zero persistent locks.

The fresh host installation reuses the exact package
`7658cb3ac4b226d1ee069a24e6e862d3435c8862bad40bee8444eeefeb52fa40`,
S3 version `BkdqGclnbSplQTmo66qIF40pFWsruFrR`, and the original approved public
certificate fingerprint. No package rebuild, new PKI or permanent recovery host
is needed. Expired permissions must be addressed before interruption, not during
an improvised restore.

## Measurements and failure boundary

Record each UTC transition: drain, positive SQL fence, final backup, source EC2
termination, new launch, SSM ready, TLS, restore/CHECKDB, handoff, ECS ready and
functional round trip. Report the sum as observed RTO. Report both the last
scheduled backup's age at the simulated failure and any final planned-cutover
backup optimization; the latter is not proof of zero disaster RPO.

If a destination fails, keep the source fence, verified backup and retained disk.
Do not restart an old writer automatically. After new writes, the old disk is
stale and requires reconciliation before any return. Retained disks and remote
versions continue to incur charges; their eventual deletion needs separate
authorization. The two-day lab window does not authorize indefinite retention
of active compute or a third trial.
