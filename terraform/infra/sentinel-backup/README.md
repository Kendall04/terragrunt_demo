# Sentinel backup pipeline — local Terraform/Terragrunt increment

This is reviewable local source, not an admitted deployment. The prior USD1 cycle is closed.
It creates no resources until a separately reviewed plan/apply. No existing ECS/EKS root,
CloudFormation stack, state, backup bucket or IAM role is imported or modified here.

The isolated administrator-owned root follows the repository's separation from ordinary
TARGET lifecycle: Terraform owns the two runtime roles/boundaries and all resources in
this module. It requires selected lifecycle and sender identities. With the optional observer
module the dedicated sender role is created explicitly; pipeline-only use selects an existing role.
The sender's one-queue SendMessage policy is an OUTPUT PROPOSAL, never an attachment
silently installed on an existing role. There is no CloudFormation execution role,
business service, CA, NAT provider or new authentication mechanism. The pipeline-only
module has no EC2; the OFF-by-default observer module is described below.

## Ownership and immutable code

- One pipeline module owns DynamoDB's original PK/SK and Due/Active/Cleanup schema;
  a private versioned SSE-S3 archive; SQS/DLQ/policies; logs; two Lambda roles/boundaries;
  two .NET10 Lambdas; SNS and its email subscription; event-source mapping.
- Terraform also owns the content-addressed code object. Both Lambdas bind its actual
  S3 version and local SHA256. The release manifest must have matching source/upstream
  commits, digest, v3 contract and admitted runtime mode. Old trial manifests fail closed.
- CI/package preparation produces code; Terraform alone updates Lambda code/configuration.
  No competing CLI updater, ignore_changes or destroy provisioner is present.
- Namespace/archive prefix derive from the original Sentinel JSON-array SHA256 contract,
  cross-checked against the real C# implementation.
- Mapping is disabled by default. Confirm SNS and reviewed mode/producer before enabling.
  Dispatcher scheduling is opt-in and OFF by default; enabling adds three explicitly scoped
  EventBridge rule/target/Lambda-permission resources. No cadence default is chosen.

## Toolchain boundary

Existing ECS roots retain AWS5.100.0. That version validates Lambda runtimes using a
Lambda SDK enum without dotnet10. This NEW root pins AWS6.27.0 only: its SDK1.87.0
contains dotnet10. One Windows provider was downloaded to the central project cache and verified against
official release/Registry SHA256 plus detached GPG signature with the same renewed
HashiCorp primary key. Terraform generated the Windows lock; actual provider schema
and root validate PASS (zero diagnostics) using a junction to that one binary.
The S3 backend was not initialized and no AWS API was called. The schema probe has
no resources/backend. This does not qualify an apply/destroy or Linux provider.

