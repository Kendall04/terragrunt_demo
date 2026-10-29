# Portfolio and native DEV operations

Use the [native DEV lifecycle](native-dev-lifecycle.md): network, NAT HA, data,
platform, apps, edge; DOWN reverses dependencies. E16 is retired. The existing
operator, S3 backends/versioning/locks, E2 and E13 remain. Every native saved plan
requires review and separate explicit approval. The guide covers network-only
retirement; the records below are dated history, not a new AWS inventory.

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
