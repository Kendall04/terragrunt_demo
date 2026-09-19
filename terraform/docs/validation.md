# CD safety validation

## Develop integration status

This integration carries the CD safety mechanism from candidate
`9cef1cb7ea712857c947ed8e5591651122fa476a`, integrated into main at
`41c53252efc66ff86b88cb96d50b7825e88ae27d`, onto develop baseline
`b0d9780c2210b941f5d142525d8fdc5ec4c0240a`.
The seven workflow/selector/test files preserve candidate blobs and Git modes.
Documentation is adapted to develop without importing the broader KDD bootstrap.
Develop-targeting PR and actual develop-push evidence remain pending publication.
Local validation does not constitute Reviewer approval or deployed AWS evidence.

## Execution and selection

[CI - CD Safety](../../.github/workflows/ci-cd-safety.yml) exposes the unconditional
`CD Safety Validation` job for PRs targeting develop/main and pushes to develop.
There are no workflow path filters, AWS authentication, or deployment calls.
The exact event checkout is verified before accepting the result. Selector and
result self-tests execute even when the main suite is exempt.

The [selector](../../.github/scripts/cd/select-safety-tests.sh) defaults to RUN.
Exemption requires complete history and only ordinary non-executable files in
root README.md, Markdown/PNG under terraform/docs, or C# under the application
and application-test directories. AGENTS.md remains relevant everywhere.
Unknown paths, executable/type changes, empty diffs, and uncertain comparisons
run the suite. PR selection combines merge-base-to-head and base-to-tested-merge
differences; push selection compares before-to-pushed revisions. Renames retain
both origins and destinations. Checkout identity mismatch fails validation.

Required execution comprises all three scope/layer/gate suites, with individual
exit codes. Missing, skipped, or failed required execution cannot satisfy the
final result. An exemption is reported as "suite not required", not "suite passed".
Logs and summaries record event, comparison/test SHAs, run identity and outcomes.

## Local deterministic validation

Use an installed Linux-compatible Bash/Git/jq/Unix toolchain. These tests create
disposable temporary files and Git histories; they are not read-only commands.
They require no AWS, Terraform initialization, application build, or Docker build.
From the repository root, the offline entry points are:

```bash
bash .github/scripts/cd/tests/test-detect-scope.sh
bash .github/scripts/cd/tests/test-resolve-terragrunt-layers.sh
bash .github/scripts/cd/tests/test-validate-infra-gate.sh
bash .github/scripts/cd/tests/test-select-safety-tests.sh
bash .github/scripts/cd/tests/test-safety-workflow.sh
bash .github/scripts/cd/tests/test-safety-mutations.sh
```

The mutation harness corrupts disposable copies only. Its expected failures
demonstrate assertion propagation and rejection of an overly broad exemption.
Bash syntax and workflow lint checks supplement these tests when tools are
available. Do not install dependencies or run AWS-backed validation implicitly.

## Evidence boundaries

Helper tests do not establish full workflow scheduling, ALB behavior, AWS readiness,
or rollback. Actual PR and develop-push runs must identify their distinct tested
revisions and demonstrate execution. Never merge deliberately failing experiments
into develop. Preserve original candidate and integration identities separately.

This check does not gate existing CD jobs. See the
[deployment runbook](deployment.md#cd-safety-validation) for integration scope.
External required-check settings, bypass rules and merge-queue use are unverified
here; this workflow has no merge_group trigger. No GitHub settings are changed
by this integration.