Official source:
- [AWS5.100 runtime validation](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/lambda/function.go#L316)
- [AWS6.27 dependency](https://github.com/hashicorp/terraform-provider-aws/blob/v6.27.0/go.mod)
- [SDK1.87.0 runtime enum](https://github.com/aws/aws-sdk-go-v2/blob/service/lambda/v1.87.0/service/lambda/types/enums.go)

[Provider qualification](provider-qualification.json) records the adjacent minimum-version
boundary, signed checksum, real lock/schema and central-cache evidence. Official6.26
has no dotnet10 enum,6.27 does. Additional platforms need their own authentic lock entries;
do not copy a5.x lock or upgrade the14 existing TARGET roots.

## Inputs, state and local commands

The Terragrunt wrapper reads explicit SENTINEL_INPUTS_FILE metadata JSON and
SENTINEL_STATE_BUCKET / SENTINEL_STATE_REGION / SENTINEL_STATE_ID. Its S3 backend
uses an isolated sentinel-backup/<state-id>/terraform.tfstate key, encryption and
native locking. The backend must already exist under separate reviewed authority;
no credential/profile/default account or email is selected.

Input config is defined in main.tf.json: account/region/name/source/ZIP/manifest,
existing same-account sender role and lifecycle principal, subject/correlation scope,
logical owner, email, notice policy, timestamps and retention/evaluation bounds.
No SQL/password/secret values belong in inputs or state. The current managed runtime
remains a bounded sandbox contract (<=24h), including observer-check mode, not an
indefinite production service. Permanent timing/retention is not silently chosen.

Offline checks from repository root with existing tools only:

    python3 -I -B -m unittest discover -s operations/integrations -p test_terraform_pipeline.py -v
    python3 -I -B -m unittest discover -s operations/sql-backup -p test_sentinel_publish.py -v

Managed tests additionally need the separately verified pinned Sentinel staging source
and existing locked NuGet cache. Private-source acquisition/OIDC/hosted CI is a future gate,
not implemented by adding these source checks to repo hygiene.

## Producer, admission and outbox policy

sentinel_publish.py wraps the existing observer's actual CHECK command. It durably
stores a candidate BEFORE local transition state advances, retries the identical payload
after uncertain SQS acceptance and never overwrites pending work with newer observations.
A fresh tick drains old pending work first; this can delay newer checks during delivery
failure. Max1..3 attempts and expiry are explicit; counters survive restart/crash.
A recognized access denial blocks automatic resends pending review. A known SQS MessageId
means ENQUEUED, not incident commitment or email delivery. SQS Standard can duplicate;
the original Sentinel receipt identity deduplicates the exact observation.

The AWS CLI path is explicit and must already exist on the chosen independent observer
host. Its subprocess receives no inherited AWS keys/profile/custom endpoint/config.
Only the EC2 role path is permitted; IMDSv1 is disabled. No credentials are copied.
The replacement systemd service/timer are INERT: host, role, cadence, expiry, expected-UP,
local producer-failure receipt and attempt limit need reviewed configuration. Do not run
the old observer and replacement unit simultaneously on the same state.

Managed admission separates synthetic-trial (LOCAL_RECEIPT_REPLAY) from explicit
observer-check (CHECK_COMMAND_RESULT); neither can relabel the other. Normalizer/ACK,
DynamoDB store/reducer/outbox and S3 archive remain original pinned Sentinel components.
Readable SNS content now has an explicit real-observation mode, still says a backup
health check is not a SQL restore, and never calls SNS acceptance inbox delivery.

DispatchFunction.Reconcile uses the original durable work directory, one20-item page,
original dispatcher/fences and a durable checkpoint in a single CTRL item in the SAME
table/namespace. Conditional revision/worker/lease checks prevent competing/stale
workers advancing it. A crash retains the old page until lease expiry; uncertain writes
grant no execution. Empty-page continuation is preserved. External cursor overrides are
rejected. No alternative receipt/outbox/backend exists.

Opt-in watchdog tracks one additional monotonic heartbeat CTRL item, including valid
suppressed healthy observations. Last arrival is not backup health. With an explicit
deadline and expected-UP=true it reuses the original TelemetryWatchdog and reducer:
missing observations mean UNKNOWN, never an invented failed backup or restore.
Unknown escalates on the existing recovery budget; only later genuine healthy evidence
can heal. Ingest and watchdog share one explicit catalog identity; the original policy-
migration guard remains. Expected-down disables watchdog evaluation, not fake recovery.
Enable expected-UP only with reviewed matching producer cadence/heartbeat configuration.

Optional EventBridge scheduling invokes only the dispatch function through its exact
rule ARN and account. Target retry is zero, but Lambda asynchronous error retries
and duplicate delivery remain possible; the durable cursor/lease still applies. The
next reviewed tick can resume the durable page. The existing application remains one business API. All units/flags are
uninstalled/disabled until a future admitted cycle.

Active RequestFunctionalProbe work is explicitly UNSUPPORTED: no attempt, no claimed
success and no NAT worker. For a closed episode, the original store's CAS/obsolescence
checks cancel old probes/checks. Tests preserve these distinctions and cancellation
of an unsent stale failure notice instead of misleading late email.

The original reducer still requires NAT-shaped policy fields and emits probe intents.
Those inert fields are validated; no original core is forked to erase inconvenient work.
A service-neutral upstream probe-capability policy remains the right permanent fix.
Periodic independent observations supply actual backup-health evidence in this increment.
They do NOT prove restoration. The watchdog code is local-qualified only; no schedule/unit is installed. No guarantee covers
failure of Sentinel itself; an independent host/location and its checker-read role remain
subject to explicit identity/access review. Neither is provisioned by the pipeline module;
the optional observer module provides its own host/role under separate opt-in.

## Lifecycle and next integrated test matrix

1. Qualify isolated provider/lock and new immutable v3 package. Review account/principal,
   backend key, sender role/host, email, timing, retentions, budget and both saved plans.
2. Inventory names and effective CREATE/READ/DELETE permissions once. Include the known
   historical Get/DeleteEventSourceMapping wildcard-context limitation in the approval
   scope if it applies; never auto-widen grants after denial.
3. Apply with ingestion disabled; verify versioned code, runtime/namespace, roles and SNS.
   Owner confirms subscription; install only reviewed producer SendMessage access/unit.
4. Exercise real checker MISSING/STALE/failure/UNKNOWN/recovery using synthetic receipts/
   disposable data; verify authenticated ingress, durable ACK, dedupe, uncertain-send
   retry, no NAT effects, actual S3 archive and separate inbox receipts. Preserve cursor.
5. Quiesce producer/ingestion, settle known inflight work, export receipts/queue/outbox/
   archive identities. Active unsupported work stays visible; never mark it successful.
6. A saved destroy must show ONLY the new integration. Table deletion is protected by
   default. Changing allow_data_retirement needs the explicit irreversible-data decision.
   Bucket force_destroy stays false: export/hash/version-match and delete only owned
   synthetic objects/versions under the approved retirement receipt before bucket removal.
   Terraform's code-object resource deletion is not proof every historical version vanished.
7. Destroy runtime, policies, roles/boundaries/logs/topic/queues and data only as admitted.
   Verify native absence and original resources/access preserved; retain terminal state/
   exported evidence and restore any separately installed sender/lifecycle access.

Expected lifecycle API groups (review proposals, not effective grants):
S3 bucket/config/policy/version/object CRUD; DynamoDB table/index/encryption/retention
descriptions and table CRUD; SQS queue/attributes/tags/policy CRUD; SNS topic/subscription/
policy CRUD; Lambda function/code/concurrency/tags plus mapping Get/Create/Update/Delete;
CloudWatch Logs describe/retention/delete; IAM role/trust/inline/boundary/policy/version
CRUD and PassRole ONLY the two Lambda roles to lambda.amazonaws.com. Mapping callbacks may
evaluate "*" without function context: any fallback grants regional metadata/delete
capability beyond a UUID and requires explicit disclosure/consent, not IfExists fiction.
There is no CloudFormation permission in the final path.

Local tests do not satisfy those AWS/installation/durability gates. Prior2+2-day backups,
original states/evidence, prior synthetic-trial receipts, EKS/demo and PKI scope are unchanged.

[Next integrated trial proposal](NEXT-INTEGRATED-TRIAL.md) separates the locally qualified pipeline from the unimplemented observer-host slice; it grants no deployment authority.

## Optional observer host local increment

The OFF-by-default [observer module](modules/observer/README.md) now provides its own
network/instance/profile and restricted SSM control, reusing one versioned code object
in the pipeline bucket. Full scheduled source inventory43, pipeline-only29/base26.
No installed host/timer or AWS access. [Coordinated reads](READONLY-PREFLIGHT.json) and
[required capability contract](required-capabilities.json) precede any exact grant or
new consent. The Lambda ZIP bcac19f is unchanged; the host has a separate bundle lineage.

## Current review update — 2026-10-24

[Exact proposed cycle and reversions](REVIEW-r20261024b2.md) supersedes the earlier
AMI-unselected/preflight-pending and unchanged-Lambda statements above. The metadata
preflight completed without mutation; bounded send/notice code requires NEW qualified
artifacts. Earlier qualification receipts remain immutable historical evidence. No
consent, deployment or successful AWS observer execution is implied.

## Executed b2 status — 2026-10-24

The [b2 trial](../../../operations/integrations/NATIVE-TRIAL-2026-10-24.md) created43
resources and closed cleanly at07:01:54UTC, restoring original access. Native
AL2023 bootstrap, Lambda/DynamoDB cursor and teardown were demonstrated. SSM
authorization remained blocked; periodic producer/checker/SQS/notice acceptance
is not established. Earlier proposal/qualification documents are dated snapshots,
not current deployment authority. No live resources or new budget are implied.
