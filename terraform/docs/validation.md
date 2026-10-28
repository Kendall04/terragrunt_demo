# Development and validation entry points

> **Current DEV operations (2026-10-28):** use the [native Terraform lifecycle](native-dev-lifecycle.md). E16 execution/session requirements below are historical; independent security and delivery contracts remain.

The WP3C [internal release implementation](e1-internal-release.md) adds hermetic
adapter/authority acceptance and provider-free selective-compute fixtures.
These never constitute live AWS isolation or deployment evidence.

## CURRENT CONTRACT — toolchain and coverage

CI selects Terraform 1.13.4, Terragrunt 0.93.3 and exact .NET SDK 10.0.402.
All 14 TARGET environment/layer roots have tracked locks; the neutral security
root now has an AWS-only lock. They retain AWS 5.100.0 (~>5.50); TARGET locks
also retain TLS 4.3.0. [E14-B](e14b-toolchain-reproducibility.md) records verified
standalone tool checksums, immutable CI action identities, platform/hash coverage
and the intentional update procedure. [E14-A](e14-container-hardening.md) retains
verified .NET 10 Linux/amd64 image digests and UID 1654. Runner inputs, jq, BuildKit,
NuGet and protected runtime installation evidence remain reproducibility gaps.

These are current selections, not a guarantee other versions work or a requirement
to install/update tools automatically. Scripts assume Bash/Linux-style tooling;
the workspace may be Windows. Do not infer local support from CI configuration.

Evidence: [static CI](../../.github/workflows/ci-terragrunt.yml),
[hygiene](../../.github/workflows/ci-repo-hygiene.yml),
[app CI](../../.github/workflows/ci-dotnet.yml),
[Dockerfile](../../demo-api/Dockerfile), [locks/live](../live).

## Command effect classification

Examples use repository-root paths. Inspect flags, environment and dependencies
before execution. A command listed here is not blanket permission to run it.

