# Technical Plan — CD Safety Test Enforcement

Status: Finalized technical plan incorporating human review; implementation not performed.
Planner verdict: READY_FOR_IMPLEMENTATION, subject to section 14 preconditions.

## 1. Planning Context

The approved durable specification is [spec.md](spec.md), titled "Durable Spec — CD Safety Test Enforcement". It remains the source of requirements. This plan supplies implementation mechanisms and evidence paths; it does not replace, narrow, or weaken the spec.

Authority order:

1. Approved durable spec.
2. Root/scoped AGENTS.md and their authoritative KDD references.
3. Current implementation.
4. Historical material only where not superseded.

Planning inspected branch `main`, implementation HEAD `f8c948cf54ec869bc135aea8a9bf1d43e02030f5`, plus the pre-existing working-tree KDD/AGENTS/spec bootstrap. That SHA identifies the inspected implementation, **not the future implementation review baseline**. No infrastructure is assumed live. No tests, AWS operations, deployment, commits, or pushes were performed during planning.

Knowledge consulted: [root guidance](../../AGENTS.md), [Terraform guidance](../../terraform/AGENTS.md), [backend guidance](../../demo-api/AGENTS.md), [validation](../../terraform/docs/validation.md), [delivery](../../terraform/docs/deployment.md), [architecture](../../terraform/docs/architecture.md), and [decisions/limitations](../../terraform/docs/decisions-and-limitations.md). Read these progressively according to their triggers. No genuine spec/KDD contradiction was found. Baseline register statements that no first spec exists are historical sequencing statements superseded by the approved spec.

Before Executor work, a human/local checkpoint must commit the approved KDD bootstrap, AGENTS files, spec, and this plan and leave a clean working tree. Record that commit as `BASE_REVISION`; do not invent its SHA here. Record the eventual implementation commit as `CANDIDATE_REVISION`. Identify `SPEC` as `BASE_REVISION:specs/cd-test-enforcement/spec.md`. The Reviewer compares `BASE_REVISION` to `CANDIDATE_REVISION`, excluding the earlier bootstrap diff. See section 14.

Inspection found Bash harness defects: conditional scenario subshells can suppress ordinary `set -e` handling, allowing early resolver assertions or the scope output-name assertion to fail without making the scenario fail. Repairing failure propagation is necessary enforcement work. No classification fixture expectation was found to conflict with durable knowledge. If implementation exposes a genuinely ambiguous expectation, stop and report it rather than changing it to obtain green CI.

## 2. Current-State Findings

### Existing tests and dependencies

All paths below are repository-relative. The three scripts and production helpers are executable in the Git index. Tests write temporary files and must run only in a phase permitting those writes.

| Test | Execution and dependencies | Protected behavior and limits |
| --- | --- | --- |
| `.github/scripts/cd/tests/test-detect-scope.sh` | Bash, jq, grep and standard Unix tools; invokes `detect-scope.sh`, transitively `resolve-terragrunt-layers.sh` | Compares complete canonical JSON output, checks GitHub output names and summary heading. Does not execute workflow filters/conditions. Explicit failure propagation needs repair. |
| `.github/scripts/cd/tests/test-resolve-terragrunt-layers.sh` | Bash, jq, diff, grep, find and standard Unix tools; sources `.env` fixtures and executes resolver | Compares six layer/path output files. Early failed assertions can be masked by later success. |
| `.github/scripts/cd/tests/test-validate-infra-gate.sh` | Bash and standard Unix tools; sources `.env` fixtures and executes gate | Checks expected exit status and ready/blocked summary. Expected failure checks use explicit exits. Does not validate actual GitHub dependency wiring or AWS readiness. |

None is invoked by existing workflows. These tests need no AWS, Terraform, Terragrunt, .NET, Docker, credentials, or real fixture-referenced infrastructure files. Paths in fixtures are synthetic strings.

The scope golden file is `.github/scripts/cd/tests/fixtures/detect-scope/golden-outputs.json`. Its 11 scenarios are:

| Scenario | Meaning |
| --- | --- |
| `app-only` | App change without infrastructure |
| `safe-infra-only` | Safe shared layer |
| `safe-infra-plus-app` | Safe platform layer with app |
| `high-risk-managed-infra-only` | Managed data layer |
| `high-risk-managed-plus-app` | Managed apps/fargate layer with app |
| `critical-manual-only-infra-only` | Dev root needs manual handling |
| `critical-manual-only-plus-app` | Shared module needs manual handling |
| `unmapped-high-risk` | Unknown dev infrastructure becomes critical/unmapped |
| `docs-only` | Documentation-only classification |
| `prod-infra` | Production path does not become automatic dev work |
| `infra-workflow` | CD helper is workflow-related infrastructure |

