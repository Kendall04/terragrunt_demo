# Automatic API delivery: one executor, two environments

**DEV implemented and running. PROD disabled and unqualified.** First automatic
DEV delivery: [run 42751096835](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835).
CA-only TLS delivery: [run 42761946295/2](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2).
Terraform and CloudFront retain separate lifecycles. The original manual bootstrap
is not counted as an automatic deployment. The approved administrative handover
fenced legacy writers; historical E2 remains intact and is not delivery authority.
Sentinel is not a dependency of this executor.

## Design decision

The previous design coupled every deployment to E2 ownership, signed receipts,
historical attempts and publication recovery. Those mechanisms did not make the
first automatic deployment operable: interrupted E2 ownership has no supported
administrative release. We replace that dependency with a GitHub environment
queue, a small versioned operational record, and an explicit administrator
handover that prevents competing writers. We do **not** reset the existing E2.

```mermaid
flowchart LR
  F[Feature PR + required CI] --> D[Merge develop]
  D --> S{Application changed?}
  S -->|No| N[No AWS identity or build]
  S -->|Yes| Q[DEV queue + exact-SHA CI]
  Q --> B[Build once + immutable ECR digest]
  B --> X[Inactive color + task SQL/KMS readiness]
  X --> T[ALB switch + client health + drain]
  T --> R[Versioned S3 record + GitHub Deployment ID]
  R --> P[develop to main PR: approve exact release ID]
  P --> M[Merge commit + exact-SHA CI]
  M --> V[PROD: pinned ID + exact S3 version/hash + ECR digest]
  V --> X2[Same executor with PROD configuration; no build]
```

| Keep | Replace or retire |
| --- | --- |
| Required CI/Safety, strict branch updates, no bypass | One separate activation flag per environment |
| Common blue/green algorithm and real SQL/KMS readiness | E2 mutation grants → GitHub queue plus fenced external writers |
| Exact digest, versioned secrets, `validated-v2`, two containers | Attestation/artifact discovery → GitHub Deployments metadata index |
| Immutable S3 configuration and release bytes | Historical attempt reconstruction → one explicit producer attempt |
| Previous compatible image and live recovery checks | Permanent ownership hold → observable state and explicit reconciliation |

The four [workflow files](../.github/workflows/api-delivery.yml) are two callers
and two reusable jobs, not four competing delivery paths. The
[executor](../scripts/api_delivery/executor.py) is shared by DEV, PROD and rollback.
[GitHub](../scripts/api_delivery/github.py) handles the index/check;
[AWS](../scripts/api_delivery/aws.py) handles ECS/ALB/ECR;
[state](../scripts/api_delivery/state.py) handles operational recovery.

## Normal operation and promotion

`API_DEV_DELIVERY_ENABLED` and `API_PROD_DELIVERY_ENABLED` default to disabled.
The old shared `API_DELIVERY_ENABLED` is ignored by this implementation. A
docs-only push exits before credentials or the environment queue. CI and CD
Safety must succeed on the exact integrated SHA before AWS credentials.

