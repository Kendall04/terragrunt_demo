# Automatic API delivery

This is the replacement API delivery implementation. It is **not activated in
GitHub or AWS by this change**. The old manual-DEV design is superseded by the
owner's develop/main promotion flow. Terraform and the public CloudFront DEMO
remain independent.

## Flow and immutable promotion

```mermaid
flowchart LR
  F[Feature PR to develop] --> CI[Existing CI and CD Safety]
  CI --> D[Merge into develop]
  D --> V[Wait for both push validations on exact merge SHA]
  V --> B[Build common Linux image once and publish ECR digest]
  B --> DEV[Deploy inactive DEV color and verify every task]
  DEV --> R[Healthy DEV receipt with application identity and digest]
  R --> PR[develop to main PR]
  PR --> G[API Promotion Validation on exact PR head]
  G --> S[Immutable PR receipt: head + base + application + DEV digest]
  S --> M[Merge commit on main]
  M --> PROD[Same executor in PROD using that receipt's digest]
  PROD --> RB[Separate manual environment rollback]
```

A merge is the deployment decision. No release form accepts a commit, tag, digest,
command or endpoint. The only manual action is rollback, whose sole input is
the environment; the executor resolves its previous healthy compatible release.

- [api-delivery.yml](../.github/workflows/api-delivery.yml): push on develop/main,
  plus environment-only rollback dispatch. No PR trigger.
- [api-execute.yml](../.github/workflows/api-execute.yml): the sole reusable AWS
  job; environment-specific configuration and OIDC. Both environments execute
  [the same algorithm](../scripts/api_delivery/executor.py).
- [api-promotion.yml](../.github/workflows/api-promotion.yml): trusted default
  branch code on PR-to-main events and after a successful DEV run. No OIDC or
  AWS credentials. It fetches PR objects but never checks out or executes PR code.
  It publishes `API Promotion Validation` on the exact PR head; incomplete,
  cancelled or failed evaluation cannot supply a successful check.

[Application identity](../scripts/api_delivery/model.py) hashes Git modes,
paths and blobs of the build context, API/tests, SqlBackup projects and build
configuration. Documentation is excluded. Different merge SHAs with identical
application inputs identify the same version; changed runtime/tests/Dockerfile
inputs require fresh DEV success. Docs-only pushes do not acquire AWS credentials,
build or move traffic.

The PR receipt includes PR number, head SHA, base SHA, application identity and
the complete successful DEV receipt. PROD checks the actual merge's two parents
against that receipt and the resulting application identity. It never asks for
the newest DEV image. Thus B remains B if DEV subsequently publishes C.
If develop advances **before** the PR merges, its head changes and the old receipt
is invalid: the new contents need validation. Merge commits are required for
promotion; squash/rebase promotion is rejected.

Keep strict up-to-date branches. After each promotion merge, merge main back into
develop through its normal PR path before the next promotion. This preserves
both histories and makes main an ancestor of the next develop head. A sync with
unchanged application inputs does not deploy.

## Evidence and authority

The [GitHub adapter](../scripts/api_delivery/github.py) checks repository, workflow
ID/path, event, source branch, exact source SHA, run attempt and successful
conclusion. Both push aggregators must pass on the integrated SHA. An older green
attempt cannot override a newer failed/cancelled run.

Artifacts use pinned upload-artifact v4, unique immutable names, a verified ZIP
SHA256 and bounded contents; no arbitrary extraction. Retention is 90 days.
Expired/deleted/missing artifacts block promotion and rollback; there is no
`latest` fallback. These receipts are evidence of trusted GitHub runs, not a
claim that repository administrators cannot delete them. A successful deployment
also archives its receipt in the existing versioned SSE-KMS evidence bucket.

PRs retain existing CI authority only. The promotion evaluator can write checks
and artifacts but has no AWS identity. It cannot deploy. The required promotion
rule must be installed **only on main**, in addition to CI Validation and CD Safety
Validation, without a bypass or extra human approval requirement.

The actual repository OIDC subject uses `repo,context,job_workflow_ref`.
[Offline IAM definitions](../scripts/api_delivery/permissions.py) therefore bind
each dedicated role to its `api-dev` or `api-prod` environment and the reusable
workflow on develop or main respectively. Environment branch policies must agree.
PROD has no ECR push permission. This does not reuse or widen the historical
E1 request roles. Policy definitions include conditional S3 writes and scoped
PassRole. Registration/list/describe APIs needing `Resource:*` are explicitly
region-scoped; this is not resource isolation for those APIs.

## Executor and failure handling

The renderer, common-image entrypoint, two-container task, loopback probe and
existing per-task readiness gate are reused. Ordinary DEV and PROD require
`validated-v2`, a versioned environment-authorized runtime secret, public trust
manifest, disabled startup migrations and the same digest on API/probe. The
deployment role never reads secret values or starts migrations.

