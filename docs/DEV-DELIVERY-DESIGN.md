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
the complete successful DEV receipt. The successful check links directly to its
artifact ID, producing run, attempt and ZIP digest. PROD reads **that artifact**,
not a scan of promotion runs. It checks the actual merge's two parents against
the receipt and the resulting application identity. It never asks for the newest
DEV image. Thus B remains B if DEV subsequently publishes C.
If develop advances **before** the PR merges, its head changes and the old receipt
is invalid: the new contents need validation. Merge commits are required for
promotion. A main-only merge-method rule must enforce `merge` before the evaluator
will approve a PR. Repository merge commits must also be enabled, with no linear
history or merge-queue rule incompatible with this executor. Squash/rebase is
rejected **before merge**, not discovered only after the operator merges.

Keep strict up-to-date branches. After each promotion merge, merge main back into
develop through its normal PR path before the next promotion. This preserves
both histories and makes main an ancestor of the next develop head. A sync with
unchanged application inputs does not deploy.

## Evidence and authority

The [GitHub adapter](../scripts/api_delivery/github.py) checks repository, workflow
ID/path, event, source branch, exact source SHA, run attempt and successful
conclusion. Both push aggregators must pass on the integrated SHA. An older green
attempt cannot override a newer failed/cancelled run. `pull_request_target`
REST `head_sha` may identify the PR head, while `GITHUB_SHA` and
`GITHUB_WORKFLOW_SHA` identify the trusted base code. The reader checks the PR
association and evaluator identity separately. For `workflow_run`, the triggering
DEV execution/attempt is a separate identity from the default-branch evaluator;
it is not the version implicitly selected for promotion.

Artifacts use pinned upload-artifact v4, unique immutable names, a verified ZIP
SHA256 and bounded contents; no arbitrary extraction. Retention is 90 days.
Expired/deleted/missing artifacts block promotion and rollback; there is no
`latest` fallback. These receipts are evidence of trusted GitHub runs, not a
claim that repository administrators cannot delete them. A successful deployment
also archives its receipt in the existing versioned SSE-KMS evidence bucket:

1. DEV writes `api-delivery/dev/operations/<operation>/release.json` with
   `If-None-Match:*`. The returned S3 `VersionId` is reread explicitly. The GitHub
   release artifact carries bucket/key/version/SHA256, source, application,
   OCI digest, ECS revision and per-task/client SQL+KMS health results.
2. The PR evaluator uploads `promotion-record-<attempt>` and downloads it by ID
   before setting the check green. `external_id` encodes the artifact locator;
   `details_url` opens that artifact. A changed PR or missing upload fails the gate.
3. PROD follows the check completed before the merge. It verifies artifact
   metadata, ZIP bytes, producing workflow/event/attempt, PR and actual parents.
   With its own role it reads the exact DEV S3 version, compares the full manifest
   and its hash, and retrieves the ECR OCI manifest to verify its digest. No ECS
   registration or traffic mutation precedes those checks. E2 acquisition is
   coordination only; a failed preflight releases an untouched owner as FAILURE.
4. PROD records the final main SHA, deployment result and the originating
   check/artifact/run/attempt/digest locator in its own versioned manifest.

This installation contract requires a **shared immutable ECR repository in the
same account/region**. DEV may push; PROD and its execution role may only pull/read.
There is no admitted cross-registry copier. PROD's DEV-evidence permission is only
`GetObjectVersion` on the DEV release-manifest prefix, plus CMK decrypt through
S3 for those objects. It cannot list DEV journals, read secrets, write DEV evidence
or inspect unrelated prefixes. Release manifests disable S3 Bucket Keys so their
KMS encryption context remains object-scoped. Bucket/key policies must match.

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
PassRole. `RegisterTaskDefinition` is scoped to the two environment task families;
`DescribeTaskDefinition` requires `Resource:*` and is region-scoped. Response-only
`requiresAttributes` and `compatibilities` metadata are validated separately from
the exact requested `requiresCompatibilities=[FARGATE]`, image, roles, secret and
container configuration.

For E2, a prefix-scoped `ListBucket` request (`Prefix=exact terminal key`,
`MaxKeys=1`) establishes whether the terminal exists. Only an authorized empty
listing is absence. Existing terminals are read and verified normally; a 403 on
either request remains a denial. No broad bucket listing or 403-to-404 conversion
is used. Conditional-write bucket barriers and the existing E2 algorithm remain.

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