GitHub serializes each environment with `cancel-in-progress: false` and
`queue: max`. This is the documented [multi-pending queue](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
not the single-pending queue that can discard C when old B is retried. Queue
capacity is finite; rejected runs are visible failures. Once admitted, an old
application lineage is skipped before build. Documentation descendants preserve
eligibility; B → C → B′ does not revive the original B. A running deployment is
not cancelled midway when a newer merge arrives.

Successful delivery writes an immutable SSE-KMS S3 manifest (conditional create,
exact VersionId and SHA-256). The subsequent step creates a
[GitHub Deployment](https://docs.github.com/en/rest/deployments/deployments)
with task `api-release` and a
[success status](https://docs.github.com/en/rest/deployments/statuses).
The payload contains repository/environment, source/application identity, OCI
digest, ECS revision, health result, configuration reference, previous compatible
target, producer run/attempt and exact S3 reference. No secret values, SQL text,
credential material or private logs belong in this public metadata. Artifacts
are diagnostic downloads only; deleting them does not erase a release.

The evaluator runs trusted base code with contents/actions/PR/deployments read
and checks write. It has **no OIDC, AWS credentials or deployment environment**.
It discovers a healthy DEV release matching the PR's application content and
first-parent lineage. `API Promotion Validation.external_id` fixes the PR, base,
application, release ID and evaluator run/attempt; the exact check fixes the head.
The evaluator rereads both the check and release and rechecks the live PR before
success. Presentation URLs are not identity fields.

PROD reads the successful check completed before merge, requires two parents
exactly matching the approved base/head, and fetches that release ID. Its own role
checks the exact S3 version, bytes, encryption and ECR manifest digest before
mutation. If B was approved and C appears after merge, PROD still consumes B.
If C enters the PR before merge, the head/check must be revalidated. Keep strict
branch updates: merge main back into develop through a normal PR after promotion.

This installation expects an explicitly approved **shared ECR repository**;
PROD cannot publish to it. Cross-account registry copy is not implemented. SQL,
secrets, roles and environment configuration remain separate. Future independent
registries need a reviewed digest-preserving copy, not a rebuild.

Trust boundary: repository administrators and protected workflow editors can
change publisher/check logic. The reader checks GitHub Actions identity,
workflow, event, branch, producer SHA/attempt and successful execute step; it
does not claim cryptographic separation between mutually trusted repository
workflows. S3 version/hash and ECR checks independently protect the AWS consumer.
Deleted index entries or missing producer evidence block promotion and can be
republished only through a verified current-state reconciliation. No latest-image
fallback or AWS credentials in PR evaluation are needed.

## Failure, rollback and reconciliation

`api-delivery/<env>/state.json` is versioned SSE-KMS metadata with `HEALTHY`,
`DEPLOYING` or `RECONCILE`, current/previous release and candidate revision.
Conditional `If-Match` detects conflicting writes. This object is **not a lease**:
GitHub serialization and administrative exclusion of other writers are required.
The role cannot create missing state, overwrite operation evidence or write the
handover. Missing/denied state is never interpreted as an empty environment.

Before drain, the executor rereads both ALB routes, exact task cohort and the
client `/ready` response. SQL/KMS failure restores both routes while blue still
has its original capacity. After drain starts it preserves the new color rather
than switching to capacity that may already be gone. `stop` waits for ECS zero
and **empty target groups**, including ALB deregistration delay.

| Situation | Operator action and guarantee |
| --- | --- |
| Healthy S3 release, GitHub publication failed | Retry the original run or dispatch `reconcile`. Verify current revision, exact S3/configuration and current SQL/KMS; republish without build/ECR/ECS mutations. New releases wait for publication. |
| Failed operation, old color still serving | Inspect operation journal and both routes. If the candidate remains running, stop only that positively identified inactive candidate under supervised maintenance, then `reconcile`. It never guesses unknown effects away. |
| Candidate serves after drain, final record missing | `reconcile` accepts only its recorded revision/configuration, both settled routes, zero inactive capacity, exact healthy tasks and fresh client SQL/KMS. It writes a new reconciliation record preserving the original source; no redeploy. |
| Unknown routes, foreign revision or unsettled capacity | Keep activation off, repair the observed state through supervised operation, then rerun reconciliation. No force/reset command. |
| Rollback after completed deployment | Dispatch `rollback` for the environment. Resolve its previous compatible image automatically, validate the current baseline, deploy to inactive color using current approved configuration, then health/switch/drain. No DB rollback or automatic schema migration. |

Commands after installation (select the corresponding protected branch; no SHA
or image inputs):

```sh
gh workflow run api-delivery.yml --ref develop -f environment=dev -f operation=reconcile
gh workflow run api-delivery.yml --ref develop -f environment=dev -f operation=rollback
```

Reconciliation runs in the same environment queue. It changes evidence/state,
not ECS, ECR or ALB. Current source and producer must pass CI even for recovery.
Compatible revision/configuration metadata alone does not prove valid credentials
or certificates: live SQL/KMS readiness is still mandatory.

## Installed DEV boundary and future PROD activation

The DEV handover and native baseline were installed before the first automatic
[DEV run](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835).
The old E2 DEV/application generation 18, operation
`09342d65-e953-4865-b177-6e7bbbaad967`, remains historical ACTIVE. It was not
unlocked: administrative controls fenced the old application writers and the
handover recorded settled effects. Current delivery validates the pinned
`legacy_head`, handover and binding instead of acquiring E2.

`API_HANDOVER_V2` records administrator identity, writer controls, execution
termination and settled-effect evidence. Its exact S3 version/hash and binding
hash are pinned by `API_HANDOVER_REF`. `API_STATE_V2` records subsequent operation
state. A changed legacy head or unknown active revision blocks delivery; do not
reinitialize these installed records or repeat the bootstrap as routine recovery.
[E2-R](../terraform/docs/e2r-owner-recovery.md) still offers no administrative unlock.

The scoped [permission definitions](../scripts/api_delivery/permissions.py) and
protected `api-dev` environment support DEV. Required environment variables are
`API_ACCOUNT_ID`, `API_REGION`, `API_DELIVERY_ROLE_ARN`, `API_BINDING_REF` and
`API_HANDOVER_REF`. Preserve the custom OIDC `job_workflow_ref` subject and
environment claims. GitHub serialization does not replace the administrative
exclusion of Terraform/manual writers.

Readback on 18 November: DEV enabled; PROD disabled. The old evaluator PR #45
was closed as superseded. Current evaluator code is now in main, but **PROD
activation remains separate**: the main-only required promotion check, merge-only
policy, genuine PROD SQL/TLS, roles, resources and live qualification are still
prerequisites. Existing CI/Safety protection must remain intact. Current rules
allow additional merge methods, so the optional evaluator's prerequisite rejection
does not establish a working PROD promotion. No installer or pipeline changes are
part of this documentation update.

## Validation boundary

```sh
python3 -I -B -m unittest discover -s scripts/tests/api_delivery -v
python3 -O -I -B -m unittest discover -s scripts/tests/api_delivery -v
```

Tests exercise real Git histories, GitHub REST readers, CLI/state transitions,
S3 version/hash checks and the common executor with deterministic transports.
They retain readiness, rollback, lost ALB acknowledgements, one-blue/two-green,
old/new secret configuration, metadata and IAM boundaries. Attestation/artifact
and E2-publication permutations were removed with those retired mechanisms;
independent E1/E2/security suites and immutable historical evidence remain.
These tests do not themselves qualify effective AWS permissions or deployment.
The linked DEV runs separately provide actual merge/run, ECR/ECS and health
evidence. PROD remains unqualified; source tests do not change that status.