Each compares complete expected outputs, including compatibility aliases and path/layer arrays.

The 12 files under `.github/scripts/cd/tests/fixtures/resolve-layers/` are:

| Fixture | Meaning |
| --- | --- |
| `app-only.env`, `docs-only.env` | Empty infrastructure input produces no routing |
| `safe-infra-only.env` | Dev shared path maps to shared |
| `safe-infra-app.env` | Platform path maps to platform |
| `high-risk-data.env` | JSON input maps to data |
| `high-risk-apps-fargate.env` | App infrastructure maps to apps/fargate |
| `root-hcl.env` | Dev root review |
| `module-path.env` | Shared module review |
| `unmapped-infra-path.env` | Unmapped review |
| `prod-infra.env` | Production path produces no dev routing |
| `infra-workflow.env`, `infra-workflow-script.env` | Workflow/helper paths produce no apply layer |

All use newline inputs except `high-risk-data.env`. The harness passes target `dev`; `prod-infra.env` tests a production path, not a production-target invocation.

The nine files under `.github/scripts/cd/tests/fixtures/infra-gate/` are:

| Fixture | Expected behavior |
| --- | --- |
| `app-only.env` | Ready with irrelevant infra jobs skipped |
| `safe-infra-app-success.env` | Ready after safe apply |
| `high-risk-managed-app-success.env` | Ready after high-risk plan/apply |
| `safe-infra-required-but-skipped.env` | Blocked |
| `plan-failure.env`, `apply-failure.env` | Blocked |
| `high-risk-apply-cancelled.env` | Blocked |
| `critical-manual-only-app.env`, `unmapped-high-risk-app.env` | Blocked |

Existing fixture semantics agree with delivery knowledge. Synthetic paths such as `demo-api/src/Program.cs` are not stale merely because the real source has a different location.

### CI and CD topology

`.github/workflows/ci.yml` handles PRs targeting develop/main and pushes to other branches; pushes to develop/main are excluded. There is no event path filter. `dorny/paths-filter@v4`, configured with `base: develop`, selects app, hygiene, infrastructure and docs scopes. Conditional reusable workflows perform hygiene, .NET/Docker, infrastructure static checks, and PR remote plans. PR plans currently target dev even for main-target PRs.

Declared check/job names include Detect CI Scope; Repo Hygiene / Actionlint • Shellcheck • Format; App CI / .NET Restore • Build • Test • Docker Validate; Infra Static Checks / Terragrunt Static Checks; Infra PR Plan / Terragrunt Remote Plan. Exact displayed check identities require actual GitHub observation. There is no universal final safety result.

`ci-repo-hygiene.yml` runs actionlint, checks top-level `scripts/*.sh`, renders task definitions, checks artifact helper contracts, and formats infrastructure in check mode. It omits the CD fixture suite. Coupling safety enforcement to it would retain the develop-push gap and unnecessary tool setup. `ci-terragrunt-manual.yml` reuses static checks and optionally remote plans; it is not automatic safety enforcement.

`cd.yml` handles path-filtered develop/main pushes. It already uses checkout with `fetch-depth: 0` and dorny against event `before` and current SHA. Its inline filters feed booleans and JSON path lists to `detect-scope.sh`. Safe layer order is shared, secrets, global, platform, edge. Data and apps/fargate are managed high-risk; root, module, and unmapped paths are critical/manual. On develop, safe apply and high-risk plan/approval/apply feed the ready gate. The gate helper is followed by AWS resource preflight. App delivery then calls `cd-demo-api.yml`, which calls `release-build.yml` and `deploy-dev.yml`. Main emits manual-promotion notices. Manual promotion and two rollback paths are separate workflows.

Existing production routing, approval gates, digest delivery, Terraform/runtime ownership, and secret separation must remain unchanged. The new check detects develop regressions; it does not redesign CD ordering or add a new deployment dependency.

## 3. Technical Design

### Dedicated workflow and stable result

Add `.github/workflows/ci-cd-safety.yml`, workflow name `CI - CD Safety`, with one stable job named `CD Safety Validation`.

