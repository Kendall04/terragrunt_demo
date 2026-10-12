# Development and validation entry points

The WP3C [internal release implementation](e1-internal-release.md) adds hermetic
adapter/authority acceptance and provider-free selective-compute fixtures.
These never constitute live AWS isolation or deployment evidence.

## CURRENT CONTRACT — toolchain and coverage

CI selects Terraform 1.13.4, Terragrunt 0.93.3 and exact .NET SDK 8.0.425.
All 14 TARGET environment/layer roots have tracked locks; the neutral security
root now has an AWS-only lock. They retain AWS 5.100.0 (~>5.50); TARGET locks
also retain TLS 4.3.0. [E14-B](e14b-toolchain-reproducibility.md) records verified
standalone tool checksums, immutable CI action identities, platform/hash coverage
and the intentional update procedure. [E14-A](e14-container-hardening.md) retains
verified .NET 8 Linux/amd64 image digests and UID 1654. Runner inputs, jq, BuildKit,
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

When application code is run outside its isolated tests, startup migrations are
enabled by default and KMS operations use the credential chain. A local API start
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
