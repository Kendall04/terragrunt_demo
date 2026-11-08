# Durable Spec — CD Safety Test Enforcement

Status: Approved for technical planning  
Scope: CI/CD validation  
Owner intent: Human-approved  
Implementation status: Not implemented

## 1. Problem

The repository contains automated tests that validate important CI/CD classification, gating, and routing behavior.

These tests currently exist as repository assets but are not reliably enforced by CI.

As a result, a change affecting deployment classification, safety gates, routing behavior, related fixtures, or their dependencies may be accepted without proving that the existing safety behavior still works.

This creates a gap between:

- safety behavior encoded in tests
- safety behavior actually enforced by repository governance

The repository baseline identified this as an existing CI/testing gap.

## 2. Desired Outcome

Changes capable of affecting CI/CD classification, gating, or routing behavior must automatically execute the relevant safety tests.

A relevant test failure must make the change unacceptable for promotion toward `main`.

The same validation should also detect relevant regressions when changes reach `develop`, so failures are discovered close to introduction rather than only during later promotion to `main`.

The resulting mechanism should be:

- automatic
- deterministic
- visible in CI
- associated with the exact commit being evaluated
- difficult to bypass accidentally through path-filter mistakes
- lightweight enough to avoid unnecessary CI execution

Correct safety coverage takes priority over CI optimization.

## 3. Functional Requirements

### 3.1 Relevant-change validation

When a repository change is capable of affecting CI/CD classification, gating, routing, or the tests that validate those behaviors, the relevant safety test suite must execute automatically.

The implementation must determine the complete set of change categories that can materially affect this behavior.

The durable requirement is behavioral coverage, not any specific path-filter implementation.

### 3.2 Pull request enforcement

For pull requests participating in the normal path toward `main`:

- relevant changes must execute the safety tests
- any relevant safety-test failure must produce a failed CI result
- the change must not be considered valid for merge while that required validation is failing

The repository-side implementation must expose a stable CI result suitable for use as a required branch-protection check.

### 3.3 Develop validation

Relevant changes reaching `develop` must also execute the safety tests.

The purpose is early detection: a regression introduced into `develop` should become visible immediately rather than remaining latent until a later promotion toward `main`.

### 3.4 Test and dependency coverage

The validation trigger must account not only for the test files themselves, but also for repository changes that can change the behavior those tests are intended to validate.

A change must not be able to affect CI/CD safety logic while unintentionally avoiding its corresponding validation because of an incomplete trigger definition.

### 3.5 Existing test corrections

If implementation work demonstrates that an existing safety test is stale or incorrect relative to the current documented repository contract, that test may be corrected as part of this work.

Such a correction is allowed only when:

- the current durable project knowledge clearly establishes the intended behavior
- the change makes the test reflect that already-established behavior
- the correction does not silently redefine CI/CD behavior

If intended behavior is ambiguous, implementation must stop and surface the ambiguity rather than modifying the test to make CI pass.

### 3.6 CI evidence

The validation result must correspond to actual test execution for the exact commit/change being evaluated.

A successful status must not be manufactured from defaults or assumed metadata.

CI should expose enough evidence to determine:

- what commit/change was evaluated
- whether the relevant suite executed
- whether it passed or failed

Large or redundant artifacts are not required unless they provide material diagnostic value.

## 4. Branch Protection Target

`main` is intended to use production-like repository governance.

The CI result produced by this validation should be suitable for configuration as a required check before merge.

Branch-protection configuration may exist outside the repository.

Therefore:

- repository implementation must provide the appropriate stable check
- external configuration must not be falsely reported as implemented unless it is actually verified
- if branch protection cannot be configured or verified from the implementation environment, the remaining external action must be reported explicitly

## 5. Reliability Requirement

The safety mechanism must protect against the failure mode where a change to the CI/CD safety system also changes or bypasses the conditions that would have caused its tests to run.

The implementation should therefore be evaluated not only for:

> "Do the tests pass?"

but also for:

> "Can a relevant change avoid running them unintentionally?"

The chosen design must provide convincing evidence for both.