- Run for PRs targeting develop and main, including ordinary opened/synchronize/reopened activity. Account for base retargeting without adding an exclusion that can skip relevant PRs.
- Run on pushes to develop. Do not add push-to-main validation as part of this scope.
- Use no workflow-level `paths`/`paths-ignore` and no job-level condition that skips the stable job.
- Use a hosted Linux runner, `contents: read`, and available Bash/jq/Git/Unix tools, with explicit dependency checks. No new test framework or dependency installer is needed.
- No AWS, OIDC, environment approval, inherited secrets, application build, or deployment invocation.
- Avoid concurrency cancellation that suppresses validation of develop pushes. The simplest choice is no concurrency group for this small workflow.
- Keep existing orchestrator and deployment filters untouched.

### Explicit history and revision contract

Configure checkout deliberately with `fetch-depth: 0`; default shallow checkout is not sufficient. Full depth is a starting mechanism, not proof every event object is present. Verify required commits and relationships, especially fork PRs and force pushes. If necessary, obtain the exact event refs/objects using read-only repository access during CI, without replacing immutable event SHAs with a moving branch tip.

For PRs, retain distinct identities for event base SHA, event head SHA, merge base, event merge/test SHA, and actual checked-out HEAD. Test the event merge revision; verify actual HEAD matches the intended tested revision. Derive the complete PR path set from merge base to event head, not the last commit. Conservatively include base-to-tested-merge differences when available to account for the exact merge tree under test. If relationships cannot be established unambiguously, run the suite rather than exempt. A checkout identity mismatch must fail the check; running tests against an unintended revision does not satisfy provenance.

For develop pushes, retain event `before`, pushed SHA, and actual checked-out HEAD. Compare the complete before-to-pushed range, not only the last commit. Treat zero, missing, unavailable, incomplete, or ambiguous history/base as RUN. Check for a shallow repository; unless completeness can be established, do not grant exemption.

Use NUL-delimited Git filenames and disable rename detection so moving a relevant file to an exempt location includes the original deletion. Check Git command exit status explicitly; no failed command or truncated/incomplete list may become an empty successful exemption. Empty diffs conservatively mean RUN. History uncertainty must result in RUN with a visible reason; an internal selector crash/malformed result must not grant exemption or a successful check.

### Conservative selector

Add `.github/scripts/cd/select-safety-tests.sh`. It is independent of production `detect-scope.sh`: the latter determines deployment scope and must not decide whether its own tests are necessary.

Default is RUN. Exemption requires complete trustworthy enumeration and every changed path to be one of:

- Root `README.md`.
- Markdown or PNG files under `terraform/docs/`.
- C# source files under `demo-api/terragrunt-demo/`.
- C# test files under `demo-api/terragrunt-demo.Tests/`.

The inspected safety helpers do not consume those contents. Do not exclude all of demo-api: its deployment template is a runtime tooling dependency. Do not exclude all Markdown globally, all Terraform documentation extensions, all tests, or unknown paths. Build/project configuration, scripts, fixtures, workflow/action definitions, and repository control files remain relevant. Treat uncertain file types or path interpretation conservatively; use no shell evaluation of filenames. If a future dependency begins consuming an exempt area, the exemption contract must be reconsidered and tested.

### Selector self-protection and suite execution

Add `.github/scripts/cd/tests/test-select-safety-tests.sh`, using the existing Bash testing approach and disposable Git histories. Execute selector tests unconditionally before selection, even when the main safety suite is exempt. Expectations for relevant categories must be independent of the selector's implementation, and include the selector, its tests, the new workflow, dependencies, unknown paths and mixed changes.

For relevant selection, execute all three existing tests as separate Bash processes, record each exit code, and attempt all three even if one fails. The suite fails if any fails. Avoid advisory checks, swallowed statuses, `continue-on-error`, and relying on `set -e` inside conditional function/subshell contexts. Correct explicit assertion/helper failure propagation in the two identified harnesses without changing production semantics.

A final result step checks actual step outcomes: selector self-tests succeeded; selection is explicit and valid; RUN means all three suites actually executed and passed; exemption means complete proven irrelevant selection. Unexpected skipped steps, missing execution, failed dependencies, malformed outputs and cancellation must not produce success. A cancellation cannot be reclassified as a passing run. An always-running summary must not overwrite a failed conclusion. Exempt runs say "suite not required", never "suite passed".