| Class | Entry points | Effects / limitations |
| --- | --- | --- |
| Local/static inspection | git diff/status; rg; read tracked files | No build, backend or AWS operation |
| Local/static checks with existing tools | bash -n scripts/*.sh; bash -n .github/scripts/cd/*.sh; shellcheck scripts/*.sh .github/scripts/cd/*.sh; terraform fmt -check -recursive terraform/; terragrunt hcl format --check --working-dir terraform/live | Check-only flags are essential; do not drop them or install tools implicitly |
| Local tool analysis | actionlint; tflint --recursive; tfsec --no-color . --minimum-severity=MEDIUM | Inspect installed tool/config behavior; initialization/downloads/caches are separate write/network operations, not guaranteed read-only |
| Offline tests with writes | .github/scripts/cd/tests/test-detect-scope.sh; test-resolve-terragrunt-layers.sh; test-validate-infra-gate.sh in the same directory | Bash/jq fixtures create temporary outputs; do not run during a strict no-write assessment |
| Readiness deployment tests | scripts/tests/run-offline-readiness-tests.sh | Offline Bash/jq tests run in a scrubbed environment with a pinned fake AWS executable, synthetic identities and disposable temporary files; inherited credentials, profiles, startup hooks and shell functions cannot reach real AWS |
| App build/tests | dotnet restore/build/test demo-api/terragrunt-demo.sln | Restore uses package network/cache; build/test create bin/obj/results; not read-only |
| Container checks | Docker build of demo-api | Pulls/builds images, writes caches and executes Dockerfile steps |
| Artifact helper checks | render/validate scripts in scripts/ | Renderers write files; validate-only JSON helpers use local jq; inspect caller because adjacent publish/read helpers use S3 |
| Terraform/Terragrunt validation | init, validate, plan; ci-terragrunt-plan.yml | May generate provider/backend files, locks, caches and Lambda ZIPs; dependency outputs/backends/providers contact AWS; plan is not an offline safety synonym |
| State/resource audit | audit-terraform-state-secrets.sh; check-deploy-resources.sh | AWS reads; audit downloads sensitive state to private temporary files; prohibited in an offline/no-AWS task |
| Bootstrap/apply | bootstrap.sh init-state/apply-*; full-dev-bootstrap; cd-terragrunt.yml | Creates/changes AWS resources; secret steps read/write secret values |
| Deploy/promote/rollback | deploy.sh; ecs-blue-green-deploy.sh; deployment workflows | Registry/S3/ECS/ALB/EventBridge mutations; partial success possible |
| Destroy/cleanup | Terraform destroy or manual deletion | Destructive; never a routine validation command |

Dry-run is helper-specific, not a universal purity guarantee. Some helpers still
validate/render/write outputs. --plan-only still permits initialization and AWS
reads. AWS CLI --generate-cli-skeleton output used in hygiene is an offline
shape check, not a real task registration or runtime test.

Startup migrations now default off; legacy opt-in or the explicit confirmed migration
command can still mutate SQL. validated-v2 performs a native read-only permission
check at startup. KMS operations use the credential chain. A local API start
can contact configured services and mutate a database. Tests disable startup
migrations and replace healthy readiness checks; inspect configuration before
broadening integration tests.

## Existing test meaning and gaps

[E14-A container tests](../../demo-api/terragrunt-demo.Tests/ContainerContractTests.cs)
run in the existing .NET suite and deterministically reject base/user/port/publish
contract regressions. [Evidence and a bounded Linux smoke recipe](e14-container-hardening.md)
distinguish passing host application checks from unavailable Docker execution.

[Text handler tests](../../demo-api/terragrunt-demo.Tests/TextHandlersTests.cs)
verify encryption/persistence/decryption/pagination using doubles.
[Pagination tests](../../demo-api/terragrunt-demo.Tests/TextPaginationTests.cs)
execute the actual repository and GET handler/controller against an in-memory
SQLite relational database. They cover normal and consecutive pages, tied
CreatedAt timestamps with unique Id ordering, lower-bound internal normalization,
HTTP validation/defaults, representable offset boundaries and overflow rejection
before repository/connection work. Production EF SQL Server translation is checked
through the actual repository with connection opening and command execution
suppressed; it is not live SQL Server execution, migration or performance evidence.
Stable-page assertions use an unchanged dataset, not concurrent-write snapshots.
[KMS wrapper tests](../../demo-api/terragrunt-demo.Tests/KmsEncryptionServiceTests.cs)
and [text endpoint tests](../../demo-api/terragrunt-demo.Tests/TextEndpointTests.cs)
cover the 4095/4096/4097 UTF-8 byte boundaries with ASCII and multibyte input,
including surrogate pairs. Recording SDK/repository doubles verify local rejection
without encryption or persistence, HTTP 400 string errors, blank-input precedence,
and accepted bytes, ciphertext, DTOs and cancellation forwarding. The wrapper
tests also cover base64/UTF-8 decryption conversion; no live AWS is required.
[Health tests](../../demo-api/terragrunt-demo.Tests/HealthEndpointTests.cs)
verify liveness/readiness responses and Swagger/environment behavior.
They do not prove real KMS, SQL migrations, deployment or rollback.
[Readiness probe tests](../../demo-api/terragrunt-demo.Tests/ReadinessProbeTests.cs)
exercise transient startup, consecutive-success reset, bounded failure, fixed
loopback `/ready` addressing and strict response validation without starting the
normal application or using AWS/SQL. The deployment fixtures exercise both color
directions, per-replica evidence, exact target/cohort identity, stale/missing and
hostile observations, invalidation, bounds, and the no-listener-write failure
boundary. Renderer checks prove the same immutable image, non-essential probe,
no secret/environment injection, no restart/health policy and unchanged essential
application launch. App CI also executes the packaged probe capability from the
built image. These are deterministic contract checks, not live Fargate evidence.

CD fixture tests exercise scope/layer/gate behavior through the dedicated
[CD safety workflow](../../.github/workflows/ci-cd-safety.yml), described below.
Hygiene checks top-level scripts, readiness fixtures and the CD helper/test shell
tree. It parses schema JSON and uses hand-written validators; that is not exhaustive
JSON Schema conformance testing. Protected E1 controller/recovery fixtures exist;
comprehensive deployed rollback evidence remains absent.

## CURRENT CONTRACT — E11 CI selection and enforcement

[CI orchestration](../../.github/workflows/ci.yml) starts for PRs targeting
`develop`/`main` (including retargeting edits) and all branch pushes, without event
path filters. It checks out the exact event SHA with complete history and runs
[focused selection tests](../../.github/scripts/ci/tests/test_ci_selection.py)
before the [selector](../../.github/scripts/ci/select-checks.py).

The selector inspects complete push history, or both the PR merge-base/head diff
and the exact base/tested-merge diff. Renames are deletion plus addition; unknown
paths, shallow/missing history, ambiguous merges, unsupported file types and
malformed observations select every validation job. Checkout identity mismatch
fails selection. Failed/missing selection causes the job conditions to attempt
all gates, and cannot pass the final unconditional `CI Validation` result.

| Change family | Selected existing validation |
| --- | --- |
| Protected scripts, schemas, authority inputs and specs | E1 acceptance and hygiene; readiness helpers additionally select app CI |
| Terraform roots/modules, including TARGET and security | E1 acceptance, hygiene and infrastructure static checks |
| Application source | App CI, including .NET, Docker and readiness fixtures |
| Application Docker/deploy inputs | App CI, E1 acceptance and hygiene |
| CI orchestration/selector, unknown workflow or composite action | All validation jobs |
| Known workflow changes | E1 acceptance/hygiene plus their affected app or infrastructure job |
| Current KDD/guidance | E1 acceptance and hygiene |
| Explicit historical narratives/diagram PNGs | Hygiene; no blanket expensive validation |

E1 acceptance is independently selected in the orchestrator. Infrastructure
static CI retains acceptance by default for standalone callers; the orchestrator
sets `run_acceptance: false` because its separate job executes the same gate once.
No E1 suites or acceptance criteria are replaced. `CI Validation` requires actual
successful selected job results and explicitly skipped unselected jobs; failed,
cancelled, skipped or missing required execution cannot count as acceptance.
CD Safety remains a separate unconditional check with its own conservative
selector and actual-process result enforcement, now also covering main pushes.

The hygiene workflow applies Bash syntax and ShellCheck to
`.github/scripts/cd/*.sh` and `.github/scripts/cd/tests/*.sh` as well as its existing
script inputs. No AWS credentials, OIDC, provider initialization or deployment is
introduced by E11. GitHub required-check/branch-protection configuration is
external and remains unverified. Local tooling availability is reported separately.

Focused command (Git/Python only, writes disposable Git fixtures):

```text
python -I -B -m unittest discover -s .github/scripts/ci/tests -v
```

Local E11 validation: 33 focused tests passed. The current .NET source was rebuilt
without restore and all 40 tests passed (environment-only EventLog suppression).
The complete E1 gate passed all 983 tests (959 regressions plus 24 WP7 tests),
AC1-AC16 and all nine static checks, with no failures, errors or skips.
Inventory, Python/JSON parsing and inactive 0/11, 0/16 and 0/8 activation maps
also passed. This is provider-free repository evidence, not live installation.
Native Ubuntu parsed 27 workflows and checked five local reusable references;
33 shell syntax checks, the existing CD selector/result fixtures and all five
process-supervision tests passed from normalized disposable source copies.
`jq`, ShellCheck and actionlint were unavailable locally: the three jq-dependent
CD suites and full fresh Linux E3 were not rerun, and lint success is not claimed.
Their existing CI execution remains configured; no tooling was installed.
One bounded E11 self-check found no scope, authority or activation change.

## CD safety enforcement — reviewed contract

`CI - CD Safety` exposes the unconditional `CD Safety Validation` job for PRs
targeting develop/main (including retargeting edits) and pushes to develop/main.
It has no event path filter, deployment invocation or AWS dependency. It checks
the exact event checkout, runs selector/result self-tests, then executes all
three scope/layer/gate suites when selected. Each process exit is recorded;
missing, skipped or failed required execution cannot satisfy the final result.

The [selector](../../.github/scripts/cd/select-safety-tests.sh) defaults to RUN.
Exemption requires complete history and only ordinary non-executable files in
root README.md, Markdown/PNG under terraform/docs, or C# under the application
and application-test directories. AGENTS.md files remain relevant everywhere.
Unknown paths, executable/type changes, and uncertain comparisons run the suite.
PR selection combines merge-base-to-head and base-to-tested-merge differences;
push selection uses before-to-pushed differences. Rename detection is disabled
to retain relevant deleted origins. Checkout identity mismatch fails validation.

Offline entry points (Bash/Git/jq/Unix tools; disposable temporary writes):

- The three existing `test-detect-scope.sh`, `test-resolve-terragrunt-layers.sh`
  and `test-validate-infra-gate.sh` scripts under `.github/scripts/cd/tests/`.
- [Selector histories](../../.github/scripts/cd/tests/test-select-safety-tests.sh)
  and [workflow outcomes](../../.github/scripts/cd/tests/test-safety-workflow.sh)
  run unconditionally in this workflow, including exempt changes.
- [Controlled mutations](../../.github/scripts/cd/tests/test-safety-mutations.sh)
  are a local evidence command; they corrupt only disposable copies and verify
  failing assertions and accidental exemption-policy broadening are rejected.

Preserve the narrow exemption boundary when dependencies change: if a helper
starts consuming an exempt area, reconsider and test that exemption. History
uncertainty means RUN; selector errors or wrong checkout identity cannot become
a successful exemption. Logs/summaries distinguish "suite not required" from
"suite passed" and record event, comparison/test SHAs, run identity and process
results.

### Review and evidence boundary

The independent Reviewer returned REVIEW_PASS for all 12 acceptance criteria
of [the spec](../../specs/cd-test-enforcement/spec.md), as supplied in the
post-review handoff. Authoritative identities:

- BASE_REVISION: `ac28991a8346118fecc001c216add63a2884b221`.
- CANDIDATE_REVISION: `9cef1cb7ea712857c947ed8e5591651122fa476a`.
- MAIN_INTEGRATION_REVISION: `41c53252efc66ff86b88cb96d50b7825e88ae27d`.
- DEVELOP_INTEGRATION_REVISION: `399cc900ec3068284ca982bde163427c80e70de3`.

Remote job/step metadata rechecked during knowledge capture confirms the stable
`CD Safety Validation` identity and these outcomes:

| Evidence | Recorded revision (PR head or pushed commit) | Outcome |
| --- | --- | --- |
| [Candidate PR](https://github.com/Kendall04/terragrunt_demo/actions/runs/35422984748) | `9cef1cb7ea712857c947ed8e5591651122fa476a` | Suite execution and final result succeeded |
| [Controlled failure](https://github.com/Kendall04/terragrunt_demo/actions/runs/35423039579) | `39d7fc8f416454345fc529faa04e9f93593537b4` | Suite and final result failed |
| [Restored experiment](https://github.com/Kendall04/terragrunt_demo/actions/runs/35423077706) | `6fa33890cb0e71d5f30a5c3e1407641c18738629` | Suite execution and final result succeeded |
| [Unrelated PR](https://github.com/Kendall04/terragrunt_demo/actions/runs/35426970333) | `c1352aeb10abe6f19719c7e40c6e43828e33dc6a` | Self-tests and final result succeeded; suite skipped as exempt |
| [Develop integration push](https://github.com/Kendall04/terragrunt_demo/actions/runs/35428412430) | `399cc900ec3068284ca982bde163427c80e70de3` | Suite execution and final result succeeded |

PR head identities above are not substitutes for the tested merge SHA. Log
downloads returned HTTP 403 during capture; exact checkout/per-process log
validation and the full acceptance assessment rely on the supplied Reviewer PASS,
not a claim that those logs were independently reread here.

Required-status-check enforcement remains external and unconfigured/unverified;
see [delivery](deployment.md) for outstanding governance actions. These tests
do not prove AWS readiness, full deployment correctness, every workflow expression
or ALB behavior, or tamper resistance against deliberate removal of enforcement
and its tests.

## Deployment readiness promotion — reviewed evidence

The deployment-readiness feature completed independent review with
`REVIEW_PASS_WITH_NON_BLOCKING_FINDINGS`. Authoritative identities:

- Planning revision: `cfef900b576a9aa811859e8e194f41528daff1fc`.
- Reviewed candidate: `e7634874da19b1502eaa5451ed00d57ad0d80e94`.
- Main integration revision: `6da9a699b5de0e8fe228fd4f099f1e13320d6558`.
- Integrated pull request: [#16](https://github.com/Kendall04/terragrunt_demo/pull/16).

[Exact-candidate CI](https://github.com/Kendall04/terragrunt_demo/actions/runs/35756560824)
completed successfully for the reviewed candidate. It covered the application
tests and packaged probe, hermetic Bash/jq readiness fixtures, task-definition
rendering/validation, bounded Linux process supervision, ShellCheck/repository
hygiene and selected infrastructure static checks. The deterministic suites cover
both color directions, every-replica evidence, identity and cohort replacement,
malformed external and nested JSON, ALB normalization, repeated service identity,
deadline enforcement, registered-definition execution controls, and the
no-listener-write failure boundary.

[Post-merge orchestration](https://github.com/Kendall04/terragrunt_demo/actions/runs/35762365169)
completed successfully for the integration revision. It ran scope detection and
main-branch informational notices; infrastructure apply and application delivery
jobs were skipped. It is evidence of repository orchestration behavior, not AWS
runtime validation.

This provenance establishes deterministic local/CI behavior and the reviewed
repository contract. No live Fargate task, ALB promotion, dependency readiness or
other AWS runtime behavior was exercised, so it is not deployed-production proof.

## Working guidance

The correction subset `scripts/tests/test-ecs-readiness-gate.sh
--validation-fixes-only` runs first in the full suite. It rejects malformed
nested attachment/detail/container/network evidence at startup, complete and
final observations; final cases exercise the promotion path and assert no
listener/rule mutation. Registered-definition cases reject execution overrides
and invalid/enabled restart policies before task probe results are read. Positive
cases retain missing startup collections, empty API defaults and explicitly
disabled restart policies. The renderer suite feeds its actual rendered payload
through the production registered-definition validator using a local capture
double. No AWS registration or discovery occurs in these tests.

Authorization-response boundary regressions follow the correction subset in
`scripts/tests/test-ecs-readiness-gate.sh`; use `--response-boundaries-only` for
the focused subset. They cover initial/final listener and rule streams, registered
definitions, services, task lists and target-health envelopes, including actual
promotion-path no-listener-write assertions. The normal hermetic readiness entry
point runs this subset together with the existing regression suites. These tests
create disposable files and require Linux Bash/jq tooling; they do not access AWS.

For future changes, choose checks matching the affected contract and authorized
side effects. Report what was actually run and what remains unverified.
Do not claim tests passed based on metadata defaults or old generated outputs.
For documentation-only work, inspect diff, resolve local links, and verify changed
paths; builds, dependency installs and cloud commands are unnecessary.

After changes, inspect tracked/untracked status and ensure generated files were
not accidentally added. [Decisions/backlog](decisions-and-limitations.md) records
missing coverage and reproducibility work without authorizing it.

## E1 WP2A foundation — offline evidence

The [neutral security-root foundation](../infra/security/README.md) adds a separate
closed-source runner: `python -I -B scripts/tests/security_root/run.py --report
<temporary-report-path>`. It uses WP1 hermetic guards and disposable mutation
fixtures. `python -I -B scripts/tests/security_root/render.py` checks generated
Terraform/ wrapper wiring without writes; `--write` explicitly regenerates it.
The unchanged WP1 runner remains `python -I -B scripts/tests/authority/run.py`.
Neither command accepts E1 or proves live controls. CURRENT authority remains
positive/PARTIAL characterization; closed synthetic negative fixtures are not
CURRENT or final target completeness. Run formatting checks without init; missing
provider validation is an explicit gap, never a reason to contact AWS/download.
Git Bash selector cleanup is still FAILED/UNRESOLVED and Linux UNVALIDATED.

## E1 WP2B foundation — offline evidence

[Control bundles](e1-control-bundles.md) add `python -I -B
scripts/tests/control_bundles/run.py --report <temporary-report-path>`. The suite
uses hermetic guards and disposable production-source mutations. Run the complete
WP1 and WP2A suites alongside it; CURRENT evidence meaning is unchanged.
The existing security-root renderer now checks both admitted modules and catalog
integrity. `pack_bundle.py` in the same directory prepares/verifies only inactive
artifacts outside the repository; it cannot upload, install or execute them.
Python AST/JSON parsing and check-only formatting are offline; provider-free
Terraform expression evaluation must use disposable configuration with no backend
or provider. Provider-backed validation remains UNVERIFIED/not initialized.

## E1 WP2C foundation — offline evidence

[Controller compute](e1-controller-compute.md) adds `python -I -B
scripts/tests/controller_compute/run.py --report <temporary-report-path>`. Run the
24-test suite alongside WP1 (236), WP2A (18), and WP2B (22). It mutates disposable
canonical source and actual Terraform and checks fixed mappings, deny-only roles,
closed envelopes, exact-version requirements, overrides and inactive activation.
The existing security-root renderer checks the compute module too. Provider-free
Terraform evaluation must use disposable configuration without providers/backend;
check decoded authority, joined references, empty compute instance maps and the
creation preconditions. No image download, bundle installation, AWS call or
provider initialization is authorized by these checks. Existing platform/live gaps
remain unchanged.

## E1 WP2D ownership and publication — TARGET

[Ownership and administrator publication](e1-ownership-publication.md) documents
the extracted neutral declarations, explicit protected consumer records, dormant
cleanup/NAT reservations and offline exact-version installer. Existing ordinary
roots remain CURRENT transitional exclusions; deployment/state migration has not
occurred. WP2C compute stays inactive. Run `python -I -B
scripts/tests/ownership_publication/run.py` alongside all accepted suites.
This is repository evidence pending independent review, not deployed enforcement.

## E1 WP4D — offline candidate checks

WP5 checks are described in
[protected environment lifecycle](e1-protected-environment-lifecycle.md).
Run `python -I -B scripts/tests/lifecycle/run.py` for the focused hermetic suite
and `python -I -B scripts/tests/lifecycle/check_static.py` for actual Terraform
gate/policy/trust and IAM size evaluation in a disposable provider-free root.
The checker runs only console/validate without providers/backend. It does not
initialize actual lifecycle roots or execute the runtime's live init path.

[WP4D materialization](e1-wp4d-iam-materialization.md) adds the hermetic
`python -I -B scripts/tests/wp4d/run.py` entry point. It checks action/resource/
condition combinations, import/schema closure, exact installation readback,
protected entrypoint construction, warm package loading and live-membership
adapter rejection using doubles. Run all eleven existing WP1–WP4C Python entry
points alongside it; passing fixtures do not prove live IAM or AWS membership.

`python -I -B scripts/tests/wp4d/check_static.py` uses installed Terraform
console/validate in a disposable configuration containing only variables and
locals. It evaluates the actual generated WP4D gates/policies/trusts for empty,
fully synthetic and invalid prerequisite maps. It has no backend/provider,
initialization, credential discovery, AWS operation or dependency installation.
It does not validate AWS provider resource schemas. Check generated wiring with
`scripts/tests/security_root/render.py`, inventory freshness, Python/JSON parsing,
`terraform fmt -check -recursive terraform/`, local documentation links and
`git diff --check`. Store reports/packages outside the repository.


## E1 WP6 - protected workflow candidate

[WP6](e1-protected-workflows.md) adds `python -I -B scripts/tests/workflows/run.py`
(61 hermetic tests) and `python -I -B scripts/tests/workflows/check_static.py`
(actual generated Terraform gate/trust/policy and public bucket isolation).
Run the thirteen existing WP1-WP5 suites too: the accepted baseline is 898 tests.
`python -I -B scripts/workflow_requests/render.py` checks deterministic fixed
workflows; `--write` regenerates only the admitted source-driven caller/entry files.
The generated `.yml` files use JSON, a YAML subset, so stdlib JSON parsing also
checks their YAML syntax. Inline Python and fixed Actions schema/pins are checked
by the focused suite. Static CI and the retained scope job have no AWS permission.

Use the existing security-root renderer, source inventory, Python/JSON parsing,
WP3 extracted-package checker, WP4D/WP5 static checks, check-only Terraform format,
local documentation links and `git diff --check`. Neither new checker initializes
providers, runs the runtime client's live plan path, obtains a GitHub token or
accesses AWS. Admin-channel and installation projections are synthetic fixtures,
not genuine approval/readback or operational proof. Supported-host fresh Linux
E3, provider-backed schema checks, live IAM/GitHub conformance and membership
remain unverified. Keep reports and extracted packages outside the repository.

## E1 WP7 — final repository acceptance gate

Run `python -I -B scripts/tests/final_acceptance/gate.py --report-dir
<outside-repo-directory>` using preinstalled Python/Git/Terraform. It requires all
959 accepted regressions plus the focused WP7 suite, exact generated Terraform and
workflow wiring, inventory, packages, provider-free WP4D/WP5/WP6 static checks,
parsing, current KDD links, approved-contract hashes, check-only Terraform format
and diff whitespace. Reports identify exact content/revision/dirty status and AC
families; missing/skipped/failed evidence cannot pass. No init/provider/backend,
AWS access, dependency download or activation occurs. Static CI runs this gate.

WP1's old positive bypass witnesses now characterize inert historical source in
disposable fixtures. They must not be interpreted as final TARGET permissions.
See [WP7 acceptance and live limits](e1-final-acceptance.md). Optional preinstalled
Linux checks use `scripts/tests/final_acceptance/check_linux.py` for YAML/Bash
syntax and the existing E3 entry points; unavailable dependencies are explicit.

## E15 — provider-free ephemeral lifecycle readiness

Run `python -I -B scripts/tests/ephemeral/run.py` and
`python -I -B scripts/tests/ephemeral/check_plan_shape.py`. The
[E15 contract](e15-ephemeral-lifecycle.md) covers offline preparation, graph order,
confirmation/residual/budget boundaries and teardown-only WP5 empty-state checks.
The shape check uses installed Terraform 1.13.4 with an empty provider-free local
configuration, no backend, init or AWS. Both run as additional E1 gate checks;
983 E1/WP counts remain fixed. No local notes or mock proves real teardown.

## E8 — provider-free image retention

Run `python -I -B scripts/tests/retention/run.py` for 18 focused hermetic tests.
The [E8 contract](e8-rollback-image-retention.md) records the captured any/count-15
expiration risk, untagged WP3 publication, removal of all three protected repository
lifecycle policies and unbounded storage tradeoff. The existing E1 gate runs this
suite as an additional check; accepted E1/E2/E4 counts stay unchanged. Generated
structures, installed exact availability reads, dev/prod rollback/emergency,
E4 UNCERTAIN/E2 holds, package hashes and unchanged authority are tested offline.
No provider initialization or AWS preview/read/deletion is required or implied;
live policies, pulls/restoration and race behavior remain unverified.

## E7 — provider-free CloudWatch alarm configuration

Run `python -I -B scripts/tests/monitoring/run.py` for the focused hermetic suite.
[The monitoring contract](e7-cloudwatch-alarms.md) records corrected ECS/NAT
metrics, dimensions/collection, gauge missing-data behavior, sparse 5xx exceptions
and guarded capacity math. Tests preserve dev/prod generation, alarm inventory,
protected ownership and bounded IAM. Run applicable existing E1 acceptance,
renderer, source-inventory, lifecycle static, local-link and check-only Terraform
format checks too. No provider initialization, AWS operation or dependency
installation is required; metric delivery and live alarm/SNS behavior remain
unverified.

## E13 — provider-free NAT reliability

Run `python -I -B scripts/tests/nat/run.py` for hermetic controller, event,
readiness, replacement-approval and generated-source checks. Run
`python -I -B scripts/tests/nat/check_static.py` for actual generated retry,
qualified destination, queue policy and alert expression evaluation in a disposable
provider-free Terraform root. Both run inside the existing final acceptance gate;
the accepted 983 E1/WP tests retain their counts. Run E7 monitoring regressions too.
The [runbook](e13-nat-reliability.md) separates configuration/bootstrap evidence
from unverified live forwarding, AMI compatibility, failure containment and
notification/rollout proof. No init, provider, AWS or installation is authorized.

## E2 environment mutation arbitration

Run python -I -B scripts/tests/mutation/run.py for the focused hermetic suite and
python -I -B scripts/tests/mutation/check_static.py for actual generated bucket
barriers in a disposable provider-free Terraform configuration. The existing
final acceptance gate retains all 983 E1/WP tests and adds E2 separately;
no initialization, provider, AWS, dependency installation or activation occurs.
See [E2 contract and evidence](e2-environment-mutation.md).

Final E2 local gate: 983 accepted E1/WP tests plus 41 E2 tests passed, with
AC1–AC16, all ten static checks, inventory and parsing; no failures/errors/skips.
The evidence is provider-free repository validation, not AWS installation.

## Batch 2 combined integration evidence

[Combined reconciliation and validation](batch2-integration.md) records preserved
E2/E13/E14-B contracts, actual lint debt comparisons and local tooling gaps.
The full jq-dependent CD/E3 suites and exact pinned SDK/container execution remain
unverified on this host; independent candidate or earlier Batch 1 results are not
a substitute for fresh combined acceptance.

## E4 bounded post-switch recovery

[The selected scenario and operator runbook](e4-post-switch-recovery.md) cover
one failed switch-evidence write under a still-live E2 owner. Run
`python -I -B scripts/tests/post_switch/run.py` for the focused hermetic suite.
The existing full final-acceptance gate now includes this separate suite without
changing the required 959 accepted regressions plus 24 WP7 tests or E2 criteria.
Tests use actual delivery journals/controllers and E2 grants with deterministic
faults/interleavings, no sleeps, credentials, SDK network calls or provider init.

The focused E4 suite passed all 28 tests with no failures, errors or skips.
Affected suites passed 98 delivery, 53 recovery, 33 WP4D and 41 E2 tests.
The full source gate returned E1_REPOSITORY_ACCEPTANCE_PASS: 959 accepted
regressions plus 24 WP7 = 983 E1/WP tests, independently 41 E2 and 28 E4 tests,
AC1–AC16 and all 12 additional checks passed. The E13 check also passed its
40 tests. Inventory/package/source admission, 149 Python/48 JSON/22 generated
YAML parses, generated wiring, approved immutable E1 hashes, provider-free IAM/
trust/PassRole and installation checks, Terraform format and whitespace passed.
No failures/errors/skips occurred; activation remains 0/11, 0/16 and 0/8.
Reports are outside the worktree and identify precommit source/dirty identity;
this validation-result paragraph was added afterward and checked separately.
The runbook's two Bash diagnostic blocks passed syntax-only checks using existing
Git Bash; those AWS commands were never executed. Exact E1 authorization, E2
primitive and E3 source bytes remain unchanged after line-ending normalization.
One bounded requirements self-check confirmed original grant/request identity,
fresh post-switch readbacks/post-plan guards, no attempted-stage resend, no
takeover/compensation API and truthful blocked outcomes.

No native Linux rerun is claimed: existing `codex-vm` SSH failed host-key
verification and WSL enumeration returned E_ACCESSDENIED. No host trust, tooling
or dependencies were changed. Native E3, live installation, SDK attribution,
IAM/S3 CAS and ECS/ALB/EventBridge behavior remain unverified here. Application,
E7, E11 and E14-B suites were not rerun because their implementations are unchanged;
accepted baseline results are not presented as fresh E4 execution.

## E2-R interrupted-owner diagnostics

Run `python -I -B scripts/tests/owner_recovery/run.py` for hermetic interruption,
fencing counterexamples and read-only diagnostic tests. The existing final gate
requires this separate suite without replacing the 983 E1/WP, 41 E2 or 28 E4
tests. E13's 40-test check and all existing provider-free static checks remain.
The [runbook](e2r-owner-recovery.md) records why general administrative recovery
cannot yet prove executor termination/remote quiescence. Unsafe head changes in
two tests are confined to an in-memory double and demonstrate delayed old effects;
they never authorize a production unlock or simulate proven administrative recovery.
No installed package, IAM/trust/PassRole, Terraform source, activation or E2/E4
runtime change is introduced. Source inventory, Python/JSON parsing, local KDD
links, package/generator integrity and `git diff --check` are required as usual.

Final E2-R source gate returned `E1_REPOSITORY_ACCEPTANCE_PASS`: 959 accepted
regressions + 24 WP7 = **983 E1/WP tests**, independently **41 E2**, **28 E4**,
**23 E2-R**, and **40 E13** tests passed with no failures, errors or skips.
AC1–AC16 and all 12 additional checks passed, including actual provider-free
E2/WP4D/WP5/WP6 IAM/trust/PassRole expressions, NAT configuration, generated
security/workflow wiring, deterministic packages, immutable approved contracts,
KDD links, Terraform format and whitespace. Inventory/parsing passed for
152 Python, 48 JSON and 22 generated YAML files; activation remains 0/11, 0/16
and 0/8. One bounded acceptance self-check confirmed original E2/E4/runtime and
authority/package inputs are unchanged, diagnostics cannot write/recover, and no
positive administrative recovery is claimed. Reports outside the worktree bind
precommit source/dirty identity at baseline `ea05ce4fd05f5dda7487438d84e4d0501a314e03`.
This result paragraph was added afterward and checked separately; no executable
source changed after the gate. No AWS, provider initialization, deployment,
dependency installation, push or merge occurred. Native Linux E3 was not rerun
because its implementation and shell inputs are unchanged. Live authentication,
executor termination/neutralization, remote-effect settlement, S3 CAS/IAM and
ECS/ALB/EventBridge behavior remain unverified; administrative recovery is BLOCKED.

## E15-B — provider-free DEV DOWN boundaries

Run `python -I -B scripts/tests/dev_down/run.py` for 42 hermetic tests of the actual
WP5 consent/runtime/E2/NAT and local operator boundaries. The existing E1 gate
includes this additional check without replacing 983 E1/WP or AC1–AC16 evidence.
[Contract and runbook](e15b-dev-down.md) distinguish offline artifact consistency,
fresh ECS snapshots and blocker witnesses from protected approval, controller
closure and genuine live teardown. Existing E15/E2/E2-R/E4/E13/E8 regressions,
source admission, packages, generation, IAM/trust/PassRole and inactive installation
checks remain required. No AWS or Terraform provider initialization is permitted.

## E15-C — provider-free exact destroy approval

Run `python -I -B scripts/tests/exact_destroy/run.py` for 46 hermetic tests of
actual WP5 approval/journal/E2/runtime boundaries. The E1 gate includes this
additional check, preserving 983 E1/WP and AC1–AC16 requirements. The
[contract](e15c-exact-destroy-approval.md) distinguishes synthetic trusted ports
from authentic administrative context, real conditional S3 semantics and installed
single-use execution. E15-B/E15/E2/E2-R/E4/E13/E8, package/source/generation/IAM,
inactive installation, parsing/KDD/format and whitespace checks remain required.
No AWS/provider/state operation or activation is allowed by these tests.

E15-C acceptance passed 983 E1/WP tests, AC1–AC16, E2 41, E2-R 23, E4 28,
all 17 additional gate checks (including E15-C 46/E15-B 42/E15 30/E8 18/E13 40),
and independent E11 33/E14-B 19. Parsing: 164 Python, 50 JSON, 22 generated YAML;
activation: 0/11, 0/16, 0/8. Installed Ubuntu lint reproduced the exact inherited
24 TFLint warnings and 46 tfsec findings, with no differences. See the linked
E15-C results for scope and remaining live/authority prerequisites. No executable
source changed after the gate; these result paragraphs were checked separately.

## E15-D — provider-free administrative handoff

Run `python -I -B scripts/tests/handoff/run.py` for 50 hermetic actual adapter/runtime
boundary tests. The full E1 gate includes it without changing 983 E1/WP or AC1–AC16.
[Contract/runbook](e15d-administrative-handoff.md) separates concrete SDK code from
uninstalled storage/session authority and real service proof. E15-C/B, E15, E2/R/
E4, E8/E13, package/inventory/generation/IAM/activation, parsing/KDD/format and
whitespace regressions remain required. No AWS, provider init or activation occurs.

E15-D full acceptance passed 983 E1/WP, AC1–AC16, E2 41/E2-R 23/E4 28 and all
18 additional checks (E15-D 50, E15-C 46, E15-B 42, E15 30, E8 18, E13 40).
Independent E11 33/E7 8/E14-B 19 passed. Parsing covered 167 Python/50 JSON/22
YAML; activation stays 0/11, 0/16, 0/8. Ubuntu lint exactly reproduced inherited
24 TFLint warnings and 46 tfsec findings, with no differences. See the linked
results for scope and pending installation/owner/live gates. No executable source
changed after the gate; these result paragraphs were checked separately.

## E15-F — provider-free NAT quiescence

Run `python -I -B scripts/tests/nat_quiescence/run.py` for the independent
[contract](e15f-nat-quiescence.md): actual NAT/E2/journal boundaries, deterministic
late-effect barriers and durable denied teardown. No live adapter, package/IAM
activation or shared acceptance/source-inventory regeneration is supplied here;
combined integration must reconcile admission. Existing E13/E2/R/E4/E15/B/C/D and
E1 acceptance regressions remain required. No AWS/provider initialization is allowed.

## E15-E/F combined provider-free validation

Run `python -I -B scripts/tests/combined_quiescence/run.py` plus both ECS/NAT
feature suites and the original final acceptance gate from the integrated tree.
[Combined contract](e15ef-combined-quiescence.md) records exact repository/live
limits, inventory/package reconciliation and required original regression checks.
No AWS, provider initialization, installation or timing-based settlement proof is
authorized. Standalone feature agents did not complete full E1 acceptance.

## E15-G provider-free operational components

Run `python -I -B scripts/tests/operational_teardown/run.py` and the complete
original final-acceptance gate. [Contract and limits](e15g-operational-teardown.md)
distinguish implemented ECS/whole-owner components from blocked installation.
E1/WP, E2/R/E4, E13 and E15/B/C/D/E/F/combined regression requirements remain.
Inventory/packages, static gates, KDD links, parsing, check-only Terraform format
and whitespace are required; no AWS/init/network or installation occurs.

Final E15-G source gate completed with E1_REPOSITORY_ACCEPTANCE_PASS: 983 E1/WP,
AC1-AC16, E2 41/E2-R 23/E4 28 and all 22 sequential checks, including E15-G 54,
E15-E 49/E15-F 51/combined 39 and existing E15/B/C/D/E8/E13 suites. Independent
E7 8/E11 33/E14-B 19 passed. Parsing: 179 Python/50 JSON/22 generated YAML;
activation stays 0/11, 0/16, 0/8. All eight extracted WP5 package imports passed.
Static finding identity/multiplicity remains exactly inherited 24/46. See E15-G
for report paths, the single bounded repair, missing native Linux/lint tooling
and explicit installed/live limitations. No executable source changed after this
successful gate; results/link/whitespace documentation checks follow separately.


## E15-H trusted NAT source increment

[E15-H](e15h-nat-trusted-closure.md) selects one bounded CAS admission coordinator,
adds cooperative E13 dispatch/seal accounting and native ASG read contracts under
the original E15-G owner. Installed authentication, callable-version coverage and
remote finality remain unproved; networking and complete DOWN still fail closed.
No IAM policy, active binding or AWS resource is installed by this increment.

## Original complete DEV lifecycle (2026-10-13)

The owner restored the original full architecture. E15-S was explicitly reverted;
E15-S2 is not integrated. The [first-session procedure](original-full-lifecycle.md)
records the complete resource/state graph, existing WP5/WP6 commands, thin DEV
entry and separate UP installation versus DOWN finality blockers. No reduced
lab, authority bypass, activation or AWS operation is introduced.

## Historical E16 supervised mode (retired 2026-10-28)

The [historical E16 operator record](e16-practical-dev-lifecycle.md) implements
per-layer original DEV saved-plan review/apply and observed shutdown under an
explicitly authorized, exclusive existing-human state-writer transfer. Default
mode remains inert; PROD/shared/security-root ownership is retained. Existing
WP3/WP4 delivery and E13 recovery remain. E15-G/H advanced finality contracts are
not weakened or activated. Source readiness is distinct from genuine installation
and live AWS validation; no AWS operations occurred.


E16 final offline acceptance: 983 E1/WP, AC1–AC16 and all 44 gate suites/checks
PASS; E16 35 and original entry 12 PASS. E2/E2-R/E4, E13 and E15-E/F/G/H
regressions, inventory/package identities and generated-source checks passed.
Historical static debt remains 24 TFLint/46 tfsec by rule/resource/message/source
snippet and multiplicity, without suppression. See the [E16 evidence record](e16-practical-dev-lifecycle.md#completed-offline-acceptance-2026-10-13)
for report paths, the bounded corrections, unavailable tools and separate
IAM/provider/Linux/AWS gates. No cloud, provider init or deployment occurred.

## .NET 10 LTS local migration - 2026-10-16

The owner explicitly authorized upgrading the source to .NET 10 LTS while
retaining the original two-AZ architecture and existing Terraform/Terragrunt
selections. SDK 10.0.402, runtime/ASP.NET 10.0.13 and Microsoft EF Core/testing
packages 10.0.13 were verified against [Microsoft downloads](https://dotnet.microsoft.com/en-us/download/dotnet/10.0),
[release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json)
and NuGet. global.json still disables roll-forward and prereleases. App CI rejects
a different SDK input; Docker bases remain immutable linux/amd64 child manifests.
Microsoft.NET.Test.Sdk is 18.11.0. Other application dependencies are unchanged.

The first successful restore identified two PKCS advisories in transitive 9.0.11.
An explicit System.Security.Cryptography.Pkcs 10.0.13 reference selects the patched
version ([Microsoft advisory](https://github.com/advisories/GHSA-2fmv-rv2c-59x7),
[second advisory](https://github.com/advisories/GHSA-846f-f764-76mx)); no warnings
were suppressed. The final NuGet direct/transitive audit reported no vulnerable
packages from its current public source; this is dated evidence, not a guarantee
against future advisories.

Executed locally through SSH on codex-vm using the exact SDK image:

- Restore and Release build succeeded with zero warnings/errors.
- All 104 .NET tests passed, with none skipped. Existing API/KMS boundaries,
  pagination, health/readiness and container mutation checks remain. The added
  SQL Server model comparison uses no connection and confirms there are no
  pending schema changes; checked-in migration/snapshot files are unchanged.
- All 25 offline reproducibility/static-finding tests passed. Only the three
  reviewed SDK/CI/Dockerfile source-inventory entries were refreshed, with their
  semantic dispositions preserved. This does not certify new AWS authority.
- A fresh Docker build succeeded. Linux smoke verified effective UID 1654,
  nonwritable application binaries, Production /health HTTP 200, packaged probe
  capability and exit 1 without a local readiness server. Smoke used network=none,
  no credential mounts, a dummy connection and startup migrations disabled.

The worktree was moved with git worktree move from
`C:\proyectos\terragrunt_demo-wt-batch1` to `C:\CodexDrop\terragrunt_demo`
(VM: `/mnt/hgfs/CodexDrop/terragrunt_demo`), retaining its history/metadata.
Windows Git manages the linked worktree: its common repository remains under
`C:\proyectos\terragrunt_demo`, so Linux Git cannot follow the Windows gitdir
pointer directly. Build/test uses the shared source without another clone.
NuGet HTTP cache must stay on a Linux filesystem (container `/tmp`), because
its URL-derived cache names contain colons rejected by the Windows-backed share.
The package cache and test logs are outside Git under
`C:\CodexDrop\temp\terragrunt-demo-dotnet10`.

No AWS deployment, real SQL/KMS test, OIDC rebinding, protected installation,
push/merge, full E1 historical suite or Terraform/Terragrunt upgrade occurred.
The reusable-workflow pins and existing cloud authority remain unchanged. This
qualifies the local source/container; a future cloud session needs its own
authorization and release qualification.

## SQL backup/restore local increment - 2026-10-16

Current source: [CLI/protocol/native SQL/S3 adapter and tests](../../operations/sql-backup/README.md).
The app solution includes the new projects; operations/sql-backup changes select
app, hygiene and acceptance gates (and infra if IaC is later added). The new
operational sources are inventoried as UNVERIFIED for authority semantics; a
source hash does not grant a cloud role or certify a policy installation.

Local qualification uses pinned SDK 10.0.402/runtime 10.0.13. The final ordinary
solution run passed 104 existing application tests plus 40 new backup/SDK/process
safety tests. One native SQL fact is explicitly skipped without lab credentials;
it was then executed separately against real SQL Server 2022 **Express 16.0.4265.3**
and passed without skips. Its assertions cover native COPY_ONLY/CHECKSUM header
and VERIFYONLY, a db_backupoperator login with sysadmin=0/CREATE ANY DATABASE=0,
restore to a new DB with MOVE, DBCC CHECKDB, the exact synthetic known row,
refusal of an existing target, rejection of a truncated backup and preservation
of a newer second source row. Restore/verification used a separate administrative
synthetic SQL connection, not the restricted backup login.

Storage in the native test is an in-memory S3 fake. The 40 offline cases cover
checksum/size/key/version mismatch, ambiguous writes, commit failure, corruption,
wrong target/manifest, insufficient space, missing/stale/maintenance, duplicate
JSON, symlinks, credential-output redaction, mandatory TLS and S3 owner/encryption/
conditional-write requests. They do not prove real AWS IAM, SSE-KMS, retention,
notifications, cross-AZ recovery, KMS decryption or application readiness.
The CLI's direct/transitive NuGet audit reported no vulnerable packages from the
current public source. CI selection/enforcement passed 35 tests; reproducibility
retains its separately executed 25 passing tests.

The official SQL image was pinned to
`mcr.microsoft.com/mssql/server@sha256:ba4c8329f48fb8f02e1416be6a930ebfd71268caee78aa985f3af4315e457c89`.
After explicit owner approval, the lab set ACCEPT_EULA=Y/MSSQL_PID=Express under
[Microsoft terms dated 2022-10-21](https://www.microsoft.com/content/dam/microsoft/usetm/documents/sql-server/sql-server-2022-developer-express-evaluation/retail-packaged/SQLServer2022_SQLServer2022DeveloperExpressEvaluation_English.pdf).
It exposed no ports and used network=none, random process-only credentials,
private 0700 staging and a new labelled volume. Runner identity must match SQL's
actual UID/GID (10001/10001 here); do not assume GID 0 or relax permissions.
The SDK's VSTest 18.7 runner executes the prebuilt native test directly, avoiding
SDK first-use migrations as that UID. The harness validates labels and removes
only its containers/volume in finally, including on failure. The existing SQL
container and all other projects remain untouched. The final lab evidence binds
the CLI/test assembly hashes and records cleanup and remaining space.

Private logs/TRX/evidence and the generated cloud preview remain outside Git in
`C:\CodexDrop\temp\terragrunt-demo-sql-backup`. No raw .bak, SQL credentials,
cloud credentials or actual data are committed. Native backup staging existed only
in the retired synthetic volume. No AWS client was invoked against AWS and no
unit, timer, IAM/bucket/endpoint or notification was installed. The service template
uses Requisite and cannot start SQL or EC2 by itself. The code preserves failure/
UNKNOWN outcomes and never claims remote cancellation or authorizes blind replay.

A direct historical WP1 test_repository invocation expects retired active IAM
paths and failed; that invocation is not the current acceptance entry. No retired
source was restored or altered to satisfy it. The supported final-acceptance gate
is used for the current source and its result is recorded separately below.

### Completed E1 acceptance and final targeted SQL correction

Before the final S3 ordering correction, the supported provider-free
final-acceptance gate completed successfully on
2026-10-16: E1_REPOSITORY_ACCEPTANCE_PASS, all 16 AC criteria passed,
959 accepted regressions plus 24 WP7 cases;
E2 mutation 41, E4 post-switch 28 and E2-R owner-recovery 23 cases also passed.
All gate checks, source-inventory admission, generated artifacts, knowledge links,
Terraform formatting and whitespace checks passed. Evidence is outside Git in
`C:\Users\PC\AppData\Local\Temp\terragrunt-demo-sql-backup-e1-final\acceptance.json`.
The report identifies that pre-correction source and its content hashes.
Final review then found that GetObject on a missing key returns 403 without
ListBucket, which the minimal producer role deliberately lacks. The protocol
now starts with conditional Put on its new UUID key and reads back afterward;
no extra permission was added. A regression covers a store that denies reads
of absent objects. The final solution tests (104 app + 40 backup/process/SDK,
one native fact skipped in ordinary CI), separate native SQL test, source
inventory, knowledge check and whitespace/link checks passed after this fix.
The expensive historical E1 suite was not repeated after the small protocol
correction; its prior result is kept distinct from the final targeted proof.
No IAM/lifecycle implementation or frozen E1 contract changed. This is repository
evidence, not AWS provider-schema or live acceptance.

The final native SQL run at 2026-10-16T15:43:25.730514+00:00 passed and its evidence matches
the final CLI/test assembly hashes. CleanupVerified is true; only the lab's
labelled containers/volume were retired. Free root space afterward was
7651381248 bytes (about 7.13 GiB).
`sql-lab-evidence.json`, `sql-integration.log` and the final TRX under
`C:\CodexDrop\temp\terragrunt-demo-sql-backup` retain the detailed local proof.

## Approved S3/KMS component drill preflight - 2026-10-16

The owner approved a bounded component session: at most four hours, only
cnp-cert-dev/account 341936017254/us-east-1, one dedicated private/versioned
SSE-KMS backup bucket, one new backup CMK, two scoped temporary IAM roles and
synthetic local SQL data. The owner subsequently confirmed an incremental budget
of USD 10 total including the first month of retained resources (superseding
the initial USD 2 proposal). The minimum-session estimate remains approximately
USD 1.26 before taxes under its published assumptions: one CMK-month, at most
3 GiB S3 for a month, 1,000 PUT/LIST plus 1,000 GET, 1,000 KMS requests and
2 GiB outbound. This is an operator limit, not an automatic AWS spending cap.
No full DEV UP, permanent scheduler, publication or additional infrastructure
is part of this minimum session. Any necessary expansion must first explain
its resources, principal/permissions, risk and cost. Keep backup objects/bucket
and CMK after the drill; never delete an existing key or a permanent backup
merely to remove residual charges.

Preflight at 2026-10-16T15:54:10Z used AWS CLI 2.35.12 on Linux through SSH
with the existing host configuration
and attempted the read-only AWS CLI STS identity check on codex-vm, explicitly
selecting profile cnp-cert-dev and region us-east-1. AWS CLI exited 1 before
an authenticated identity could be established: the selected config profile
could not be found. This is a missing Linux authentication prerequisite, not
an IAM denial or proof of account access. No credentials/tokens were printed,
copied or transferred. No bucket, CMK, role, grant, endpoint or AWS runtime was
created or modified; no cloud resource retirement was necessary.

Result: BLOCKED_BEFORE_CREATION. The existing local SQL/native and simulated
storage evidence remains unchanged; real S3/SSE-KMS/download/restore and negative
cloud cases remain unexecuted. The bounded session has not spent AWS resource
budget. Existing retained project resources may continue their prior charges.
Resume only after supported native Linux authentication provides the named
profile; repeat STS and require the exact approved account before any mutation.
Do not solve this prerequisite by copying Windows sessions or creating another
account's credentials. Record a fresh bounded four-hour execution window when
resuming under this authorization, rather than silently extending this preflight.

## SQL S3/KMS component qualification - 2026-10-16

Result: COMPONENT_ACCEPTANCE_PASS, 36 consolidated component checks.
The Linux-profile preflight above was superseded by supported Windows operations,
without creating another login or transferring AWS credentials. Windows profile
cnp-cert-dev verified account 341936017254 and human cnp-cert-admin; region was
explicitly us-east-1. AssumeRole credentials lived only in Windows child-process
memory, with 900-second sessions and roles bounded to 3,600 seconds. The existing
profile's public CA bundle was applied to role-authenticated Windows children;
TLS validation stayed enabled. SSH carried only public metadata and synthetic
backup/ciphertext bytes, never AWS tokens, .aws files or SQL passwords.

The temporary operator harness stayed outside Git. It used the actual production
NativeSql and local Protocol backup on codex-vm, actual S3Store/Protocol.Check on
Windows, and AWS CLI conditional PUT/versioned GET for cloud transport. This is
real component integration, not execution of the monolithic co-located CLI or an
installed EC2 service. No product source, Terraform, frozen E1/E2/E13/lifecycle
contracts, persistent access keys or existing IAM/key policies were changed.

Confirmed: Express 16.0.4265.3 COPY_ONLY/CHECKSUM/HEADERONLY/VERIFYONLY with a
backup-only login (sysadmin=0, CREATE ANY DATABASE=0); two distinct native backups;
real SSE-KMS conditional object writes with ExpectedBucketOwner and actual SHA-256
readback; backup/manifest VersionIds; download of the first exact version after
the second backup; isolated restore/CHECKDB and the known first row; real decrypt
of restored synthetic ciphertext with the original text key; refusal of existing
restore target and hash/native rejection of a truncated copy. The malformed
HEADERONLY result failed closed with InvalidCastException; the harness originally
caught too narrow an exception family and was corrected, without product changes.

Actual production checker states MISSING, MAINTENANCE, UNKNOWN, STALE and HEALTHY
passed. STALE used an explicitly authored old-timestamp fixture; no two-hour
wall-clock monitoring or notification delivery is claimed. IAM negatives passed:
producer List/Delete, observer Put, outside-prefix Put, wrong/missing SSE-KMS key,
missing conditional header, overwrite (PreconditionFailed), missing version and
session-policy-denied KMS Decrypt. Missing-version GET returned AccessDenied under
the scoped permissions; a positive exact-version control passed. No deletion
probe targeted a retained backup or version.

Retained resources (outside DEV runtime teardown):

| Resource | Exact identity |
| --- | --- |
| Private versioned S3 bucket | `terragrunt-demo-sql-backup-341936017254-fa48a32dc9` |
| Lab prefix | `terragrunt-demo/dev/sql-backups/lab-fa48a32dc9/` |
| Backup CMK | `arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced` |
| Backup alias | `alias/terragrunt-demo/dev/sql-backup-fa48a32dc9` |
| Existing text key, used without policy changes | `arn:aws:kms:us-east-1:341936017254:key/50d3fe36-8128-4d09-ac13-8f5536a230a7` |

S3 retains six objects totaling 9121293 bytes: two genuine backup/
manifest pairs and one clearly labelled old-timestamp checker fixture pair.
Current expiry is two days and noncurrent expiry two further days, with eventual
processing; this is not a two-day erasure guarantee. No cloud backup/key was
deleted. Both exact td-sql-lab producer/observer roles and inline policies were
removed; new-CMK role-use statements were removed, keeping exact human key-policy
administration for future authorized recovery. Post-cleanup IAM readbacks returned
NoSuchEntity and key/bucket configuration readbacks passed. Synthetic Docker
containers/volumes and local .bak/.bin data were retired; existing windrose SQL
remained running. Logs, policy documents, receipts and hashes remain privately in
`C:\CodexDrop\temp\terragrunt-demo-sql-cloud-fa48a32dc9`.

The initial malformed KMS-tag request created no CMK (reconciled by exact unique
description); its temporary roles were removed. Subsequent recoverable harness/
trust/negative-expectation fixes reused the same retained bucket and CMK. Focused
continuations uploaded no additional backup data. Prior attempt reports are kept,
and final traffic counters describe only their own continuation, not total usage.
The final evidence binds production assembly SHA-256 `296e9551d29ec6ee457cea3b5c93e65dc71b068475fbf9261215025ef423c472`.

The retained-resource session ran 2026-10-16T16:16:41.044316+00:00 through
2026-10-16T16:29:19.897003+00:00, within four hours. Approved incremental budget is USD 10
including the first month, not an automatic AWS cap. Conservative first-30-day
estimate remains USD 1.2574 before taxes using the approved upper bounds, despite
actual retained data being only about 8.70 MiB.
Residual new-CMK storage is approximately USD 1/month plus remaining S3/API use;
existing project baseline charges are separate. No paid runtime was created.

Hourly backup while UP, two-hour stale threshold and 2+2-day expiry are accepted
lab values, not installed scheduling or guarantees. RPO <=70 minutes conditional
on hourly success/<=10-minute completion, and component RTO <=30 minutes remain
unmeasured objectives. Cross-AZ/EC2 recovery, app /ready and POST/GET, EC2-role
installation, independent-host notification and full original DEV qualification
remain outside this drill. Future restore needs a separately authorized scoped
role/key-policy binding; retained data is not an automatic access grant.

## SQL backup service local qualification - 2026-10-16

Result: LOCAL_SERVICE_COMPONENT_PASS. Owner-authorized source/scripts/templates,
KDD and local commit only; no AWS calls, deployment, host service installation,
push/merge, credential transfer or persistent permissions change. Windows Git
owns the existing linked `C:\CodexDrop\terragrunt_demo` checkout; Linux validation
uses `/mnt/hgfs/CodexDrop/terragrunt_demo` over supported SSH codex-vm with explicit
Windows SSH config, BatchMode and StrictHostKeyChecking=yes. No WSL or trust change.

Evidence directory: `C:\CodexDrop\temp\terragrunt-demo-sql-service-20261016`.
FinalTestResults records 104/104 app tests and 51/51 backup offline tests (one
native fact intentionally skipped there). host-tests.log records 12/12 Python
fixtures in a pinned official Python container, network=none and source read-only.
Coverage includes two accelerated activations, lock exclusion, waiting inhibit,
explicit resume, failed/no-space/not-ready stubs, timeout UNKNOWN fencing,
secret-output sentinel, permissions/links, deterministic archive, traversal/drift
refusal and unprivileged staging-only writes in the disposable container.

The separate native fact passed on real SQL Express 16 with no published ports,
fresh labelled private volume, and actual SQL UID/GID 10001/10001. A dedicated
verifier was denied before granting CREATE DATABASE in master, then successfully
verified backup headers/checksums with sysadmin=0, dbcreator=0 and source SELECT
denied. Backup remained db_backupoperator; isolated restore still used its separate
administrative lab context. Existing restore/CHECKDB/known-row/no-overwrite/
truncated-file/source-preservation checks passed. The first verifier fixture
attempt reached those assertions but failed DROP LOGIN because client pooling
held the connection. Disabling pooling for its disposable logins fixed fixture
cleanup; the final run passed. Both attempts retired their owned resources.
`sql-lab-evidence.json` records TestExitCode=0, CleanupVerified=true, CLI assembly
SHA-256 `41f257b11fdad466e6bee5317ef556cebabe35bd8c42d65bb4f98a42b00e0799` and test
assembly `c5975ca47f172b98cd92b8a304a25333306298eaebe1d6e5c9df4ec5ced6e047`.
Existing windrose-sql stayed running and untouched.

publish.log records SDK 10.0.402 self-contained linux-x64/runtime 10.0.13 publish.
real-package-evidence.json records 241 files, default plan without writes,
STAGED_NOT_ENABLED then ALREADY_INSTALLED in a temporary root, and actual apphost
cloud-preview exit 0. systemd-static-evidence.json records static unit verification
only in a temporary root, no manager and no timer activation. The fixture's
placeholder nobody user produced a static safety warning; the proposed real unit
uses the existing SQL mssql identity. Real host ownership and LoadCredential/boot/
hourly behavior are not qualified by that static check.

Cleanup's S3 proof is covered by offline protocol/store fixtures, with no new live
cloud exercise. The earlier 36-check S3/KMS component record remains historical
and its retained bucket/key are untouched. No new AWS cost was incurred by this
local increment; no fresh cloud resource or access claim is made. Real IMDS role,
SQL grants/credentials, installed timer, observer notification and full co-located
EC2 CLI remain the next installation boundary. RPO/RTO remain unmeasured.

## SQL EC2 installation preparation - 2026-10-16

Result: SOURCE_PREPARED_AWAITING_GROUPED_APPROVAL. No AWS resource, role, policy,
credential, SQL host/login, endpoint or timer was installed/modified. Windows AWS
CLI 2.24.25 with explicit cnp-cert-dev/us-east-1 read account 341936017254 and
cnp-cert-admin. Current EC2/ASG/ECS/SSM/endpoint inventories were empty; only the
default VPC exists. Retained bucket versioning/SSE-KMS, enabled backup key, six
old object versions, the SQL role/profile and existing secret metadata were
re-read without any secret value, backup-body or Terraform-state download.

External evidence: C:\CodexDrop\temp\terragrunt-demo-sql-ec2-20261016.
aws-readonly-snapshot.json records policy/lifecycle before documents, identity,
AMI candidate and public AWS Pricing GetProducts quotes: Linux t3a.small 0.0188/h,
t3.micro 0.0104/h. The generated review packet records payload hashes, exact
operational-prefix scope, retained-resource preservation, four-hour session and
the shared USD-10 boundary. No actual remaining budget or live installation is
inferred from those reads. [Full review](../../operations/sql-backup/EC2-INSTALL-REVIEW.md).

The pinned existing Python container runs the entire SQL host/review suite offline
with source read-only and network=none. The 29 fixtures cover the prior host/package
contracts plus default no-access credential planning, exact instance-role guard,
root-only files in a temporary container root, SQL input bounds, uncertain failed
bootstrap receipt/no replay, policy/lifecycle preservation, prefix scoping,
default VPC refusal, exact package digest and cost-envelope refusal. The first
new fixture exposed an incomplete fake installed-unit layout; the install-unit
precondition and fixture were corrected. No real SQL/secret call occurred.
Existing native permission proof and 104 app/51 CLI tests belong to b036141 and
were not rerun merely for these Python-only changes.

Access Analyzer ValidatePolicy checked the candidate identity policy, bucket
policy and generic KMS resource policy, creating no analyzer or attachment.
There were no ERROR or SECURITY_WARNING findings. One identity and three bucket
warnings flag literal '*' under exact s3:if-none-match equality, including the
preserved original bucket statement; these are intentional exact-header checks,
not wildcard matching. KMS policy had no findings. This is static policy analysis,
not installed IAM/KMS/IMDS behavior or an authorization grant.

No additional image pull, SQL container or SDK installation was needed; only the
cached Python image ran. codex-vm had about 7.2 GiB free initially and existing
windrose-sql remained active. The reviewed package uses the already qualified
self-contained CLI; real role/SQL/SSM bootstrap, systemd LoadCredential behavior
and two real hourly activations await the approved EC2 session.

## Approved EC2 backup execution preflight - 2026-10-16

Result: BLOCKED_BEFORE_BILLABLE_RUNTIME_CREATION. The owner gave a verified
thumbs-up to the exact grouped installation/qualification/four-hour retirement
request at 2026-10-16T22:37:21Z. This approved the 8009b21 packet under the existing
shared USD-10 limit, not another budget. Execution preflight began at 22:38 UTC.
No runtime billing-start or four-hour deadline was established because no runtime
resource was created. Ordinary read/request charges on retained services are not
a zero-cost claim. No IAM/KMS/bucket/network/SQL/credential installation occurred.

Native Windows Terraform 1.13.4 and AWS CLI 2.24.25 were available. A fresh E16
session initialized all five existing runtime roots successfully using the
retained TerragruntDemoDevOperator and a public same-profile role config.
Identity/backend/E2-idle checks passed. Windows-native execution avoided WSL and
any Linux credential handoff. The requested fresh bootstrap-network-plan then
failed at global Terraform state pull, before saving a new plan binary or apply.
There is no fresh approved plan to replay and no partial cloud apply to repair.

Before billable creation, the existing E16 retirement branch was also exercised
read-only for SDC attempt 05fc796a-03ae-5e11-8d3b-64a61d144d5d. Its original attempt
still has no terminal observed/reconciled object; the bound plan/attempt hashes
passed the existing historical guard, which then required a new session-bound
owner-disposition record. The prior exception was final-DOWN-only and cannot be
copied into this session. Native EC2 read found the old exact target
i-0bc30a0862a35bd4c absent; that does not rewrite the preserved historical UNKNOWN
or supply new owner risk consent. No program-recognized disposition file or fake
terminal observation was created. The preparation had not exercised this guard;
the execution preflight found it before any resource creation.

The installed operator Part6 version v6 also still names the previous cycle's
SQL AMI/private subnet/SG. Existing original identity rebinding remains necessary
after genuine new network outputs; no permission document was altered or widened.

Automatic approval review rejected the attempted diagnostic action that would
read/store Terraform stderr/state-related output, citing possible secret or
credential content not clearly authorized in that form. That diagnostic execution
did not run and was not retried indirectly. The Terraform read failure's underlying
cause is therefore unverified. A human may inspect the local error and provide a
sanitized summary, or explicitly authorize a narrowly bounded diagnostic review;
never hand AWS credentials or state/secret values to another execution environment.

Private evidence is C:\CodexDrop\temp\terragrunt-demo-sql-ec2-live-20261016:
execution-window.json, initialize.stdout/stderr, fresh-network-plan.stdout/stderr,
retirement-guard-preflight.json and an explicitly unsigned REVIEW-ONLY proposed
historical disposition. Raw state/provider caches remain private in that fresh
session, not in Git/output. The rejected diagnostic created no diagnostic file.
Final project-scoped native reads found no demo/dev VPC or EC2 instance; EKS was
neither targeted nor changed. There is no new runtime requiring emergency deletion.

Resume requires resolving the preserved historical owner-disposition boundary and
the native Terraform read failure, then fresh E16 state/plans and the already
approved scoped security/host installation. The original grouped approval remains
recorded; no full installation reapproval is requested merely for routine details.
Do not start compute while its required safe retirement path is blocked.

Coordination follow-up: an independent provider-schema probe used an empty local
configuration, no backend/state, AWS config/credentials set to NUL and IMDS disabled.
It attempted only to reuse the already installed pinned Windows AWS 5.100.0 package
under the copied readonly lock. Local init rejected that unpacked cache because it
did not match the recorded platform checksums, before schema execution. This probe
does not confirm the separate EKS task's reported local mTLS x509 failure and does
not diagnose the private Terraform state-read stderr. No lock, TLS validation,
certificate store, trust setting or AWS authentication was changed to bypass either
failure. The safe probe output is provider-schema-no-backend-probe.json in the
execution evidence directory. There is still no functioning qualified Terraform
route for this session and no runtime billing start. A Linux authentication handoff,
if chosen by the owner, must be performed by the human; this agent transferred no
tokens, credentials or .aws files.

At 2026-10-16 23:23 UTC the owner, through coordination, reported personally
disabling Norton HTTPS inspection while retaining AutoProtect. The EKS task
reported a successful Windows Terraform 1.13.4/AWS 5.100.0 schema check without
credentials/backend. ECS was authorized to revalidate preparation/plan only,
still without apply pending the historical UNKNOWN decision. The proposed fresh
E16 init/plan invocation was rejected by automatic approval review before process
creation: it classified the state-read flow and supported-CLI stderr capture as
a bypass of the prior rejected sensitive diagnostic. This is not a newly observed
Terraform/provider failure. No raw diagnostic was read, no new session directory
or runtime was created, and no Norton/TLS/trust/authentication change was made by
this agent. The existing plan's technical functionality remains unverified after
the owner's Norton change. plan-revalidation-auto-review-rejection.json records
the exact no-execution outcome. Do not route around the rejection; obtain explicit
bounded approval for Terraform's normal remote-state consumption during init/plan,
without raw diagnostic inspection, or use a human-produced sanitized plan summary.

## Local review of plan privacy and new UNKNOWN disposition - 2026-10-17

Result: LOCAL_SOURCE_REVIEW_CANDIDATE_NOT_EXECUTED. After the second tool rejection,
the owner requested continuing ECS after being told both blockers. The delegation
explicitly limited this step to local code review/edits, a new bounded UNKNOWN
disposition and human review, without another execution route or denied retry.
No Terraform/AWS command, state/denied-diagnostic read, runtime, apply, authentication
handoff or Norton/TLS change occurred in this task. The previous rejection remains
operative until human/tool review of the revised source.

The wrapper already discarded outer stderr; canonical E16 Process.run still
captured inner stderr. The local candidate adds --discard-diagnostics for native
init/UP-plan only, discards inner stderr rather than retaining it in Failure, and
emits a closed metadata summary excluding state, preview values and confirmation
strings. The wrapper is now import-safe, defaults to review-only and uses only
the existing original_dev.py init/bootstrap-network-plan route. A source digest
binds the candidate bytes but is not execution authority. No raw stdout/stderr
logs are persisted by that wrapper. Existing private Terraform plan artifacts
remain part of normal human plan review, not model-visible diagnostics.

Local AST comparison verified unchanged identity/backend/E2-idle/source/exact-plan,
apply, historical-disposition and shutdown-observation guard bodies. Tests are
hermetic/fake-process only; 68 E16 tests and five wrapper mock tests passed,
with zero failures/errors/skips and no live E16/Terraform invocation.
[The local review instructions](../../operations/sql-backup/LOCAL-PLAN-REVIEW.md)
give the exact human step and conditional command shape; do not execute it until
the tool rejection is resolved. Review digest is
0b84d5e8dde0939400e08b385a4a9e396bbff363df2e1d536e27a086897ebe16.

A fresh local disposition for the current ECS backup attempt records the owner's
continuation in the explained context and the explicit instruction to record it.
historical_result remains UNKNOWN. It is bound to the existing local session/config
and a digest referencing prior native metadata; no fresh cloud observation is
claimed. The old authorization was not reused and no journal/outcome was modified.
The companion provenance explicitly denies apply/deletion authority. A fresh
execution configuration needs an exact technical binding within this same approved
component scope; this is not permission for another session or a waiver of
fresh native checks, E2/E13/ASG/controller/queue guards or SQL-loss confirmation.

Evidence bundle: C:\CodexDrop\temp\terragrunt-demo-sql-ec2-local-review-20261017,
including both diffs, source hashes, new UNKNOWN disposition/provenance, and a
non-sensitive reference to the previous native observation. Program-shaped
decision/evidence files are local under the existing session directory; they
do not make that old session/source revision execute-ready. Runtime billing start
and retirement deadline remain unset. No EKS resource or retained backup changed.

## Source-only state risk assessment - 2026-10-17

The owner requested determining from Terraform source whether state should contain
secrets before any further access. This phase read only code, bounded Git history,
KDD records and public pinned-provider source: no current/historical state, private
plan or denied diagnostic was opened, and no Terraform/AWS command ran.
[The assessment](../../operations/sql-backup/STATE-RISK-STATIC-REVIEW.md) concludes
with high source-based confidence that current global/runtime states should not
contain secret values. Global consists of network/monitoring metadata and exact
published role/profile references; SQL template parameters are secret ARNs, with
actual values fetched on EC2 outside Terraform. Current ECS inputs are public
environment metadata/reference injection; secret values are bootstrapped outside
Terraform. No value-bearing resource/data path was found in 83 current source
files. sensitive=true and S3 encryption are not treated as proof of absence.

The scope matters: E16 network-only prepare still reads all five current runtime
states internally, not only global. Shared/secrets/security state and historical
versions are not in that read path. Historical source 9aa2f0f really used
random_password results and aws_secretsmanager_secret_version.secret_string for
SA/app passwords and DB connection string; if applied that source would persist
them. Those constructs are gone by f8c948c and the known c80257b real-UP source.
The documented destroyed legacy state and later zero-resource runtime states
support, but do not certify, present object contents. Current-code expectation
must remain distinct from certainty about persisted historical/current bytes.

The concrete result supports the bounded next human/tool review for internal
init/plan consumption, not another open-ended audit or a bypass of the prior
rejection. No new permission/authentication change, state access or apply occurred.

## Corrected plan admitted; execution result - 2026-10-17

The owner clarified that current state was created from scratch in the new AWS
account and old repository states belonged to a different account. Historical
9aa2f0f secret-bearing code is not evidence about current state and no further
historical-state audit was pursued. Current source still supports the expected
absence of secret values; no certainty about undisplayed bytes is asserted.

After the explicit new authorization, the normal tool review admitted the revised
wrapper with review digest 0b84d5e8dde0939400e08b385a4a9e396bbff363df2e1d536e27a086897ebe16,
source commit 11f1e9eb3392f66f2f639328148df58434e74dd0. One native E16 init/network-plan
invocation ran with internal current-state consumption only, no standalone state
export/history read, stderr discarded at both boundaries and metadata-only output.
This was admission of corrected reviewed code, not an alternative route around
the former rejection. No apply, IAM/network/runtime/Norton/TLS change or credential
transfer occurred.

The invocation exited 1 with LOCAL_REVIEW_CANDIDATE_FAILED. Unlike the previous
attempts, this is an execution failure after admission, not a tool-review denial.
Raw diagnostics were discarded as requested and were not recovered/re-read.
Existence-only local metadata shows all five backend metadata/provider executable
directories, but no generated global variables, no plan directory/binary/review,
no sanitized plan summary and no apply-attempt marker. These observations do not
prove which internal command failed or its cause; no mTLS/checksum/IAM cause is
asserted. There is no valid plan ID, plan hash or change count to approve yet.

Evidence: C:\CodexDrop\temp\terragrunt-demo-sql-ec2-reviewed-plan-20261017,
owner-state-provenance.json and execution-result-metadata.json. The wrapper also
suppressed the fixed failing-action label because its outer error allowlist
accepts only uppercase strings; the exact failed action cannot be recovered from
the available safe result. Any next diagnostic change should preserve only a
fixed init/network-plan stage and exit code, never raw stderr or state values,
and receive its own bounded review before another live invocation. No retry or
different route was executed after this result. Runtime billing start/deadline
remain unset; there is no new runtime to retire or plan ready for deployment.

## Fixed step result after admitted retry - 2026-10-17

The owner authorized the minimal fixed-step/integer exit metadata correction and
the same bounded init/network-plan invocation. Commit 4738093abf1b5557cacdef171d4f29ded6484e47
was clean; review digest e649aed37ae4739a8162d93832c9b2b3a7d3e107751fb5da58fb97f320956062
bound the wrapper and both E16 source files. All 71 E16 hermetic tests, seven
wrapper mocks, source-inventory verification and current KDD links passed.

Normal tool review admitted one invocation. It reported E16_INIT exit 0, then
FAILED / GLOBAL_TERRAFORM_STATE / exit 1. The canonical source locates this at
global `terraform state pull`, before `terraform show -json`, variable generation
or plan creation. This is a technical execution failure, not a review rejection.
No stderr was captured or recovered; no current/historical state or preview was
displayed. Existing internal current-state consumption was the only state route.

Existence-only metadata found all five backend metadata/provider executable
directories, no generated variables, no plan directory and no plan summary.
There is no plan ID, hash or change count to approve. No apply or runtime creation
occurred; billing start and runtime deadline remain unset.

The step and exit code do not identify an IAM, TLS, provider checksum or backend
compatibility cause. None is claimed. The material prerequisite is to resolve
the native Terraform/backend state-pull failure through a separately reviewed
privacy-preserving diagnosis; a blind rerun, manual state export, guard relaxation
or infrastructure apply is not supported by this evidence. No further live
invocation or raw diagnostic fallback was attempted.

Evidence: C:\CodexDrop\temp\terragrunt-demo-sql-ec2-step-plan-20261017,
execution-result-metadata.json. The prior UNKNOWN remains unchanged.

## Native runtime provider-lock repair - 2026-10-17

The authorized in-memory diagnostic classified the global state-pull failure as
PROVIDER_LOCK_CHECKSUM_MISMATCH, not a remote-state digest mismatch. Exact-profile
STS verified the DEV operator; S3 HEAD verified the current global object (620
bytes, AES256). No raw stderr/state was saved or displayed. Terraform 1.13.4 on
windows_amd64 rejected the installed package against the existing lock.

Official `terraform providers lock -platform=windows_amd64 -platform=linux_amd64`
completed the five identical DEV runtime AWS locks, retaining version 5.100.0,
constraints and every old hash, adding only origin-verified h1 entries. The origin
packages were reported signed by HashiCorp. Isolated no-backend readonly init and
provider-schema loading both passed; no IAM/TLS/backend change was needed. Source
inventory was refreshed only for those five locks. Evidence: lock-completion-metadata.json
in C:\CodexDrop\temp\terragrunt-demo-aws5100-native-lock-20261017.


## EC2 backup trial and offline retirement regression - 2026-10-21

[The dated evidence](e16-ec2-backup-trial-20261021.md) records real EC2-role
manual/05:00/06:00 backup success, bounded bootstrap recovery and PARTIAL/BLOCKED
network retirement. It does not qualify cross-AZ restore/RPO/RTO or unattended
bootstrap, nor erase the 13 residual resources or retained AWS costs. Runtime,
temporary grants and removable overlays were independently checked at closure.

`test_retirement_preflight.py` uses actual checked-in legacy operator documents
as the negative fixture for the two omitted companion resource classes. Focused
hermetic cases cover partial correction, separate Allow statements, wrong
action/account/region, Deny, unscoped resource stars, wrappers, input preservation
and the invariant that structural coverage never proves live authorization.
It runs through the existing accidental-I/O audit guard: no AWS, Terraform, VM,
socket or child process. These are offline preflight diagnostics, not a new
permission gate/certificate or live IAM proof. No policy or limit was changed.


## Isolated SQL/API cross-AZ recovery preparation - 2026-10-21

Baseline c435eac preserves V1 and the October 21 backup acceptance/retirement.
The morning PARTIAL/BLOCKED outcome above is historical: the separately approved
13-object evening closure completed, with five empty runtime states and no locks;
see the residual-only follow-up in the [trial record](e16-ec2-backup-trial-20261021.md).

The [recovery packet](../../operations/sql-backup/recovery/RUNBOOK.md) creates no
cloud resource during preparation. `prepare.py` renders a separate 20-resource
root and scoped policy additions; structural create/delete checks never authorize
creation. `host.py` defaults to plan-only. Its explicit future host actions produce
synthetic data, a fresh versioned backup, source-stop receipt and cross-AZ restore
with existing CLI CHECKDB plus real API marker/decrypt/read/write checks. There
is no generic lifecycle engine, automatic gate, timer, cloud executor or targeting.

Focused `python -m unittest -v test_recovery.py` uses fake host transports and an
audit hook rejecting sockets/processes. It checks private topology/disks, plan
scope/replacements, KMS/publisher/backend boundaries, exact companion-resource
deletes, host/AZ/time binding, marker loss/readback and deterministic safe bundles.
These are offline contracts, not a live recovery PASS. Terraform 1.13.4 schema
validation uses the cached AWS 5.100.0 Windows provider with backend disabled,
get disabled and a read-only local mirror. No AWS plan or fresh IAM simulation ran.
The provider lock reuses the October 17 completed native lock, SHA-256
901a282544168f6b5d1567b13c91e9009129a2bc0cc92bf4c934e140efdae904,
including Linux and Windows h1 entries; original project locks stay unchanged.

The initial Linux self-contained publish on isolated tracked-source copies
stopped before restore/build because Windows SDKs were 9.0.101/10.0.301. This was
resolved using an isolated workspace SDK 10.0.402 from official Microsoft release
metadata, with its SHA-512 verified; the system SDK/pin stayed unchanged and no VM
started. Both existing API and CLI published successfully for linux-x64 with
self-contained runtime 10.0.13. NuGet initially failed in sandbox TLS; the normal
HTTPS restore succeeded outside that restriction without disabling TLS validation.
No API/CLI application source changed. The deterministic real archive binds the
reviewed local package commit and every file; see the packet's local-validation.json.
Fresh cloud plans/permissions and owner cloud approval remain prerequisites. RPO/RTO are methodology only: a future
controlled marker-age bound and warm-target RTO do not prove hourly RPO or full
ECS/cold-infrastructure recovery. No new AWS/IAM/state/secret/CI change occurred.

## Native recovery getter correction - 2026-10-23

The closed `r20261023az5` trial proved creation and bounded retirement of20 owned
resources, native NAT/EIP reconciliation, empty terminal state/lock absence and
exact temporary security reversal. Source refused before DDL/API/backup at
`get_memory / SELECTED_GET_FORMAT_UNSUPPORTED`; cross-AZ recovery remains unproven.
The [dated runbook entry](../../operations/sql-backup/recovery/RUNBOOK.md#native-selected-get-cli-correction---local-2026-10-23)
records closure, package/source hashes and the native-compatible local correction.

The exact SQL16.0.4305.5-1 Microsoft package's CLI/get functions, evaluated offline
against synthetic configuration, reproduced the captured70-byte stdout hash.
The defect was dotted `get section.key` instead of `get section key`, plus omission
of its exact `key : value` formatter. Only command arguments and strict selected
value parsing changed. The error output remains rejected; memory2048, loopback,
PID/listener stability, fresh query and complete initial-environment projection
requirements and unproven consumption flags remain intact.

Three added native-protocol/source-path regressions first failed against the old
helper. The final focused suite is72 recovery/authorization/runtime tests plus27
verifier tests PASS, including negative native messages/keys/values/extra output.
No SQL engine, package installation, AWS request or new runtime artifact is part
of this offline correction. It neither requalifies the old tar nor proves native
corrected precheck, backup/restore, API or RPO/RTO acceptance.


### Native official SQL image checkpoint - 2026-10-23

The [native checkpoint](../../operations/sql-backup/recovery/RUNBOOK.md#official-image-native-qualification-checkpoint---2026-10-23)
records actual SQL2022 Express16.0.4305.5 startup/query and production getter
PASS against the exact pinned official image/package source. This supersedes
only the preceding offline-only getter limit. An explicitly adapted direct
launch configuration/process/listener observation passed; the production host
precheck refused at fresh_sql_query/FRESH_QUERY_WRONG_PROCESS. The native
SQL-reported PID was not retained and that mismatch remains unresolved. The
container does not qualify EC2 systemd/drop-ins/bootstrap, memory consumption or
recovery. All owned containers were gracefully stopped/removed, no OOM, AWS
calls or shared daemon/toolchain changes. No new artifact is qualified.


## Controlled SQL/API cross-AZ recovery with reconciled repairs - 2026-10-23

The [dated execution and local correction](../../operations/sql-backup/recovery/RUNBOOK.md#controlled-sqlapi-cross-az-recovery-and-closure---2026-10-23)
records r20261023az6: native EC2/systemd prechecks, verified backup, source SQL
quiescence, exact-version restore/CHECKDB in the other AZ, API decryption and
read/write. Warm-target RTO 142.630783 s and controlled marker-age bound 20.296562 s
include actual observations. The source needed a private staging-parent ownership
repair; restore needed in-memory Python 3.10/.NET7digit timestamp compatibility.
Original failures/STARTED markers remain preserved; DDL was not replayed.
This is controlled component proof with explicit repairs, not unmodified workflow,
hourly RPO, production workload, full ECS/cold-AZ recovery or memory enforcement.

All owned runtime resources/root volumes/ENIs were natively absent and state/lock
empty at 04:48:29UTC; exact temporary security reversal/readback at 04:48:54UTC.
Original states, az5 closure and backup retention 2+2 days were preserved; no EKS
resources or budget reset. The original aggregate USD 2 authorization is not a
billing measurement. The local host correction and seven regressions address
private-parent ownership and preserve 100 ns event ordering while accepting .NET
timestamp precision on Python 3.10. Affected suites:89Windows tests (3 POSIX skips),
27 verifier separately, all 7 focused tests on actual Ubuntu 24.04 POSIX paths.
No new artifact was published/qualified for this local correction; trial lineage
continues to bind a1e6060 and the original immutable artifact plus explicit repairs.


## New recovery artifact native component qualification - 2026-10-23

The [native component checkpoint](../../operations/sql-backup/recovery/RUNBOOK.md#new-artifact-native-local-backup-component---2026-10-23)
qualifies artifact 65c7901's actual private staging helper and published local
backup CLI against SQL 16.0.4305.5 Express/Python 3.10 from empty synthetic state.
Native checksum/SHA256 and actual seven-digit .NET timestamp ordering passed.
An explicitly manual SQL restore with the source database OFFLINE passed CHECKDB
and marker/read/write checks in the same engine. It does not execute the CLI's
remote restore or full systemd/EC2/S3/KMS/API/cross-AZ workflow. Service prechecks
refused service_state/READ_FAILED/74; guards remain intact and the finer cause is
not claimed. One harness-only hashing compatibility failure before SQL effects
and its corrected retry remain preserved. Both containers normally removed,
no OOM/force, AWS calls, builds, settings changes, archive duplication or spend.
The exact immutable artifact and native receipt/assessment hashes are in the
runbook. The measured AWS prepared-target RTO remains 142.630783 s; no hourly RPO,
production workload or whole-ECS recovery claim is added.


## Local entrypoint and backup-health completion increment - 2026-10-23

Four production host.main entrypoint contracts PASS on actual private POSIX paths
with explicit synthetic SQL/API/AWS ports: clean source/quiesce/restore, seven-digit
manifest preservation, durable failure/no replay, identity/hash/staging refusal.
The [completion checkpoint](v2-local-completion.md) binds the Page scope and exact
native/fixture/remaining acceptance boundaries.

The remote-enabled checker previously ignored local FAILED attempts when an older
remote success was recent. Three new regressions reproduced false HEALTHY before
the correction. The full backup CLI suite now has 56 PASS / 1 explicit native-SQL skip,
including five new alert-signal cases. Expected-DOWN maintenance preserves failure
evidence; a subsequent verified backup clears it normally. An independent observer
without the local attempt file still proves remote freshness only, so real producer
failure publication, independent missing/stale observation and notification remain
pending. No alarm/Sentinel/email, AWS action, deployment, publish or archive rebuild.
Artifact 65c7901 stays immutable and does not contain this later compiled health fix.
PKI/Sentinel source/package availability gates are documented without invented APIs.


## Local backup signal and release binding - 2026-10-23

The [local qualification surface](../../operations/sql-backup/README.md#local-signal-and-versioned-component-qualification---2026-10-23)
adds metadata-only build identity, a source/hash-pinned component inventory and
old-bundle/substituted-DLL rejection. An explicit read-only captured-receipt replay
invokes Protocol.Check with RemoteStorageObserved:false; it never certifies live
remote absence. Local signal JSON is bounded/sanitized, has no external delivery,
and never treats STARTED/UNKNOWN/resume as success. Existing service receipts are
the source contract; no Sentinel API or email implementation is invented. Actual
publication/output hashes and captured receipt cases remain in a separate local
qualification receipt, without rewriting old65c7901 or creating another301MB tar.


### Published corrected component and receipt qualification - 2026-10-23

Clean source b2bf8d82938e690561a85e45b3ab9e2a383413cf was locally published as
Linux-x64 self-contained .NET 10.0.13 using existing cached packages only and an
offline NuGet source list. The component has 237 files / 133344738 bytes; no application
archive was created. Its executable build-info reports that exact compiled Git
revision without config or credentials. Component DLL SHA256:
d84141e91939f41042f7cb3c0a243e9036a82a676108849da31d556b17571d88.
Versioned local manifest SHA256:
b0a98b236d25fa2d0bcc72269ac42e294276c53603f48945bc99ecfb3664c978.

The actual published Linux executable passed three replay cases through the real
Protocol.Check and local log renderer: FAILED, MISSING and STALE all produced
nonzero CLI status and ATTENTION with Delivery:NONE. Stale uses the unchanged az6
captured receipt, now older than 2 h; failed uses that actual metadata plus an
explicit synthetic local FAILED attempt; missing uses an explicit empty captured
list, not live S3 absence. Every replay says RemoteStorageObserved:false; no SQL,
API, AWS or notification call was made. Original receipts remain untouched.

Full CLI suite: 62 PASS / 1 native SQL integration skip. Nine focused Python tests cover
status/exit/maintenance/unknown/privacy and manifest/source/DLL/extra-file/payload
substitution. The real old 65c7901 tar remains unchanged and was refused with
BUNDLE_COMPONENT_MISMATCH by the current pinned component gate. Archive binding
checks actual backup payload bytes as well as declared manifest hashes. This gate
does not replace whole-bundle hygiene/inspection, IAM review or live acceptance.

The qualification tooling/doc commit may be later than the compiled component:
pin the actual b2bf8d8 source and manifest above, never infer them from latest HEAD.
The next concrete artifact packet must invoke verify-bundle before upload and
execution. Automatic AWS/CI wiring is not installed. Live producer log forwarding,
independent periodic missing/stale checking and confirmed human email/Sentinel
delivery remain open, together with unchanged full EC2/systemd/remote-restore/API
acceptance. No external email or unavailable Sentinel API was configured.


## Local ECS portfolio UI - 2026-10-23

The [local portfolio](../../portfolio/README.md) implements Product Demo,
Architecture Explorer and an evidence view without packages/build steps or AWS.
Static facts cite actual architecture/recovery contracts. Explicit DEMO/historical
labels, separate V1 NAT Instances versus az6 NAT Gateway, prepared-target RTO
limits and pending PKI/Sentinel prevent live/full-recovery claims. Messages are
synthetic and memory-only; textContent prevents markup execution. A read-only
loopback server serves only explicit asset/four source-document routes, rejects
mutation routes and blocks network connections via CSP.

Final isolated-browser run: 12 checks PASS using existing Playwright 1.64.1 and
Chrome 155.0.8059.86, no install or personal session. Covered seed/empty validation,
submit/reset/XSS text, keyboard/node/flow/topology navigation, source allowlist,
historical/pending labels, desktop/mobile screenshots and mobile overflow. No
console errors or external requests. Browser and own ephemeral loopback server
closed normally at 2026-10-23T07:03:51.285Z; no forced PID cleanup. Screenshots were
visually reviewed. Prior two receipts are preserved but not added to the count.
This is local UI evidence, not a live API/AWS/PKI/Sentinel integration, hosted
portfolio, accessibility certification or completion of the remaining Page phases.


## Bounded portfolio keyboard/provenance quality pass - 2026-10-23

The [UI acceptance checklist](../../portfolio/ACCEPTANCE.md) records 14 final browser
checks, including all three views at 320/390/768px. Fixed view-change heading focus,
skip-link versus view-history routing, accessible names/groups, invalid-input state
and status announcements. The initial repeated-mobile-navigation focus failure
and its normal teardown receipt remain preserved. Corrected final run 14 PASS;
zero external requests/console errors; browser/server closed normally at
2026-10-23T07:15:37.083Z. No new dependency, cache install, AWS or hosting.
The UI and guide now say custom repository explorer, NOT Archify-generated.
Actual Archify generation/export stays open, alongside PKI/Sentinel source access
and the remaining live/release acceptance. This is a bounded Chrome DOM/focus/
responsive check, not full accessibility or whole-project certification.


## Portable portfolio CI contracts - 2026-10-23

Ten Node standard-library tests PASS for actual source facts, DEMO/history/no-live/
non-Archify provenance, navigation/accessibility source invariants and read-only
loopback server behavior. In-memory negative cases reject external requests/assets,
false live status, removed focus/skip/status contracts; actual HTTP tests reject
mutations, unintended repo files, encoded traversal and external/malformed targets.
No DOM/browser certification is inferred; prior Chrome qualification remains separate.
The repo-hygiene source now runs the suite before existing checks with an existing
Node 20+ requirement, no installer/credential/remote execution. CI selection 35 PASS.

Reproducibility suite: 26 PASS / 1 FAIL. The unchanged existing
test_dev_prod_aws_lock_identity_and_explicit_dev_provider_selection finds differing
DEV/PROD AWS blocks in global/data/platform/apps/edge. All 14 lock files and the test
source equal base 0e08e5d; provider versions remain 5.100.0. No lock edit or skipped
test disguises this blocker. Full hygiene/hosted CI is not accepted. See the
[portfolio acceptance checkpoint](../../portfolio/ACCEPTANCE.md) for next scope.

The existing source inventory was updated only for the reviewed hygiene workflow
and new source-wiring test, retaining UNVERIFIED semantic disposition. The other
30 existing inventory findings remain unresolved; freshness hashes are not
security acceptance or permission evidence. No broad inventory refresh occurred.


## Bounded provider-lock provenance - 2026-10-23

The [exact review](e14b-toolchain-reproducibility.md#native-lock-provenance-follow-up---2026-10-23)
traces five DEV-only h1 additions to b1f5063, confirms all 15 unchanged zh values
against official AWS 5.100.0 text metadata and reproduces the Windows cache h1
without executing providers. Five exact-difference assertions PASS. The two
existing lock tests return one PASS / one equality FAIL; no validation was relaxed.
Locks, provider versions, retired sources, canonical generators and package
identities remain unchanged. Missing evidence and generator admission dependencies
are explicit; this result does not claim reproducibility is fixed. No provider
binary download, Terraform initialization, AWS, workflow or push occurred.

## NuGet dependency locks and CI/Docker restore — 2026-10-24

The four solution projects now have packages.lock.json: API, API tests, SqlBackup and SqlBackup tests. CI restore uses --locked-mode; its cache key binds locks, project files and global.json. Docker copies the API lock before locked restore and publishes with --no-restore. Pinned base identities, non-root runtime and readiness deployment contracts remain strict. ContainerContractTests now also reject removal of the lock, locked-mode or no-restore; the expected grammar was updated, not weakened.

Locks were generated with existing SDK10.0.402 and central migrated NuGet cache, using a newly created config with **no sources or credentials**. No package versions were edited or downloaded. Resolved API/backup package versions were compared with the previous qualified publications: no differences. Initial offline restore looked in the default user cache and failed with missing packages; using the known central cache resolved all four. An attempted raw NuGet.Config read was rejected by automatic review due to possible credentials; that file was never read or retried. No private configuration values are part of this change.

Actual unchanged locked restore PASS, build PASS0warnings/0errors; a temporary project copy with MediatR12.4.1→12.4.0 and unchanged lock was rejected by dotnet itself with **NU1004**. It used empty sources and left original source/lock files unchanged. This verifies the refusal path rather than relying only on command-text assertions. Local NuGetAudit=false was used solely to keep offline fixture/validation from calling advisory endpoints; CI/Docker do not disable NuGet audit. This is not a current CVE/audit result.

Managed tests using the installed Windows SDK: API107 PASS; backup62 PASS/1 intentionally skipped native SQL test. New dependency lock contracts3 PASS in WSL. Observer suite29 PASS in WSL includes root/status negatives supporting the SSM explanation. A Linux SDK was not available in WSL, no SDK was installed, and no new container build or hosted CI was executed. Prior71-test cold recovery CI qualification is unchanged, not rerun or relabelled as part of this managed validation.

Files: `.github/workflows/ci-dotnet.yml`, `demo-api/Dockerfile`, four locks, strict container tests and `.github/scripts/ci/tests/test_dotnet_locks.py`. This adds reproducibility guards; it does not publish a release, change OIDC, activate a workflow remotely or claim ECS/SQL native E2E. Remaining provider-lock provenance, Linux/container acceptance and current vulnerability findings remain separate gates. Existing historical binaries/archives are not overwritten or relabelled with new provenance.


## Native DEV extraction - 2026-10-28

Retired only E16 wrapper tests: 65 executor, 9 discard-diagnostics, 6 metadata
forwarding, and one first-deployment profile-parser method. Source remains at the
archived commit. Six companion-resource permission regressions and provider-free
S3 policy/SNS assertions moved to `scripts/tests/native_ecs` and remain in E1.
Native plan review adds foreign-scope, replacement, drift, direction and delivery
field rejection. Independent ECS, E2, E13, WP3/WP4, SQL, Sentinel and Terraform/host
validations remain. The E16-only SQL revalidation wrapper is retired.