The first automatic release cannot silently drain an unqualified native blue.
The version-pinned installation binding must include `native_baseline`: a reviewed
`API_RECOVERY_TARGET_V1` with `kind=native-admission`, environment, source/application,
OCI digest, exact ECS revision/color, `validated-v2` and the current SQL/TLS
compatibility identifier. Before any switch, the executor verifies ECR, renders
and compares the complete task definition, checks the existing task cohort and
client SQL/KMS readiness. An incompatible legacy native definition blocks until
a compatible baseline has been qualified in a separately authorized operation.
This creates a **new admission of observed state**, not a fabricated historical
workflow receipt. Its reference is saved as `previous` in the first automatic
release, so that release's manual rollback can recover it. After a rollback, the
same readiness gates must pass again with new tasks. A truly empty environment
requires both colors at zero desired/running/pending and no conflicting history.

Compensation uses the old observed revision and replica count, not the new desired
count. Blue=1 can therefore recover from a failed green=2 promotion. Lost ACKs on
compensating writes are settled by rereading both routes; they never justify a
blind retry or early drain. Unknown effects retain E2 for explicit reconciliation.

## Activation checklist — separate reviewed operation

1. Review/merge this code and install the trusted promotion evaluator on main.
   Bootstrap is a governance-only integration before its new required rule exists;
   do not claim the rule is already protecting main or bypass an installed rule.
2. With that governance-only merge complete, install the main-only promotion
   required check **and merge-only PR overlay** from
   [permissions.py](../scripts/api_delivery/permissions.py), preserving every other
   PR parameter, existing strict rules and develop's rules. The evaluator's own
   installation merge must precede the new required check; no bypass is needed.
   Verify rejection of wrong-source, pending, failed and changed PRs. Check the
   effective merge methods permit only normal merge on main. Read back both rules
   and test their behavior before enabling automatic delivery.
3. Authenticate actual DEV and PROD SQL/TLS, secret metadata/version, ECS roles,
   services, listener/candidate rules, client route and repository. PROD SQL/DNS,
   CA trust and runtime bindings are **not established by this change**. Admit the
   existing native blue explicitly or demonstrate the environment is empty.
4. Review/install the dedicated OIDC roles, bucket/key permissions and policies,
   environment branch restrictions and version-pinned public bindings. Initialize
   missing E2 heads only through the existing administrative procedure. Verify
   other writers and any old cleanup timer cannot compete. Validate the exact-key
   E2 listing protocol, task-family registration and describe permissions with real
   AWS responses. Verify shared ECR pull permissions, version retention, object-level
   CMK context and PROD's restricted DEV manifest read in IAM and resource policies.
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

The reusable executor classifies application changes **before** taking an
environment concurrency slot. With A running and B pending, docs-only C never
enters that group, cannot cancel B and cannot build. Protected-branch CI push
groups include the SHA, so C does not cancel B's mandatory qualification either;
PR CI still supersedes obsolete PR runs. Under E2, before publishing/registering,
the executor verifies that the request's application identity is still desired on
the protected branch. A retry of old B after C changed/deployed the application
returns `superseded` without mutating ECS or publishing a new image. A docs-only
descendant of B does not make B stale. PROD compares against main, never develop.

GitHub still may coalesce multiple pending **application-changing** runs. This is
latest-desired-version delivery, not a promise to deploy every intermediate commit.
A skipped/cancelled version cannot promote without its own healthy DEV evidence.
The evidence window is bounded, AWS route changes are not transactional, and an
uncertain owner may need supervised reconciliation.

## Review regressions

At reviewed SHA `1661c9c`, the REST PR-head example was rejected as a wrong base;
normal ECS metadata was rejected; old capacity 1 versus new capacity 2 blocked
compensation; E2 had no permission/protocol proving missing terminals; and the
effective main rules allowed merge/squash/rebase. These are reproduced and covered
by [wire/algorithm regressions](../scripts/tests/api_delivery/test_review_regressions.py).
The direct-reader tests keep B after a later DEV C, require revalidation if C enters
before merge, and use a main merge SHA distinct from the DEV source. No test replaces
the artifact reader with a preselected receipt. The additional scope test uses a
real temporary Git history; AWS and REST transports remain offline fixtures.

Primary platform contracts:
[trusted PR events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[immutable workflow artifacts](https://github.com/actions/upload-artifact),
[custom OIDC subjects](https://docs.github.com/en/actions/reference/security/oidc),
[GitHub concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[S3 absence versus denial](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html),
[ECS authorization table](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html).