Summary/log evidence contains event, PR/branch identity, run ID/attempt, actual HEAD, all relevant event/comparison SHAs, selection/reason, and each script's execution/result. Use ordinary logs and job summaries; no large artifact system or fabricated metadata. Keep the job name constant across outcomes and events and verify its observed GitHub check identity.

## 4. Relevant Change Surface

| Area | Relevance |
| --- | --- |
| `.github/scripts/**` | Classification, layer/gate helpers, selector, tests, fixtures and future helpers |
| `.github/workflows/**` | Triggers, inline filters, conditions, needs, permissions, reusable workflow calls and result propagation |
| `.github/actions/**` | Environment/backend/resource resolution and blue/green routing; nested local actions |
| `scripts/**` | Resource readiness, deployment, rendering, artifact readers/publishers/validators and transitive calls |
| `ci/**` | Schemas and supporting validation configuration |
| `terraform/live/**`, `terraform/infra/**` | Classification input paths, layer/root/module relationships and routing infrastructure |
| `demo-api/deploy/**` and backend build/configuration | Deployment template and build-related behavior; not the narrowly exempt C# contents |
| Root/control files, AGENTS files, `specs/**` | Execution/configuration/contract changes; not exempt except root README |
| All unknown paths | Irrelevance is unproven; default RUN |

Traced dependencies: scope helper calls resolver; deployment helper calls task renderer, which reads `demo-api/deploy/task-definition.template.json`; render/publish/read/record helpers call digest/manifest/record validators; blue/green composite action calls blue/green detection; workflows call backend/resource/OIDC actions. Broad relevance includes these without maintaining a fragile positive list.

Running the existing suite on a routing/workflow change does not prove full workflow expression semantics, deployed traffic behavior, or AWS readiness. Preserve this evidence boundary; unrelated coverage expansion is not authorized.

## 5. Ordered Implementation Plan

All paths are repository-relative. No Executor step begins before step 0.

| Step | Objective and files/areas | Current to intended behavior | Dependencies | Spec acceptance criteria | Validation required |
| --- | --- | --- | --- | --- | --- |
| 0. Human/local checkpoint | KDD bootstrap, AGENTS, `specs/cd-test-enforcement/spec.md` and `plan.md` | Dirty planning baseline to clean committed BASE_REVISION | Approved finalized plan; human/local action | 9, 12; review provenance | Verify clean status, checkpoint contains all inputs, record BASE_REVISION and SPEC. Planner does not commit. |
| 1. Harness corrections | `test-detect-scope.sh`, `test-resolve-terragrunt-layers.sh` | Maskable early failures to explicit command/assertion failure propagation | 0 | 3, 4, 9, 12 | Execute baseline suites in permitted Linux environment; mutation tests against disposable copies demonstrate each failure propagates; expectations unchanged |
| 2. Conservative selector | New `select-safety-tests.sh` and `tests/test-select-safety-tests.sh` | No selector to explicit RUN/exempt decision with complete history handling and narrow exemptions | 0 | 1, 2, 5, 6, 7, 8 | Deterministic histories, categories, unknown/mixed/renamed/deleted paths, shallow/missing/zero base cases; self-protection expectations |
| 3. Stable workflow | New `.github/workflows/ci-cd-safety.yml` | No enforcement to independent PR/develop check, deliberate history checkout, unconditional selector tests and blocking suite | 1, 2 | 1–8, 10, 12 | Bash syntax/actionlint with authorized tools; verify event/permission/condition wiring and required history; no AWS dependencies |
| 4. Revision/result binding | Same new workflow and selector outputs | No bound result to exact tested revision, comparison identities, selection and actual per-script outcomes | 3 | 3–7, 10 | Confirm actual HEAD and step results match summaries; unexpected skips/malformed output cannot pass |
| 5. Implementation evidence | Local disposable tests; controlled PR/temporary branch; valid develop change | Predicted behavior to reproducible success/failure/selection/event evidence | 1–4 | 1–8, 10–12 | Section 7 matrix; record run URLs and SHAs; never intentionally push known failure to develop |
| 6. IMPLEMENTATION DOCUMENTATION | Narrow factual updates in `terraform/docs/validation.md` and `deployment.md` | Old entry-point descriptions to accurate implemented mechanism and explicit evidence/review status | 3–5 | 9–12; spec section 13 lifecycle | Describe implemented entry points and actual observations only; label review pending, do not declare VERIFIED invariants or update AGENTS; link evidence rather than duplicate requirements |
| 7. Candidate review | BASE_REVISION, CANDIDATE_REVISION, SPEC, candidate diff and evidence | Implementation candidate to criterion-by-criterion Reviewer decision | 1–6 | All 12 | Section 12; missing evidence remains missing; spec takes precedence over plan |
| 8. POST-REVIEW KNOWLEDGE CAPTURE | Existing KDD and optionally AGENTS, only as justified | Reviewed findings to selectively reconciled durable knowledge | Reviewer PASS only | Spec section 13; preserve 9–12 | Section 13; keep review evidence tied to candidate and capture diff separately |