Bindings are independently published public `API_INSTALLATION_V1` objects:
two existing E1 color bindings, SQL identity/trust, secret VersionId, immutable ECR
repository, client HTTPS URL, replica/drain bounds, storage CMKs and an explicitly
reviewed schema/TLS compatibility identity. A protected GitHub environment pins
the S3 bucket/key/VersionId/SHA256/account/region. This is not caller-supplied
authorization. Missing PROD bindings fail closed; fixtures are not deployed ARNs.

GitHub concurrency uses the existing per-environment application group. The
executor additionally acquires the existing non-expiring E2 application head:
delivery, rollback and lifecycle must share that same head. No new lock service,
lease takeover or forced unlock is introduced. Manual/native mutation tools must
honor the same exclusion before activation.

Before traffic: inactive color must be quiescent; exact task definition readback,
frozen cohort, digest, ENIs, healthy targets and successful per-task probe are
required. The client `/ready` route proves its database and KMS health checks.
After switching, both listener and candidate rule are reread, then the client
route is checked. After the bounded drain delay the routes/cohort/targets are
verified again before reducing old capacity. No recurring cleanup timer is used.

| Failure | Behavior |
| --- | --- |
| Before switch | Preserve active traffic/capacity; retain uncertain operation ownership and attempts. |
| Listener changed, candidate write failed (including lost ACK) | Read both routes; prove old revision/capacity is healthy; restore listener, reread, restore candidate if needed, reread both and check client readiness. Keep both capacities and hold for reconciliation. |
| Unknown/foreign route or failed compensation | Do not overwrite unexplained state or drain either color. Retain hold. |
| Drain may have started | Keep new traffic; never switch back to potentially drained old tasks automatically. Reconcile explicitly. |
| Worker cancelled, evidence write lost or success upload fails | No new mutation on rerun and no deadline-based release. Inspect existing E2/immutable evidence. |

Manual rollback resolves the latest healthy environment deployment and an earlier
distinct compatible digest, verifies current runtime agrees, and redeploys it
through the same candidate/readiness/promotion algorithm. Compatibility is an
administrative schema/TLS/runtime assertion, backed by a new real readiness test;
it is not inferred from image age. No database reversal is attempted.

## Activation checklist — separate reviewed operation

1. Review/merge this code and install the trusted promotion evaluator on main.
   Bootstrap is a governance-only integration before its new required rule exists;
   do not claim the rule is already protecting main or bypass an installed rule.
2. Install the main-only promotion required check, preserve existing strict rules,
   and verify rejection of wrong-source, pending, failed and changed PRs. Check the
   configured merge methods permit normal merge and use it for promotions.
3. Authenticate actual DEV and PROD SQL/TLS, secret metadata/version, ECS roles,
   services, listener/candidate rules, client route and repository. PROD SQL/DNS,
   CA trust and runtime bindings are **not established by this change**.
4. Review/install the dedicated OIDC roles, bucket/key permissions and policies,
   environment branch restrictions and version-pinned public bindings. Initialize
   missing E2 heads only through the existing administrative procedure. Verify
   other writers and any old cleanup timer cannot compete.
5. Keep historical `cd.yml` and `cd-terragrunt.yml` disabled. Their generated
   request jobs remain byte-identical/fail-closed. The new path verifies those
   settings before mutation and does not invoke gateways or E1 workers.
6. Set the separately reviewed environment variables and
   `API_DELIVERY_ENABLED=true`. No setting was changed in this implementation.
   A first genuine application merge to develop starts DEV automatically; enabling
   a variable alone is not a deployment or approval of an arbitrary old commit.
7. Observe a real DEV deployment, PR approval, merge and same-digest PROD deployment;
   prove TLS/SQL/KMS, client route, compensation, rollback and permissions against
   the installed graph within an approved budget/window.

No permission, ruleset, environment, AWS resource or traffic mutation is included
in the implementation PR. The native lab's earlier success is not evidence that
this new automatic route has executed.

## Validation and limits

```sh
python3 -I -B -m unittest discover -s scripts/tests/api_delivery -v
python3 -I -B scripts/tests/final_acceptance/gate.py --report-dir /tmp/api-cd-acceptance
```

Repo Hygiene runs the focused suite under the required CI aggregator. The final
E1 gate admits only the exact new workflow definitions and still rejects arbitrary
credential-acquisition workflows; historical retirement checks remain intact.

Tests exercise B/C promotion, differing merge/source SHAs, changed PRs, absent
receipts, failed/cancelled checks, docs-only no-ops, environment isolation,
rollback compatibility, non-expiring exclusion and failures around both routing
writes and drain. These are offline tests, **not AWS deployment evidence**.

GitHub may replace an older pending run within a concurrency group; no design here
promises every queued intermediate version deploys. A skipped/cancelled version
cannot be promoted unless its exact application identity has a healthy DEV receipt.
The evidence window is bounded, AWS route changes are not transactional, and an
uncertain owner may need supervised reconciliation.

Primary platform contracts:
[trusted PR events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[immutable workflow artifacts](https://github.com/actions/upload-artifact),
[custom OIDC subjects](https://docs.github.com/en/actions/reference/security/oidc).
