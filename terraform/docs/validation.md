# Development and validation entry points

## CURRENT CONTRACT — toolchain and coverage

CI selects Terraform 1.13.4, Terragrunt 0.93.3 and .NET SDK 8.0.x.
Terraform modules generally permit >=1.9 and AWS provider ~>5.50.
Five dev layer provider locks are tracked; dev edge/apps and prod locks are
absent. Docker bases use mutable 8.0 tags. tfsec downloads latest; action tags
and downloads are not a fully pinned/checksummed toolchain.

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

[Text handler tests](../../demo-api/terragrunt-demo.Tests/TextHandlersTests.cs)
verify encryption/persistence/decryption/pagination using doubles.
[Health tests](../../demo-api/terragrunt-demo.Tests/HealthEndpointTests.cs)
verify liveness/readiness responses and Swagger/environment behavior.
They do not prove real KMS, SQL migrations, deployment or rollback.

CD fixture tests exercise scope/layer/gate behavior, but no workflow invocation
is currently wired. Hygiene checks top-level scripts and artifact examples,
not the complete CD helper/test tree. It parses schema JSON and uses hand-written
validators; that is not exhaustive JSON Schema conformance testing.
No Lambda unit tests or comprehensive deployed rollback evidence were found.

## Working guidance

For future changes, choose checks matching the affected contract and authorized
side effects. Report what was actually run and what remains unverified.
Do not claim tests passed based on metadata defaults or old generated outputs.
For documentation-only work, inspect diff, resolve local links, and verify changed
paths; builds, dependency installs and cloud commands are unnecessary.

After changes, inspect tracked/untracked status and ensure generated files were
not accidentally added. [Decisions/backlog](decisions-and-limitations.md) records
missing coverage and reproducibility work without authorizing it.