External governance verification is a separate evidence activity in step 5/7 when access is available. Lack of access must be reported, not disguised as implementation. Steps 5–7 may iterate to resolve failures; knowledge capture remains after PASS.

## 6. Acceptance-Criterion Matrix

The criterion descriptions below are an index, not replacements for the full normative wording in spec.md section 9.

| Acceptance criterion | Planned implementation mechanism | Planned evidence |
| --- | --- | --- |
| 1. Relevant logic triggers execution | Default RUN selector and independent events | Relevant helper change produces actual suite execution at recorded SHA |
| 2. Tests/fixtures/dependencies trigger execution | Non-exempt broad surface and unknown-path default | All fixture/test paths covered locally; fixture/dependency representative PR runs |
| 3. Deliberate failure fails CI | Corrected harness propagation and blocking named check | Controlled failing fixture on PR/temporary branch; failed CD Safety Validation; never intentionally broken develop |
| 4. Passing suite succeeds through execution | Require successful actual execution of all three scripts | Restored/final passing run with each script's result and exact revision |
| 5. Normal PR path validated | PR targets develop and main | Actual relevant PR runs targeting both branches |
| 6. Develop changes validated | Dedicated push-to-develop event | Relevant valid change reaches develop; automatic suite runs and succeeds at exact pushed SHA |
| 7. Proven unrelated changes can avoid suite | Narrow all-path exemption policy with complete history | Local backend C#/docs cases and actual unrelated PR with explicit exemption; selector tests still execute |
| 8. Trigger does not trivially omit safety changes | Default RUN, unconditional selector tests, full diff, no event path exclusions | Surface/self-change/unknown/mixed cases; missing/shallow history runs; workflow-only representative evidence |
| 9. Test changes justified by durable contract | Harness repair preserves expectations; stop on ambiguous semantics | Diff rationale tied to spec failure enforcement and durable delivery behavior; any later fixture correction separately justified |
| 10. Stable required-check-compatible status | Unconditional stable CD Safety Validation job and final outcome validation | Same observed check identity across PR outcomes and exemption; no skipped-job success substitution |
| 11. External enforcement verified or reported outstanding | Separate governance verification | Actual settings evidence or explicit outstanding external configuration action |
| 12. No unrelated functional change | Bounded implementation and fixed checkpoint | BASE_REVISION to CANDIDATE_REVISION diff and Reviewer scope assessment; no bootstrap diff mixed in |

## 7. Evidence Plan

### Local deterministic evidence

Run only in an authorized implementation environment, following validation.md. Existing tests create temporary outputs. Preserve executable modes and use Linux-compatible line endings. No AWS, .NET build, Terraform init/plan, Docker build, or dependency installation is needed for these tests.

- Execute the three existing suites and retain actual results. Do not infer success from inspection.
- In disposable copies, corrupt first/middle/last resolver expectations, a scope canonical value, the scope output-name behavior, and a gate expected exit. Verify each makes its test fail. Restore copies; do not commit mutation artifacts.
- Distinguish a passing negative gate fixture (expects blocked behavior) from an intentionally failing safety assertion. Only the latter proves CI failure propagation.
- Exercise selector PR histories spanning multiple commits and push before-to-after ranges; do not rely only on path arrays detached from Git history.
- Test both PR targets, base/head divergence, exact merge identity handling, multiple commits per push, additions/deletions/renames/type changes, relevant-to-exempt moves, mixed changes, every existing fixture/test category, new unknown paths, and filenames with spaces/unusual characters.
- Create disposable shallow clones/history truncation scenarios where reasonably possible; exercise absent base/head objects, unavailable merge base, zero before, ambiguous comparison, and empty diff. Each uncertainty must RUN rather than exempt. Checkout identity mismatch must fail.
- Test the enforcement selector itself and its tests/workflow as relevant. Mutating the exemption policy must cause an independent selector test failure, even if the altered policy would exempt the main suite.
- Test final-result handling for failed selector tests, invalid output, missing/skipped relevant suite, and failed suite process. Record actual command exit codes.
- Run appropriate Bash syntax and actionlint checks with available/authorized tooling. Inspect the bounded diff; no automatic dependency installation or unrelated formatting.

