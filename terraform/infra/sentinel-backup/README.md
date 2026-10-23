# Sentinel backup pipeline — local Terraform/Terragrunt increment

This is reviewable local source, not an admitted deployment. The prior USD1 cycle is closed.
It creates no resources until a separately reviewed plan/apply. No existing ECS/EKS root,
CloudFormation stack, state, backup bucket or IAM role is imported or modified here.

The isolated administrator-owned root follows the repository's separation from ordinary
TARGET lifecycle: Terraform owns the two runtime roles/boundaries and all resources in
this module. It requires separately selected lifecycle and existing EC2 sender identities.
The sender's one-queue SendMessage policy is an OUTPUT PROPOSAL, never an attachment
silently installed on an existing role. There is no CloudFormation execution role,
business service, CA, NAT provider, EC2 instance or new authentication mechanism.

## Ownership and immutable code

- One pipeline module owns DynamoDB's original PK/SK and Due/Active/Cleanup schema;
  a private versioned SSE-S3 archive; SQS/DLQ/policies; logs; two Lambda roles/boundaries;
  two .NET10 Lambdas; SNS and its email subscription; event-source mapping.
- Terraform also owns the content-addressed code object. Both Lambdas bind its actual
  S3 version and local SHA256. The release manifest must have matching source/upstream
  commits, digest, v2 contract and admitted runtime mode. Old trial manifests fail closed.
- CI/package preparation produces code; Terraform alone updates Lambda code/configuration.
  No competing CLI updater, ignore_changes or destroy provisioner is present.
- Namespace/archive prefix derive from the original Sentinel JSON-array SHA256 contract,
  cross-checked against the real C# implementation.
- Mapping is disabled by default. Confirm SNS and reviewed mode/producer before enabling.
  No automatic dispatcher schedule is created: see the cursor gate below.

## Toolchain boundary

Existing ECS roots retain AWS5.100.0. That version validates Lambda runtimes using a
Lambda SDK enum without dotnet10. This NEW root pins AWS6.30.0 only: its SDK1.87.1
contains dotnet10. No provider was downloaded, initialized or locked for this root.
The installed Terraform1.13.4 parsed the module but validate is BLOCKED by missing
required provider; Python source checks are not provider/schema/plan acceptance.

Official source:
- [AWS5.100 runtime validation](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/lambda/function.go#L316)
- [AWS6.30 dependency](https://github.com/hashicorp/terraform-provider-aws/blob/v6.30.0/go.mod)
- [SDK1.87.1 runtime enum](https://github.com/aws/aws-sdk-go-v2/blob/service/lambda/v1.87.1/service/lambda/types/enums.go)

A future tool qualification must verify official signed/checksummed platform archives,
generate the real lock and test this isolated module. Do not copy a5.x lock, fabricate
hashes or upgrade the14 existing TARGET roots to bypass that gate.

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
original dispatcher/fences and returned continuation. The caller MUST retain/pass its
cursor, including empty pages with a continuation. Restarting every tick at null could
starve later work; therefore automatic scheduling remains deliberately unwired until a
durable caller checkpoint is implemented/qualified. It does not scan all tenants.

Active RequestFunctionalProbe work is explicitly UNSUPPORTED: no attempt, no claimed
success and no NAT worker. For a closed episode, the original store's CAS/obsolescence
checks cancel old probes/checks. Tests prove multi-page reconciliation, real archive/
audit ACKs with SDK doubles, and that an unsent stale failure notification is cancelled
after recovery instead of sending a misleading late failure email.

The original reducer still requires NAT-shaped policy fields and emits probe intents.
Those inert fields are validated; no original core is forked to erase inconvenient work.
A service-neutral upstream probe-capability policy remains the right permanent fix.
Periodic independent observations supply actual backup-health evidence in this increment.
They do NOT prove restoration. A missed/crashed observer watchdog is also not installed.

## Lifecycle and next integrated test matrix

1. Qualify isolated provider/lock and new immutable v2 package. Review account/principal,
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
