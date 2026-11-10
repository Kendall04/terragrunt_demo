# Portable SQL cohost: local package integration closed

The new cohost tar is built from `0359bafa1fbb3c48ebc53ce29836acf034381108`,
with254 payload files and133,703,680 bytes. SHA256:
`081b62f739cd309e84abf64b5c8e327bf6b7445214f37d85069fa070f0e2f24f`.
It reuses exactly the verified self-contained Linux-x64 SqlBackup10.0.13 component
from `b2bf8d82938e690561a85e45b3ab9e2a383413cf`; no new C# component publication,
SDK, Docker build or dependency download. The original component manifest/hash and
every binary file are verified; C# and project sources are unchanged (only the known
platform-specific lock update differs). Old tar/ZIP/receipts remain immutable.

Its paired managed-dotnet10 Lambda remains the qualified `25f037e` ZIP,
SHA256 `4e89587b2760b5ec6d4a37a4bc6327ed6f770d0316d2e1f3fba32d4b1d54cca7`.
Upstream Sentinel stays pinned to `b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828`.
The cohost includes the portable publisher; the Lambda deliberately does not.
Neither artifact hash or fixture receipt provides installation/deployment authority.

## Actual wiring

`package.py build --with-observer --with-portable` adds the four small portable files
under `portable/`, records EVENTBRIDGE_REPORT_V1 and its contract hash. The compact
`sentinel.Portable={SchemaVersion:1,ContractSha256:...}` opt-in selects the mode.
The exact two-monitor installation, bridge settings and Lambda binding are carried in
the verified package rather than duplicating them in User Data. This trial binding
admits only FULL_COPY_ONLY_CHECKSUM, backup Artifact/freshness2h and host Reported
telemetry/freshness20min. Installed contract hash, subject, deployment, producer,
account, region, cadence and window are checked; mode drift refuses installation/start.
The existing legacy SQS mode remains unchanged and cannot consume portable settings.

The existing SQL bootstrap still verifies EC2-role identity, exact artifact version,
owner, KMS context and package hash, then imports that package's installer. No new
transport, remote-exec, Session Manager or SSM retry. Portable rendering replaces the
observer service ExecStart with the installed `portable/cohost_runtime.py run`; the
real integrity ExecStartPre, sandbox, StateDirectory and no-force-kill settings remain.
The entrypoint accepts no caller config/transport/collector override. It derives the
check path, public config, local producer-job receipt and state directory, runs the
actual existing observer, projects two Report entries and uses the actual durable
EventBridge publisher. Environment forwarding excludes SQL/AWS secret credentials.

The two target/timer groups remain inert at install. Observer activation can plan/run
without producer SQL credentials; the producer still needs its independent admitted
credential handoff and activation flag. No SQL credential is fetched by the observer.
The existing IaC rule that producer-at-boot also requests observation remains intact.
No change to SQL backup frequency/retention or public API. Lost producer success remains
UNKNOWN; a heartbeat never refreshes backup dataAt. One atomic journal preserves20
entry attempts total and3 per pending entry across restart/partial/uncertain outcomes;
it never selects legacy SQS concurrently. Exhaustion/denial needs review, not a reset.
External Sentinel/watchdog remains outside the SQL failure domain and supervises the
separate host expectation; no independent S3 observation is claimed by this mode.

## Evidence and exact limits

-44 POSIX package/legacy/cohost tests pass.33 bridge/durable-publisher tests pass on
 Linux, including the final budget slot. Three existing source-wiring checks pass.
-42 artifact/installed-flow checks pass on WSL Ubuntu24.04: real tar inventory and ELF,
 actual rendered bootstrap Python with only fixture-root/time remapping and explicit
 STS/S3 doubles, inert and idempotent installation, no credentials/services, exact
 installed imports/integrity, producer refusal, and real ELF synthetic-receipt replay.
 The first fixture omitted the host's normal `/var/lib` parent; its failed log is kept.
 The fixture was corrected; the sealed tar was reused without rebuilding it.