### GitHub Actions evidence

Record event, run URL/attempt, PR target or pushed branch, base/head/merge/push identities as applicable, actual tested HEAD, selection reason, per-script logs/results, and observed check name/conclusion. Label experiment revisions separately from CANDIDATE_REVISION. Re-run final passing candidate after any functional correction; earlier success at another SHA is not candidate proof.

| Experiment | Required observation |
| --- | --- |
| Relevant helper change in PR to develop | Automatic suite execution |
| Relevant change in PR to main | Automatic execution through normal promotion path; stable named check |
| Fixture-only/dependency representative change | Appropriate suite executes |
| Workflow-only representative change | Enforcement workflow still starts and tests execute |
| Controlled deliberately incorrect fixture on temporary PR branch | Relevant selection, actual test failure, named check failure; do not merge the failing revision |
| Restore failing fixture on that branch | Actual suite success at the restored revision |
| Backend C#-only or docs-only PR with otherwise unrelated diff | Selector tests execute; main suite explicitly exempt; stable check succeeds without claiming suite passed |
| Relevant valid change reaching develop | Push event automatically executes suite; actual HEAD equals pushed SHA; successful validation |

**Never intentionally push or merge a known failing safety case into develop.** Failure propagation is proven in the controlled PR/temporary-branch experiment and disposable local mutations. Develop coverage is proven with a relevant valid change. This split proves both required behaviors without deliberately breaking develop. A temporary branch push without a PR is not sufficient by itself because this design has no general working-branch push trigger.

For an unrelated PR experiment, the complete PR diff must be unrelated relative to its base. An implementation branch still containing the new workflow is relevant even if its last commit only edits documentation. Arrange the experiment against a base containing the mechanism; do not manufacture exemption by inspecting only the last commit.

Publishing/merging evidence changes requires the execution phase's normal authorization. Before any evidence push, inspect all existing workflow effects. Prefer a valid fixture/helper-only develop change: current CD classification treats it as workflow infrastructure without app or apply layers. Do not push broad app/infrastructure changes solely to collect evidence or allow experiments to trigger AWS work. If safe remote execution is unavailable, report CI evidence pending rather than claiming completion. No persistent bypass toggle or deliberately failing fixture belongs in the final candidate.

### External GitHub governance verification

Verify when access permits, otherwise explicitly list outstanding actions:

- Main requires the observed CD Safety Validation check from the expected Actions source.
- Normal merges are blocked while required validation fails or is missing; accurately report bypass/direct-push/admin exceptions.
- Required-check identity matches actual displayed checks; no other workflow produces a conflicting name.
- Determine fork approval/Actions policy constraints and whether merge queue is actually used.
- If merge queue is active, account for and validate `merge_group` before claiming compatibility with that path. Do not enable/configure a queue as part of this feature.

The spec permits external branch protection to remain an explicitly outstanding configuration action. Repository code alone cannot prove it. No separate push-to-main run is required by this plan.

## 8. Bypass / Failure Analysis

| Failure mode | Prevention or containment |
| --- | --- |
| Positive trigger list forgets fixtures, helpers or future files | Default RUN outside narrowly proven exclusions; category and unknown-path tests |
| Workflow-level paths suppress required result | No workflow path filter; stable job starts for required events |
| Selector exempts its own change | Selector validation always runs; independent expected relevant paths include selector, tests, workflow |
| Existing CI excludes develop or CD filter misses a change | Dedicated event configuration independent of both orchestrators |
| Incomplete history yields empty/partial paths | Explicit full checkout plus completeness checks; uncertainty RUN; never silently exempt |
| PR last commit omits earlier relevant edits | Complete PR comparison using exact base/head relationship |
| Push contains several commits | Complete before-to-pushed range |
| Rename into exempt directory hides relevant origin | No rename collapsing; inspect old deletion and new addition |
| Script/parser failure is treated as false | Explicit valid selection required; internal errors cannot grant exemption/success |
| Conditional job/step skips suite but reports acceptable status | Unconditional job and final actual-outcome validation; relevant suite must execute |
| Bash harness masks early failed assertion | Explicit propagation and independent mutation evidence |
| Summary defaults claim success | Use actual exit/step outcomes; exemption explicitly differs from passing suite |
| Wrong revision or moving ref is tested | Exact event checkout verification and distinct SHA labels |
| New push cancels earlier develop validation | Avoid shared cancelling concurrency policy |
| Entire workflow removed, disabled or skipped by platform policy | Required-check settings should contain missing-result merges; verify externally; no claim every platform-suppressed run executes |
| Workflow deliberately rewritten to unconditionally succeed | Self-tests cannot make repository code tamper-proof; review and external governance remain necessary |

