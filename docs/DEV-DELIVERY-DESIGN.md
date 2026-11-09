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
  branch caller on PR-to-main events and after a successful DEV run. Its reusable
  [api-evaluate.yml](../.github/workflows/api-evaluate.yml) signs with Sigstore OIDC,
  with no AWS role or deployment environment. It fetches PR objects but never checks out or executes PR code.
  It publishes `API Promotion Validation` on the exact PR head; incomplete,
  cancelled or failed evaluation cannot supply a successful check.

[Application identity](../scripts/api_delivery/model.py) hashes Git modes,
paths and blobs of the build context, API/tests, SqlBackup projects and build
configuration. Documentation is excluded. Different merge SHAs with identical
application inputs identify the same content. A release also belongs to a
continuous first-parent application history: B → C → B′ is a new promotion even
when B and B′ have identical files. Changed runtime/tests/Dockerfile inputs require
fresh DEV success. Docs-only pushes do not acquire AWS credentials,
build or move traffic.

The PR receipt includes PR number, head SHA, base SHA, application identity and
the complete successful DEV receipt and its exact signed attestation locator. The
successful check carries a compact subject/statement hash and producer identity.
PROD reads **that attestation from GitHub**,
not a scan of promotion runs. It checks the actual merge's two parents against
the receipt and the resulting application identity. It never asks for the newest
DEV image. Thus B remains B if DEV subsequently publishes C.
If develop advances **before** the PR merges, its head changes and the old receipt
is invalid: the new contents need validation. Merge commits are required for
promotion. A main-only merge-method rule must enforce `merge` before the evaluator
will approve a PR. Repository merge commits must also be enabled, with no linear
history or merge-queue rule incompatible with this executor. Squash/rebase is
rejected **before merge**, not discovered only after the operator merges.

The repository's optional `allow_merge_commit` field is not assumed visible to
the read-only job token. The job requires effective merge-only branch rules and
rejects an explicitly false setting. Installation separately requires an owner
readback with `GitHub().require_merge_policy(administrator=True)`; a missing field
fails that administrative check. CI reports field visibility using its existing
`contents:read` token; no administration permission is added to any job.

Keep strict up-to-date branches. After each promotion merge, merge main back into
develop through its normal PR path before the next promotion. This preserves
both histories and makes main an ancestor of the next develop head. A sync with
unchanged application inputs does not deploy.

## Evidence and authority

The [GitHub adapter](../scripts/api_delivery/github.py) checks repository, workflow
ID/path, event, source branch, exact source SHA, run attempt and successful
conclusion. Both push aggregators must pass on the integrated SHA. During source
qualification, an older green CI attempt cannot replace a newer failed/cancelled
run. A completed promotion approval is different: its sealed attempt is fetched
with `/actions/runs/<run>/attempts/<attempt>`, not the latest run endpoint. Thus
run 80/attempt 3 cannot invalidate or replace the approved attestation from attempt 2.
The finalizer still reads its current in-progress run and demands its own attempt.
`pull_request_target`
REST `head_sha` may identify the PR head, while `GITHUB_SHA` and
`GITHUB_WORKFLOW_SHA` identify the trusted base code. The reader checks the PR
association and evaluator identity separately. For `workflow_run`, the triggering
DEV execution/attempt is a separate identity from the default-branch evaluator;
it is not the version implicitly selected for promotion.