## 6. Efficiency Requirement

The validation should avoid running for repository changes that cannot materially affect the relevant CI/CD behavior.

This project is intentionally cost-aware.

However:

correctness and reliable safety coverage take precedence over reducing CI minutes.

Optimization must not introduce ambiguous or fragile exclusions.

If reliable selective execution cannot be achieved, broader execution is preferable to missing relevant validation.

## 7. Durable Constraints and Invariants

This work must preserve existing documented CI/CD behavior unless a change is explicitly required to satisfy this spec.

In particular:

- do not redesign the deployment architecture
- do not redefine classification semantics merely to simplify testing
- do not weaken existing gates
- do not convert tests into non-blocking advisory checks
- do not fabricate successful evidence
- do not introduce hidden dependencies on live AWS infrastructure for these safety tests unless the existing contract genuinely requires it

The implementation should remain compatible with the repository's single-operator and cost-aware design constraints.

## 8. Non-Goals

This work does NOT include:

- redesigning the complete GitHub Actions architecture
- redesigning deployment or rollback
- changing infrastructure behavior
- solving unrelated baseline findings
- implementing IAM improvements
- changing application behavior
- changing AWS resources
- deploying infrastructure
- creating an entirely new CI/CD safety framework when the existing tests can satisfy the requirement
- fixing unrelated test coverage gaps
- resolving external GitHub governance settings beyond what is necessary to expose the required CI check

## 9. Acceptance Criteria

The implementation is acceptable only when all of the following are demonstrated:

1. A relevant CI/CD logic change causes the safety tests to execute automatically.

2. A change to the safety tests or their relevant fixtures/dependencies causes the appropriate validation to execute.

3. A deliberately failing safety-test case produces a failed CI result.

4. A passing suite produces a successful CI result based on actual execution.

5. Relevant validation occurs for the normal pull-request path toward `main`.

6. Relevant validation also occurs for changes reaching `develop`.

7. A backend-only or otherwise unrelated change can avoid the safety suite when the implementation can prove that the change cannot affect the validated CI/CD behavior.

8. The trigger mechanism cannot trivially omit a meaningful CI/CD safety change because only the obvious test directory was considered.

9. Any modification to an existing test is justified against an existing durable repository contract rather than merely changed to make CI green.

10. The resulting CI status is stable and suitable for use as a required `main` branch-protection check.

11. External branch-protection enforcement is either verified or explicitly reported as an outstanding external configuration step.

12. No unrelated functional behavior changes as part of this work.

## 10. Required Evidence

Completion must include evidence showing:

- which repository change categories are considered relevant
- why those categories cover the behavior under test
- actual execution of the safety suite
- a successful validation case
- a controlled failing validation case
- behavior for an unrelated change
- behavior on the pull-request path
- behavior on `develop`
- the exact commit or revision associated with the reported result
- final repository diff demonstrating that scope remained bounded

Evidence should come from deterministic tests, CI execution, repository inspection, or equivalent reproducible mechanisms.

Claims such as "this should run" are not sufficient when the behavior can be tested.

## 11. Planning Boundary

This spec deliberately does not prescribe:

- which workflow file must change
- which jobs must be created
- how path selection must be implemented
- how many jobs are appropriate
- job names
- dependency graphs
- shell commands
- test-runner integration details

The technical planner must inspect the repository and determine the smallest reliable implementation that satisfies this contract.

The technical plan must not replace or weaken this spec.

## 12. Review Contract

The final implementation must be reviewed against this spec directly.

A technically correct implementation of the Planner's plan is not sufficient if the resulting repository fails any acceptance criterion above.

Review should map each acceptance criterion to concrete implementation evidence and return an explicit result for each criterion.

## 13. Knowledge Capture

After implementation and review, determine whether the work established any durable repository knowledge, such as:

- permanent CI/CD validation boundaries
- required validation entry points
- repository-specific path relationships
- safety invariants future agents must preserve

If so, update the appropriate KDD documentation or AGENTS.md guidance.

Do not duplicate implementation-specific details as durable knowledge unless future work genuinely needs them.