The design addresses accidental bypass and selection mistakes. It does not claim resistance to a writer deliberately removing both enforcement and its tests. Existing helper tests also do not prove every workflow condition or actual ALB behavior.

## 9. Implementation Risks

| Classification | Risk or resolved fact | Treatment |
| --- | --- | --- |
| RESOLVED BY REPOSITORY EVIDENCE | Offline suite has no AWS/toolchain build dependency | Keep independent lightweight workflow |
| RESOLVED BY REPOSITORY EVIDENCE | Existing CI excludes develop pushes | Dedicated develop event |
| RESOLVED BY REPOSITORY EVIDENCE | Backend tree contains deployment template | Narrow C# exemption only |
| RESOLVED BY REPOSITORY EVIDENCE | Harness failures can be masked | Fix mechanics; preserve intended expectations |
| IMPLEMENTATION RISK | Full checkout may still lack event objects, especially forks/force pushes | Verify objects/relationships; explicitly acquire history or RUN on uncertainty |
| IMPLEMENTATION RISK | PR merge SHA differs from head SHA | Distinct identity evidence; fail wrong checkout |
| IMPLEMENTATION RISK | Shell conditional semantics, filenames, line endings or executable modes | Explicit statuses, NUL paths, Linux execution and mutation evidence |
| IMPLEMENTATION RISK | Evidence pushes trigger other repository workflows | Inspect exact changes and safe event effects; no known failure reaches develop |
| IMPLEMENTATION RISK | Test execution is mistaken for full routing/deployment proof | Document helper-contract coverage limits |
| IMPLEMENTATION RISK | Bootstrap changes contaminate candidate review | Mandatory clean checkpoint and fixed BASE_REVISION |
| EXTERNAL CONFIGURATION | Main protection, bypasses, fork policy, merge queue | Verify or report unverified/outstanding; no invented assurance |

No HUMAN DECISION REQUIRED remains for the selected design. Future evidence of ambiguous intended test semantics requires a targeted stop rather than an assumption.

## 10. Expected Change Scope

### Definitely expected during implementation

- New `.github/workflows/ci-cd-safety.yml`.
- New `.github/scripts/cd/select-safety-tests.sh`.
- New `.github/scripts/cd/tests/test-select-safety-tests.sh`.
- `.github/scripts/cd/tests/test-detect-scope.sh` failure propagation.
- `.github/scripts/cd/tests/test-resolve-terragrunt-layers.sh` failure propagation.
- Narrow IMPLEMENTATION DOCUMENTATION in `terraform/docs/validation.md` and `terraform/docs/deployment.md`: describe the actual mechanism, its entry points and review/evidence status. Do not publish unreviewed conclusions as VERIFIED or permanent rules.

### Conditionally required after inspection/testing

- `test-validate-infra-gate.sh` only if execution demonstrates a harness defect.
- Additional selector/harness regression fixtures under the existing test tree, where necessary to keep meaningful deterministic coverage.
- `merge_group` handling in the new workflow only if actual external queue use makes it necessary.
- Existing fixture expectations only with a specific durable-contract justification; none is currently proposed.

### Separate, conditional POST-REVIEW KNOWLEDGE CAPTURE

After Reviewer PASS, selectively reconcile validation/deployment KDD, the completed portion of B11 in `terraform/docs/decisions-and-limitations.md`, and AGENTS guidance only if useful durable rules were established. These are not automatic pre-review implementation edits. Preserve remaining B11 gaps such as Lambda coverage. See section 13.

No production helper semantics, existing deployment workflows, application, Terraform, IAM, release provenance architecture, or AWS resource changes are expected. The current planning revision creates only this plan file.

## 11. Executor Boundaries