Receipts use GitHub repository attestations with a custom in-toto predicate,
following the [isolated prototype](https://github.com/Kendall04/terragrunt_demo/commit/6c2fe3fed15d932ae090a1922976dc15542ddc78).
Actions artifacts remain optional diagnostics; their deletion cannot change the
approved release. Attestations can also be deleted by repository administrators:
missing or contradictory evidence blocks delivery, never selects a substitute.

1. DEV writes `api-delivery/dev/operations/<operation>/release.json` conditionally
   with SSE-KMS and rereads its returned VersionId. It contains the original
   producer, E2 request hash, exact source/application, OCI digest, ECS revision,
   per-task and client SQL/KMS health and a version/hash `configuration_ref`.
2. `actions/attest` signs a closed public predicate carrying that record and
   `bucket/key/version/sha256`. A deterministic slot derived from repository,
   environment and run ID locates it. History discovery needs no prior receipt
   ID, attempt, VersionId or hash. The verified signing certificate identifies
   the attempt; REST checks independently bind it to the original execution.
3. The evaluator seals the DEV statement hash in a promotion attestation on a
   separate run/attempt slot. The predicate binds its check ID, PR/head/base and
   application. `external_id` has only `v,s,h,r,a,w` (under GitHub's 255-byte
   limit). Before green it rereads that field and verifies the **published**
   attestation from GitHub. `details_url` is informational; GitHub rewrites it.
4. PROD follows the check completed before merge, validates the exact attempt,
   trusted caller/reusable signer, PR, parents and application. With its own role
   it verifies the exact DEV S3 version/bytes and ECR manifest digest before ECS.
   It records the final main SHA and the approval locator in its own manifest.

The [repository signer policy](../scripts/api_delivery/receipt-policy.json) fixes
repository/owner numeric IDs, caller paths, reusable signer paths, events and
protected refs. The [verifier](../scripts/api_delivery/receipts.py) uses `gh
attestation verify` for Sigstore cryptography and explicit checks of certificate
claims, including invocation run/attempt. Another workflow's valid signature is
not an authorized signature. Runtime checks remain active under `python -O`.
`pull_request_target` REST head is the PR identity, not necessarily the trusted
base source in the signing certificate. For `workflow_run`, the triggering DEV
attempt and default-branch evaluator are verified separately.

Public predicates allow release identities, hashes, ARNs, readiness booleans,
versioned evidence/configuration references, the bounded previous recovery target
and promotion/check metadata. They exclude task definitions, configuration
contents, secret values, credentials, logs, database records and arbitrary extra
fields. GitHub attestations for this public repository are public: inspect this
metadata policy before installation. The protected checkout supplies the signer
policy, never PR-controlled code.

### Publication-only reconciliation

A rerun of an already terminal operation cannot build or redeploy. It derives
its operation UUID and exact S3 release key from the same original run. Without
any prior receipt, VersionId or hash, it enumerates **all versions of that exact
key**, rejects delete markers/multiple versions, reads the sole version and
verifies encryption, canonical bytes, original producer and E2 request hash.
The real E2 terminal must be SUCCESS and its matching head RELEASED; ACTIVE,
displaced, uncertain or contradictory state requires separate reconciliation.
SUCCESS with no release manifest (the superseded no-op path) is not deployment
proof. Current ECS revision/configuration, task health and client readiness are
also reread before publication. This path has no build, ECR write, ECS mutation,
S3 write or E2 acquisition/release.

The recovering attempt signs as **itself**, preserving the original deployment
producer inside the record. A failed original publisher cannot be silently
replaced by a green attempt: only an authenticated recovery with identical
record bytes can settle that gap. Original run/attempt execution evidence is
required even if it failed after persisting the manifest. Missing execution
history stops recovery. A cancelled run
is recoverable only when its exact deployment step completed successfully;
cancelled/failed deployment steps in a cancelled run remain blocked.

Receipt discovery precedes E2 acquisition. Thus C finding B's publication gap
does not replace B's released head or consume C's operation with a FAILURE
terminal: B can republish its original evidence, then C can retry once. Source
eligibility is checked before discovery and again under E2; current ECS and its
immutable configuration are still admitted under E2 before any build or mutation.

The environment role needs reviewed `s3:ListBucketVersions` limited to its own
operation release keys and max-keys <=100, in addition to existing exact-version
reads. [Permission definitions](../scripts/api_delivery/permissions.py) describe
this change; they do not install it. PROD does not gain listing of DEV evidence.

Missing publication is fail-closed. A no-receipt run can be skipped only when
all its attempts are independently proven to have skipped the delivery runner
(inhibition or scope classification), or every failed attempt proves `prepare`
failed while both credentials and deployment steps were explicitly skipped.
Missing, duplicate, contradictory or potentially effectful steps block admission.
The executor can also pass a queued run whose jobs have no delivery runner,
checking every earlier attempt; the promotion evaluator keeps its stricter pending
policy. A queued retry cannot hide an earlier deployment. An operation superseded
under E2 emits an authenticated no-deployment outcome. A failed/cancelled execution with missing
receipt is not treated as a documentation change.

This installation contract requires a **shared immutable ECR repository in the
same account/region**. DEV may push; PROD and its execution role may only pull/read.
There is no admitted cross-registry copier. PROD's DEV-evidence permission is only
`GetObjectVersion` on the DEV release-manifest prefix, plus CMK decrypt through
S3 for those objects. It cannot list DEV journals, read secrets, write DEV evidence
or inspect unrelated prefixes. Release manifests disable S3 Bucket Keys so their
KMS encryption context remains object-scoped. Bucket/key policies must match.

PRs retain existing CI authority only. The promotion evaluator can write checks
and attestations but has no AWS identity. Its minimal permissions are
contents/actions/pull-requests read, checks/attestations/id-token write. The
execution signer needs attestations write plus its existing deployment permissions.
The promotion evaluator cannot deploy. The required promotion
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

GitHub concurrency uses the existing per-environment application group with
`queue: max` and `cancel-in-progress: false`. Up to 100 pending jobs wait in arrival
order; a later old retry cannot replace the current pending deployment. The
executor additionally acquires the existing non-expiring E2 application head:
delivery, rollback and lifecycle must share that same head. No new lock service,
lease takeover or forced unlock is introduced. Manual/native mutation tools must
honor the same exclusion before activation.

Before traffic: inactive color must be quiescent; exact task definition readback,
frozen cohort, digest, ENIs, healthy targets and successful per-task probe are
required. The client `/ready` route proves its database and KMS health checks.
After switching, both listener and candidate rule are reread, then the client
route is checked. After the bounded drain delay the routes/cohort/targets and the
real client `/ready` SQL+KMS response are verified again, followed by another route
readback, before reducing old capacity. Loss of SQL/KMS during the wait therefore
enters compensation while blue remains available. No recurring cleanup timer is used.

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
compatibility identifier and `configuration_ref`. That reference identifies a
create-only `API_TASK_CONFIGURATION_V1` object with environment, color, image,
revision and exact verified task JSON at
`api-delivery/<env>/operations/<id>/<sequence>-task-configuration.json`.
Before any switch, the executor verifies ECR, reads the exact configuration
version/hash/CMK and compares the complete task definition, checks the existing task cohort and
client SQL/KMS readiness. An incompatible legacy native definition blocks until
a compatible baseline has been qualified in a separately authorized operation.
This creates a **new admission of observed state**, not a fabricated historical
workflow receipt. Its reference is saved as `previous` in the first automatic
release, so that release's manual rollback can recover it. After a rollback, the
same readiness gates must pass again with new tasks. A truly empty environment
requires both colors at zero desired/running/pending and no conflicting history.

Automatic releases seal their configuration reference in the immutable release
manifest; native admission requires an independently reviewed reference in the
installation binding. Missing historical configuration blocks admission rather
than falling back to today's renderer. Blue may still use secret v1 and trust
manifest v1 while green is rendered with v2. The archived task contains only
secret references and public trust, never secret values. Its roles, environment,
digest, strict profile and full AWS readback must match, and current health plus
the reviewed compatibility identity remain mandatory. A snapshot alone does not
prove old credentials or CA trust still work. Existing environment-scoped journal
read permission covers these objects; PROD receives no additional access to DEV
configuration objects.

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
   effective merge methods permit only normal merge on main, and run the owner
   preflight above to confirm repository merge commits are enabled. Read back both rules
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
6. Validate the signed-receipt installation boundaries below, then set the separately
   reviewed environment variables and
   `API_DELIVERY_ENABLED=true`. No setting was changed in this implementation.
   A first genuine application merge to develop starts DEV automatically; enabling
   a variable alone is not a deployment or approval of an arbitrary old commit.
7. Observe a real DEV deployment, PR approval, merge and same-digest PROD deployment;
   prove TLS/SQL/KMS, client route, compensation, rollback and permissions against
   the installed graph within an approved budget/window.

No permission, ruleset, environment, AWS resource or traffic mutation is included
in the implementation PR. The native lab's earlier success is not evidence that
this new automatic route has executed.

### Platform evidence and activation boundary

[Run 42550509226](https://github.com/Kendall04/terragrunt_demo/actions/runs/42550509226)
closed the artifact-retention diagnosis: rerunning lost the original artifact.
The signed-receipt prototype subsequently verified original DEV and approval
attestations after independent failed reruns, B preserved after simulated merge
and later C, and rejection of an authentic foreign signer and altered content.
[Consumer result](https://github.com/Kendall04/terragrunt_demo/actions/runs/42553286137)
used fictitious payloads; it did not deploy or read AWS.

Before activation, install the trusted evaluator on main, then configure the
main-only required check and merge policy. Verify GitHub's actual certificates
for both PR-target and workflow-run callers with the new reusable evaluator;
the isolated prototype exercised push identities, not those events. Verify the
new scoped version-list permission and real E2/S3 publication recovery in an
isolated AWS installation. No ruleset, role, environment or activation variable
is changed by this PR. Existing bootstrap and rollback requirements remain.

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
the protected branch and that every subsequent first-parent commit preserved it.
A retry of old B after C changed/deployed the application
returns `superseded` without mutating ECS or publishing a new image. A docs-only
descendant of B does not make B stale; B → C → B′ does. The DEV receipt used by
promotion admission must also belong to that uninterrupted application history.
The history walk is bounded to 1001 commits and fails closed if it cannot find the
source. PROD compares against main, never develop.

Deployment history now authenticates the original signed producer, even after
failed/cancelled reruns and disappearance of every diagnostic ZIP. Active
admission still reads the original S3 VersionId/hash and live revision,
configuration, compatibility and health. The executor consumes only its first
authenticated current release; rollback uses its sealed `previous` target. It
does not inspect unrelated old runs after finding the current release. The PR
evaluator retains the history search and first-parent lineage check.

[Signed-receipt regressions](../scripts/tests/api_delivery/test_signed_receipts.py)
exercise automatic discovery, published-attestation readback, compact check
readback, real Git B/C/B-prime histories, optimized Python, actual E2 terminal and
S3 journal formats, and recovery with zero prior receipt/version/hash inputs.
Transport fixtures are explicitly separate from the real prototype evidence.

The native queue preserves pending runs rather than coalescing them. This remains
latest-desired-version delivery, not a promise to deploy every intermediate commit:
obsolete queued runs exit under E2 without replacing the current desired version.
Runs beyond GitHub's 100-entry queue limit are canceled by GitHub and require
operator investigation; this is not an unbounded delivery guarantee.
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
the signed-receipt reader with a preselected receipt. The additional scope test uses a
real temporary Git history; AWS and REST transports remain offline fixtures.

The follow-up at `50261ef` reproduced root-path rejection in `GitHub.raw`, loss of
a sealed attempt after a rerun, pending C displaced by an old B retry, B → C → B′
accepted as old B, SQL failure detected only after draining blue, and v1 rejected
against the new v2 binding. [Follow-up regressions](../scripts/tests/api_delivery/test_followup_regressions.py)
use real `get/raw` with only the gh subprocess doubled, real Git merge histories,
the real E2/executor and HTTP/S3 response fixtures. No cloud failure is injected.

Pinned actionlint 1.7.12 does not parse GitHub's documented `concurrency.queue`.
[The narrow compatibility bridge](../.github/scripts/ci/lint-actions.py) validates
exactly `queue:max` plus cancellation disabled in the closed executor, removes
only that key in a temporary copy, then runs all unchanged actionlint checks on
every workflow. Other fields and diagnostics are preserved. No tool pin or
security check is relaxed; remove the bridge when an admitted upstream version
supports the key. Scheduler behavior still needs a controlled activation trial.

Primary platform contracts:
[trusted PR events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[immutable workflow artifacts](https://github.com/actions/upload-artifact),
[custom OIDC subjects](https://docs.github.com/en/actions/reference/security/oidc),
[GitHub concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[attempt-specific run API](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt),
[S3 absence versus denial](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html),
[ECS authorization table](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html).
