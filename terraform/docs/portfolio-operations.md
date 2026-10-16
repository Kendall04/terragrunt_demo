# Portfolio closure and practical DEV operations

## Closure snapshot — 2026-10-16

The original full DEV system completed UP → VERIFY → DOWN, was reconstructed,
and passed real qualification, blue/green, distinct-digest rollback and NAT
replacement trials. Final DOWN completed at 05:38 UTC on October 16 (October 15,
23:38 in Costa Rica). The API is offline; **do not start another session as part
of project closure**. Historical sections describing running DEV are dated
checkpoints, not the present resource state.

A new read-only AWS inventory on October 16 confirmed all five runtime states
empty and their S3 lockfiles absent; the cluster INACTIVE with zero tasks/services;
no matching runtime EC2, EBS, EIPs, NAT ASGs, ALB/target groups, API/VPC Link, VPC,
subnets or ENIs. Native service observations supplemented state inspection.
No self-owned AMIs or EBS snapshots were observed in the account/region. This is
a bounded project inventory, not an account-wide billing certification.

The audit used the explicitly authorized `cnp-cert-dev` profile in the verified
project account and `us-east-1`. Raw inventory, state inspection and publication
review stay in private local evidence outside Git; no secret values were read.
[Final teardown evidence](e16-practical-dev-lifecycle.md#final-real-dev-down-completed--2026-10-16-utc)
records the destructive plans, approvals, permission removal and terminal results.
E2 remains generation 14 RELEASED. The old E13 SDC attempt remains historically
UNKNOWN: the owner's exact-attempt residual-risk disposition allowed shutdown,
not fabricated ABSENT/APPLIED/SUCCESS. Original FAILURE and versioned S3 evidence
remain intact. Its archived, explicitly authorized SQS message was acknowledged;
there was no queue purge or alteration of historical failure evidence.

## Prerequisites for a separately authorized future session

1. Read [E16](e16-practical-dev-lifecycle.md), [bootstrap](bootstrap.md),
   [security](secrets-strategy.md) and [validation](validation.md). Use the
   reviewed source/locks and existing supported toolchain: Python, AWS CLI,
   Terraform 1.13.4, Terragrunt 0.93.3, .NET 8.0.425 and Linux/Docker where needed.
2. Configure legitimate temporary AWS authentication locally. Scrub overriding
   credential environment variables; explicitly select the approved profile and
   region. Verify effective account/caller before any AWS-facing process; never
   fall back to `default`. Do not transfer sessions between machines or put keys
   in GitHub, source, Terraform variables or shell output.
3. Retain/verify the separate security backend and the private, versioned,
   encrypted runtime S3 backend with native S3 lockfiles. The five keys are
   `e1/lifecycle/dev/<layer>/terraform.tfstate`, default Terraform workspace only.
   E16's installed exclusive DEV writer policy must match the selected operator;
   WP5 must not concurrently write these same states. PROD/shared/security state
   is excluded. A local JSON declaration alone is not installation evidence.
4. Keep configuration/session directories outside Git with restrictive access.
   E16 configuration uses `E16_SUPERVISED_DEV_V1`, exact account/region/profile,
   operator ARN, clean source commit and the approved per-layer variables.
   Read secret *metadata* through the approved path; bootstrap secret values
   out of band. Do not place secret values in plans, state, logs or user data.
5. Reconcile any E2 ACTIVE owner, unfinished build, stale plan or unknown effect
   before continuing. Previously retained history is not permission to seize
   authority or reuse the historical SDC exception for another attempt.

## Original UP and functional verification

Use the existing operator; this alias is a readable example, not an additional
execution authority. The paths must point to a reviewed private configuration
and session directory. Do not execute it during closure.

```bash
dev() { python scripts/original_dev.py dev "$@" --config /private/dev/config.json --directory /private/dev/session; }
dev init
dev status
dev bootstrap-status
dev up-plan
# Inspect the real full preview, preview.json and saved binary.
dev apply --plan-id <reviewed-id> --confirm '<exact printed APPLY DEV confirmation>'
# Prepare/review/apply the next layer only after the previous result is understood.
```

Order: **global → data → platform → apps → edge**. A fresh network first needs
`bootstrap-network-plan`: create the original VPC/subnets/EIPs/ALB skeleton, then
bind the real new subnet/SG/EIP/route IDs into existing security-root NAT launch
and E13 installation. Only then create both ASGs with a new reviewed global plan.
Do not reactivate retained NAT triggers against the destroyed session's IDs.
SQL uses approved Ubuntu 22.04 x86-64 / SQL Server 2022 Express bootstrap, existing
secret metadata and a newly observed private address. Refresh the connection
secret through the approved bootstrap before applications consume it. See E16's
[staged installation](e16-practical-dev-lifecycle.md#first-empty-account-installation-staged-without-invented-ids).

The operator applies the exact saved plan after source, configuration, state,
identity and binary checks. Five states are separate transactions. Partial apply
is not completion, and `up-plan` does not qualify an image or start application
traffic. Use the existing WP3/WP4 handoff below, then `dev verify`: current AWS
network/NAT/SQL/ECS/API observations, per-task readiness and actual `/ready` plus
POST/GET `/text` SQL/KMS checks. This command writes test data and is not a pure
read-only audit. No functional probe is appropriate against the destroyed API.

## CI/CD, release and rollback boundary

Use the existing `release-build.yml`, `deploy-dev.yml` and
`rollback-manifest.yml` manual callers and their immutable protected reusable
workflows. WP3 runs seven qualification controls and its authorized publisher;
WP4 accepts qualified release IDs and protected histories, promotes traffic and
cleans up automatically. Application images use ECR **digests**, never mutable
`latest`. The neutral qualified repository differs from the manual DEV bootstrap
repository; an old manual image is not a newly qualified release.

The demonstrated path used exact `refs/heads/codex/final-github-actions-cicd`,
Environments `e1-release` / `e1-dev-deploy`, and reusable-workflow pin
`f0ba8ad1d6528d362693c8de932f935c8084529d`. A merge to `main` neither changes those
bindings nor proves main-based deployment. Rebinding them would require a separate
review, authentic admission/installation and live test; it is not part of closure.
The entry gateways are currently inhibited. Do not dispatch a release or deploy
until a future authorized session has verified its runtime and bindings.

[Real A → B → A evidence](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback)
contains the complete releases/digests and Actions runs. It proves rollback of an
unchanged-schema application, not recovery of deleted SQL data or PROD operation.

## Supervised DOWN and failure handling

1. Confirm identity/backend, record resource IDs, save a private inventory and
   verify no conflicting Terraform/WP3/WP4/E2 operation. Obtain separate explicit
   infrastructure-destruction and permanent SQL/EBS-loss approvals.
2. Use `dev inhibit` with its exact confirmation; observe controllers, ECS,
   published Lambda versions, logs, queues, ASG activity and known E13 effects.
   Do not equate missing metrics, empty approximate queue counts or disabling
   EventBridge with finality. Drain ECS and normally stop SQL before terminating
   NAT needed for their connectivity. Reconcile effects and review inhibition
   through `dev review-inhibition` before a destructive apply.
3. Prepare each `dev down-plan`, inspect its actual scope and apply that saved
   binary in **edge → apps → platform → data → global** order. `data` additionally
   requires `--confirm-sql-loss 'PERMANENTLY LOSE DEV SQL <binary-hash>'`.
   E16 rechecks state/plan integrity and ordering; never silently regenerate a
   different approved plan or use `destroy -auto-approve`.
4. On failure, stop advancing. Preserve state, binary, preview and receipts;
   inspect native resource state and reconcile before reviewing a fresh plan.
   No blind retry, state deletion, automatic force-unlock, owner takeover or
   historical SUCCESS fabrication. Exceptional temporary permissions or exact
   historical-risk dispositions from the completed session do not carry forward.
5. Run `dev residual` and independent service reads of recorded resource IDs,
   parent VPC/ENIs and tagged resources. Check all five empty states and absent
   locks. Report confirmed removal, pending deletion, deliberately retained,
   unexpected and unverified resources separately. Tags or empty state alone do
   not establish complete removal or a zero AWS bill.

## Retained resources and possible charges

This October 16 **read-only** audit created, changed and deleted no AWS resources.
The following are retained deliberately unless a separate cleanup is approved:

| Observed resources | Reason / classification | Continuing cost exposure |
| --- | --- | --- |
| 6 private, encrypted, versioned S3 buckets | Runtime/security backends, control bundles, qualified artifacts, quarantine and WP4/E2/E13 evidence | Object/current/noncurrent version storage, requests; about 232 MB of listed object versions, excluding delete-marker overhead |
| 14 immutable-tag ECR repositories, 20 image manifests | 2 application repositories plus protected controller/worker/delivery/NAT images; reproducibility and digest/history references | Layer storage and transfer; summing image sizes is not deduplicated billed storage |
| 1 enabled customer-managed KMS key, 3 Secrets Manager secrets | Existing data/control identities and separately managed secret values | Key/secret retention and future requests; values were not read |
| 5 CodeBuild projects, 7 Lambda functions | Neutral WP3/WP4 and DEV recovery components; no active builds observed | Future build minutes, invocations/duration and logs; configured project/function count alone is not running compute |
| 12 protected log groups, 14-day retention | Release/deployment/recovery evidence | Stored bytes and future ingestion/query charges |
| 1 AWS-created Container Insights performance log group, 1-day retention | Residual ECS telemetry outside the five empty runtime states | About 2.36 MB observed; expiry is asynchronous, not a zero-storage guarantee |
| 6 recovery alarms, 2 diagnostic SQS queues, retained SNS alert topic | Recovery diagnostics and evidence; queue approximate counts zero at audit | Alarm charges, messaging/requests, future ingestion; no email notification delivery is claimed |
| 21 protected IAM roles, 2 instance profiles, OIDC provider, 2 NAT launch templates | Reusable security/runtime configuration | No running instance implied by a template/profile; associated storage/execution services can charge |

NAT launch EventBridge is DISABLED. Three NAT handlers, release/deploy gateways
and cleanup have reserved concurrency zero. The neutral release-completion rule
remains ENABLED for its installed finalizer, with no active builds observed;
this does not recreate a VPC, ASG or SQL instance. The operator has no temporary
inline policy; the final DOWN verified removal/denial of the temporary grants.
No new permissions or controller activation were installed during closure.

**Separate cleanup proposal, not execution:** review the unused Container Insights
log group and six dormant recovery alarms first; then consider quarantine/failed
build objects and superseded image/bundle versions only after checking protected
receipts, installed VersionIds and rollback dependencies. Untagged ECR images are
not necessarily garbage. Backend/state versions, original failure evidence,
required releases and identities remain excluded from ordinary runtime DOWN.
Any new retention/deletion decision needs explicit scope and approval.

While UP, both NAT EC2 slots, SQL EC2/EBS, Fargate, ALB, public IPv4/EIPs and traffic
also cost money, along with API Gateway, logging, KMS/secrets, builds and storage.
A future estimate must use the chosen region, actual sizes/counts, session hours,
traffic, ingestion and retention with current AWS prices; no fixed budget or
zero-dollar outcome is approved or promised here.

## Final publication boundary

The repository is PUBLIC. `main` and divergent `develop` are protected by an active
GitHub ruleset requiring a pull request and one approving review, with no bypass
actor. Preserve develop's independent commits and publish the final feature
branch only after owner approval; use a normal merge commit through the required
PR/review path to preserve history. No force push, squash or history rewrite.

Feature-branch push runs `ci.yml`; a PR to main also runs CI/CD-safety checks.
The eventual main merge touches application/infrastructure across the full
unpublished history, so `cd.yml` also matches. Its main path can classify changes,
print promotion instructions or fail closed on protected infrastructure; PROD
executors are inactive and the DEV release/deploy dependency requires develop's
inactive infrastructure gate. A green main deployment pipeline is **not** claimed.
The separate exact branch/Environment/OIDC guards also remain unchanged. No
publication, workflow dispatch, main/develop remote change or AWS mutation was
performed by the documentation closure.