- Implement this spec, not unrelated backlog findings or a complete CI redesign.
- Preserve deployment classification, approval gates, digest-based delivery, secret metadata/value separation, and Terraform/runtime ownership.
- Do not turn tests into advisory checks or add a hidden AWS dependency.
- Do not implement IAM, alarms, authentication, backend, rollback, database durability, or broader release provenance changes.
- Do not add push-to-main validation without a concrete spec necessity and review of scope.
- Do not intentionally place known failing experiments on develop or main.
- Do not change spec requirements or correct ambiguous fixtures merely to pass CI.
- Do not claim external branch protection, actual CI execution, or candidate success without evidence.
- Do not promote conclusions to permanent AGENTS rules before Reviewer PASS.
- Do not begin implementation while the bootstrap/spec/plan working tree is uncommitted. Do not commit that checkpoint on the human's behalf merely because this plan describes it.

## 12. Reviewer Contract

Review against `specs/cd-test-enforcement/spec.md` directly, not only this plan. A candidate following the plan but failing the spec is not acceptable.

The handoff must identify immutable BASE_REVISION, CANDIDATE_REVISION, and SPEC. Inspect the complete baseline-to-candidate diff and confirm spec identity remains unchanged unless separately approved. For each of the 12 criteria, report the mechanism, exact evidence/revision/run, and PASS/FAIL or missing evidence. Do not grant overall PASS while required evidence is missing. Criterion 11 explicitly allows a clearly reported outstanding external action; do not falsely convert that into verified enforcement.

Review failure propagation, selector self-protection, narrow exemptions, complete history handling, exact revision attribution, all relevant change categories, stable check behavior, PR/develop event evidence, and scope preservation. Require the safe evidence split: failed controlled PR and passing relevant develop push. Check that documentation describes observation and review status accurately without premature invariants.

Experiments can have different revisions; identify them explicitly and explain how they exercise the candidate mechanism. Final candidate success must be tied to the candidate tested tree/revision, not inferred from a previous experiment. If code changes after review, affected claims need review again. Post-review knowledge capture is a separately identifiable documentation change, not a silent replacement of the reviewed candidate.

## 13. Post-Review Knowledge Capture

Lifecycle: implementation → implementation evidence → Reviewer validation against durable spec → Reviewer PASS → knowledge capture.

IMPLEMENTATION DOCUMENTATION may accurately describe the implemented mechanism in existing authoritative documents before review. Label verification/review status precisely. It must not create a second requirements document, declare unreviewed behavior VERIFIED, close durable conclusions prematurely, or add newly inferred permanent AGENTS rules.

After PASS, perform a distinct assessment of whether the work established reusable knowledge: permanent validation boundaries, required CI entry points, stable check identity, repository dependency/change-surface relationships, history fallback rules, or safety invariants future agents must preserve. Capture only conclusions justified by review and evidence. Not every helper filename, test case or workflow detail belongs in KDD.

Reconcile the existing authoritative validation/deployment documents rather than create parallel authority. Update the decision register's testing gap only to the demonstrated extent. Update root/scoped AGENTS only if a durable navigation rule or invariant is needed; prefer linking to the authoritative document over duplicating details. Keep external governance marked outstanding unless separately verified. Link actual evidence and review identity where useful. If no new durable knowledge warrants an edit, record that assessment instead of making ceremonial changes.

Keep knowledge-capture changes identifiable after the reviewed candidate so BASE_REVISION/CANDIDATE_REVISION/SPEC remain unambiguous.

## 14. Implementation Preconditions

Executor starts only when all of the following are true:

1. This finalized plan is approved, and the durable spec remains approved.
2. A human/local checkpoint commit contains the approved KDD bootstrap and related documentation, all applicable AGENTS.md files, the durable spec, and this plan.
3. The working tree and index are clean after the checkpoint; the implementation has not been mixed into it.
4. Record the checkpoint's actual SHA as BASE_REVISION in the Executor handoff. Record SPEC as that revision's `specs/cd-test-enforcement/spec.md`; optionally record its Git blob identity as well. The future SHA is intentionally not hard-coded in this plan.
5. Executor reads AGENTS, relevant KDD, spec, and plan from that baseline and verifies baseline status before edits. If repository behavior has changed materially since planning, reconcile findings before implementation.
6. Candidate and evidence revisions are recorded explicitly for Reviewer use. No bootstrap diff is included in the baseline-to-candidate implementation comparison.

This planning task does not create the checkpoint commit, stage changes, push, configure GitHub, or implement the feature. READY_FOR_IMPLEMENTATION describes technical readiness; it does not waive the clean checkpoint precondition.