-The compact opt-in is2128 base64 bytes, below the existing4096 budget; the Terraform
 source formats cleanly. Actual fully rendered future EC2 User Data still needs the
 ordinary size/identity admission. No global provider or runtime version was changed.
-The installed observer/publisher produced missing, failed/unconfirmed, stale and fresh
 reports. Eight entries plus one partial retry consumed nine durable attempts; retry
 reused the exact pending entry and did not rerun the checker. The checker port is an
 explicit double wrapping the ACTUAL ELF's synthetic `replay-check`, not a successful
 native S3/SQL `check`. No generated receipt or Report was sent to AWS.
-17 integrated C# checks pass with the SAME shipped Worker.Lambda, Portable,
 Portable.Aws and readable Host DLL bytes from the immutable Lambda ZIP. They invoke
 the original SQS Lambda Handler with real serializer/ReportNormalizer/reducer/audits,
 original memory persistence fake and pinned-SDK SNS double. Duplicate ACK, foreign
 queue rejection, UNKNOWN opening, no false recovery from failed/stale reports, same
 incident resolution, readable schema2 attention/recovery and no NAT probe are checked.
 Future supervision stays pending; no outbox-drained claim. The outer portable Lambda's
 AWS/DynamoDB composition is not invoked. Its default factory/serializer/package load
 was separately qualified by136 prior checks. No native DynamoDB/ACK/SNS/inbox proof.

The plain-text examples are in the local evidence `readable-notices.json`, headed
PRUEBA SINTÉTICA with state, reasons, revision/time, IDs and provider-only acceptance.
They were produced by the real original notification adapter; nothing was mailed.

## Proposed access and resource effect, not execution

`trial/cohost-access-proposal.json` contains the proposed source-specific policy for
`arn:aws:iam::341936017254:role/demo-dev-data-sql-ec2-role`: only events:PutEvents to
`arn:aws:events:us-east-1:341936017254:event-bus/ecs-portable-r20261026p1`, with exact
`events:source=sentinel.report.sql-observer`, detail-type `Sentinel Observation v1`,
us-east-1 and a newly admitted time window. No SQS send is required in portable mode;
reverse only an OWN legacy temporary delta if one is actually found/admitted, not any
unrelated existing grant. The shown times are fixture inputs, not effective authority.

Future publication uses only the exact new cohost artifact key/hash in that proposal.
Its actual S3 VersionId remains unbound until an approved immutable publication. Any
SQL-role GetObjectVersion / KMS Decrypt delta must bind that exact version/object,
ViaService and encryption context/window. No extra BAK access, originals change or
retention extension. Current role/bucket/key policies have NOT been reread this turn;
there is no truthful current installable delta or permission reversal receipt yet.

The portable backend remains62 mock-plan addresses (55 upstream +4 boundaries +3 SNS).
This cohost wiring adds ZERO observer EC2/network/cloud addresses and no new AWS calls.
It needs an already separately approved SQL host; none is created by these changes.
62 is not a full ECS/recovery inventory, and historical102/USD6 are not reused.
The prior USD2 proposal is serverless-only; it does not authorize a SQL/ECS trial or
current deployment. No new budget was opened here.

## Remaining external gates

Local packaging/bootstrap/publisher/schema/handler/readable-adapter wiring is closed
within the boundaries above. Before live: fresh identity/current IAM/backend/names and
manual-deletion reconciliation, new exact paired-artifact/publication scope, actual
saved plan, budget, SNS subscription, effective workload role and full rollback/retirement.
Native boot/systemd under the actual SQL OS/service identity, actual SQL/COPY_ONLY/S3
checks, EC2-role EventBridge, durable AWS state/ACK/outbox/watchdog and SNS/inbox still
need the approved trial. First verify the autonomous observer independently of the
producer; admit producer only after the real credential handoff. Keep a user review
window within the new trial budget and teardown reserve. No indefinite waiting.

The autonomous observer requires no RunCommand. Historical SSM denial is unresolved;
SQL fencing/restore/public Fargate recovery remains its separate transport/acceptance
gate, without an alternative principal/SSH/transport used to evade the denial.
No AWS, permissions, host services, credentials, cloud state, push or workflows changed.
