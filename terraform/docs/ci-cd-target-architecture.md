# CI/CD Target Architecture

This document describes the artifact-based delivery target for the demo API.
Phase 4 made durable S3 release manifests the source of truth for app delivery.
Phase 5A hardened the delivery path by splitting OIDC roles and introducing an
environment-neutral artifact ECR repository for the final promotion model.
Phase 5B added audited rollback by manifest. Phase 5C adds the CI orchestrator
so working branches stay fast and safe while PRs to environment branches can run
remote Terragrunt plans. The dev release build still uploads short-lived GitHub
artifacts for diagnostics, but dev deploy, manual prod promotion, and manifest
rollback use the validated S3 manifest.

## Current Problem

The current app CD path combines build, push, and deploy in one workflow. That
works for dev, but it is not a serious promotion model because the build output
is not captured as a durable release contract before deployment.

Current gaps:

- App CD builds a Docker image, pushes it, and deploys it in the same run.
- There is no durable release manifest that says exactly what was built.
- If prod were wired exactly like dev, prod could rebuild instead of promoting
  an existing artifact.
- Rollback currently flips blue/green traffic to the other color. That is fast,
  but it does not necessarily mean "deploy this known previous manifest."
- GitHub workflow logs and step summaries are useful audit aids, but they are
  not the source of truth for release identity.

## Target Model

The target delivery model is build once, promote many:

1. `ci.yml` orchestrates CI. Working-branch pushes run fast local checks only;
   PRs to `develop` or `main` may run remote Terragrunt plans.
2. A release build creates an immutable Docker image and resolves its ECR
   digest.
3. The release build writes a release manifest to S3. The manifest records what
   was built, not where it was deployed.
4. Dev deployment consumes a release manifest and deploys its exact image
   digest.
5. Prod promotion consumes an existing release manifest and deploys the same
   image digest. Prod must not build or push Docker images.
6. Deployment records describe where a manifest was deployed and become the
   audit trail for environment movement.

S3 release manifests are the source of truth for deployable app artifacts.

Terraform plans are not promoted from dev to prod. Infrastructure code is reused
across environments, but plans are regenerated for each environment because live
state, resource names, ARNs, and cost posture differ. App artifacts are promoted;
environment-specific infrastructure plans are not.

## CI Orchestrator

`ci.yml` is the trigger-driven CI entry point. The focused CI workflows are
reusable implementation details:

- `ci-repo-hygiene.yml`: actionlint, shellcheck, schema validation, manifest and
  deployment-record contract checks, S3 script dry-run checks, Terraform fmt, and
  Terragrunt HCL format.
- `ci-dotnet.yml`: .NET restore/build/test and Docker build validation with
  `push: false`.
- `ci-terragrunt.yml`: static Terraform/Terragrunt checks without AWS OIDC.
  It does not request AWS OIDC permissions.
- `ci-terragrunt-plan.yml`: AWS-backed remote Terragrunt plan for PR review
  gates.
- `ci-terragrunt-manual.yml`: explicit manual entry point for infra CI. It can
  run static checks only, or an AWS-backed remote plan when requested.

Working branch pushes run only non-mutating validation. They do not assume AWS
OIDC roles, initialize the remote backend, publish S3 artifacts, push Docker, or
deploy. Their changed-file scope is evaluated against `develop` so push CI and
PR CI to `develop` report consistent app, infra, and hygiene scope.

PRs to `develop` or `main` run the same static checks. If infrastructure paths
changed, the orchestrator runs static infra checks first, then calls
`ci-terragrunt-plan.yml`. PRs to `develop` plan `dev`; PRs to `main` plan
`prod`. The job summary publishes a safe per-unit plan summary and links to a
short-lived downloadable artifact containing the full text plan.

Manual infra CI is intentionally outside `ci.yml` so workflow-dispatch-only jobs
do not appear as skipped nodes in normal feature push or PR graphs.

CI never deploys. App delivery remains in the CD workflows.

## Infra CD

`cd.yml` is also the push-driven CD orchestrator for approved merges. Infra CI
still reviews changes before merge; infra CD runs a fresh plan before every
apply and never reuses PR plan artifacts.

On merges to `develop`, safe dev layers are automatically planned and applied in
dependency order:

1. `shared`
2. `secrets`
3. `global`
4. `platform`
5. `edge`

The `data` and `apps/fargate` layers remain manual in this phase. `data` is
stateful and cost-sensitive. `apps/fargate` is runtime-sensitive because the app
release pipeline owns ECS task definition revisions, ECS service taskDefinition
updates, desired count, and ALB blue/green traffic movement.

Changes under `terraform/infra/shared`, `terraform/infra/secrets`,
`terraform/infra/global`, `terraform/infra/platform`, and
`terraform/infra/edge` are treated as safe dev source changes. Changes under
`terraform/infra/data`, `terraform/infra/apps`, or shared
`terraform/infra/modules` are treated as manual/high-risk because they can affect
stateful, runtime-sensitive, or cross-layer behavior.

If a merge contains both safe infra changes and app changes, `cd.yml` runs the
safe dev infra apply first and starts app CD only after that job succeeds. If
high-risk dev infra changed, all automatic infra apply is skipped for that run,
app deploy is blocked, and the run writes a summary telling the operator to use
the manual `CD - Terragrunt Layer` workflow.

On merges to `main`, prod infra auto-apply is still intentionally disabled.
`cd.yml` writes a summary and leaves prod changes to the manual workflow until a
future prod approval flow is implemented. Prod app promotion remains manual via
`promote-prod.yml`.

## Ownership Boundary

Terraform and Terragrunt own durable infrastructure skeletons:

- VPC and networking
- ALB, target groups, listeners, and listener rule skeleton
- ECS cluster
- ECS blue/green service skeletons
- IAM roles and policies
- Secrets Manager and KMS references
- Bootstrap task definitions used to create initial ECS services
- Scale-down Lambda and its IAM role

GitHub Actions and scripts own release movement:

- Release task definition revisions
- ECS service `taskDefinition` updates
- Desired count during blue/green deployment
- ALB listener and candidate-rule traffic switching
- Deployment records
- Environment current pointers

This boundary preserves Terraform as the owner of durable infrastructure while
keeping fast release movement out of Terraform state. The existing ECS service
Terraform module intentionally ignores `desired_count` and `task_definition` so
runtime deployment can be handled by the app CD scripts.

## Target S3 Structure

The release artifact bucket is versioned, encrypted with SSE-S3, and blocked
from public access. In the same-account demo topology the bucket is
account-scoped:

```text
demo-release-artifacts-<account-id>
```

`terraform/live/dev/shared` owns bucket creation. `terraform/live/prod/shared`
uses the same deterministic bucket name but does not create a second bucket.
The bucket is separate from the Terraform remote state bucket.

Suggested object layout:

```text
releases/demo-api/by-digest/sha256-<digest-without-colon>.json
releases/demo-api/by-commit/<git-sha>/<run-id>.json
releases/demo-api/candidates/develop/<git-sha>.json
environments/dev/current.json
environments/dev/history/<timestamp>-<git-sha>.json
environments/prod/current.json
environments/prod/history/<timestamp>-<git-sha>.json
deployments/dev/<run-id>.json
deployments/prod/<run-id>.json
```

Release manifests are immutable release identities. Environment pointers are
small records that say which release is current for an environment. Deployment
records capture the result of a specific deployment attempt.

## Release Manifest

The release manifest represents what was built. It does not contain dev/prod
deployment state.

Schema:

- `ci/schemas/release-manifest.schema.json`

Local validator:

- `scripts/validate-release-manifest.sh`

Dry-run renderer:

- `scripts/render-release-manifest.sh`

Redacted example:

- [evidence/release-manifest.redacted.json](evidence/release-manifest.redacted.json)

Important rules:

- `schemaVersion` must be `1.0`.
- `app` must be `demo-api`.
- `image.digest` must be `sha256:<64 lowercase hex>`.
- `image.uri` must be `<registry>/<repository>@sha256:<64 lowercase hex>`.
- Tag-only image URIs are rejected.

## Deployment Record

The deployment record represents where a release was deployed.

Schema:

- `ci/schemas/deployment-record.schema.json`

Local validator:

- `scripts/validate-deployment-record.sh`

Redacted example:

- [evidence/deployment-record.redacted.json](evidence/deployment-record.redacted.json)

Important rules:

- `schemaVersion` must be `1.0`.
- `app` must be `demo-api`.
- `environment` must be `dev` or `prod`.
- `imageDigest` and `imageUri` must refer to the same digest.
- `deployment.strategy` must be `blue-green`.
- `status` must be `success` or `failed`.
- Rollback records include an optional `rollback` object with selector, reason,
  previous current manifest URI, selected manifest URI, and requester.

## Rollback Model

The preferred rollback path is manifest rollback:

- Workflow: `rollback-manifest.yml`
- Trigger: manual `workflow_dispatch`
- Environment: selected `dev` or `prod`, so environment protections and secrets
  apply.
- Selectors:
  - `manifest_uri`
  - `git_sha_run_id`
  - `digest`
  - `previous_environment_history`
- Behavior:
  - reads a previous S3 release manifest,
  - validates the manifest and digest image URI,
  - deploys `manifest.image.uri` through the same ECS blue/green script used by
    dev deploy and prod promotion,
  - runs the configured smoke test when present,
  - writes a rollback deployment record to `deployments/<env>/`,
    `environments/<env>/history/`, and `environments/<env>/current.json`.

Rollback by manifest never builds Docker, never pushes to ECR, and never creates
a new image tag.

The legacy `cd-rollback.yml` workflow remains as emergency color-flip rollback.
It swaps traffic to the inactive color quickly, but it does not select a known
release manifest and does not write the manifest deployment audit record. Prefer
`rollback-manifest.yml` unless the operator explicitly needs emergency traffic
inversion.

## ECR Direction

The clean target is a shared environment-neutral ECR repository, for example
`demo-shared-demo-ms`.

Reasoning:

- Dev and prod are in the same AWS account.
- Prod must deploy the same digest that dev built.
- Environment-specific repositories require image copying or rebuilding, which
  weakens the promotion story.

Controls:

- ECR tag immutability remains required.
- Scan on push remains required.
- Deploy scripts validate and use digest-form URIs only.
- Prod deploy roles should never have ECR push permissions.

Phase 5A adds the shared artifact repository to `terraform/infra/shared`, with
`terraform/live/dev/shared` owning creation in the same-account demo. The
existing environment-specific ECR repository remains in place for transition.
`release-build.yml` can select the shared repository through the
`DEMO_API_ARTIFACT_ECR_REPOSITORY` GitHub variable after the shared repository
is bootstrapped; otherwise it keeps the current dev ECR path so existing dev CD
does not break before infrastructure is applied.

## OIDC Role Split

Phase 5A introduces these delivery roles:

- `AWS_ROLE_RELEASE_BUILD`: used only by `release-build.yml`; can push/read ECR
  artifact repositories and read/write `releases/demo-api/*` manifests.
- `AWS_ROLE_DEV_DEPLOY`: used only by `deploy-dev.yml`; reads release manifests,
  writes `deployments/dev/*` and `environments/dev/*`, mutates dev ECS/ALB
  blue/green resources, and can pass dev ECS task/execution roles.
- `AWS_ROLE_PROD_PROMOTE`: used only by `promote-prod.yml`; reads release
  manifests and dev deployment records, writes prod deployment records, mutates
  prod ECS/ALB blue/green resources, and can pass prod ECS task/execution roles.
- `AWS_ROLE_APP_ROLLBACK`: still exists for the legacy emergency color-flip
  rollback workflow. A manifest-aware rollback does not use that role because it
  also reads/writes release manifests and deployment records; until a dedicated
  manifest rollback role exists, it uses the selected environment's deploy
  authority: `AWS_ROLE_DEV_DEPLOY` for dev and `AWS_ROLE_PROD_PROMOTE` for prod.

The delivery workflows no longer fall back to the broader `AWS_ROLE_APP_CD`
role. Missing split-role secrets are hard failures so a job cannot silently run
with broader authority.

Split-role rollout checklist:

- `terraform/live/dev/shared` has been applied after the split-role changes.
- `terraform/live/prod/shared` has been applied or otherwise bootstrapped for
  the prod OIDC role.
- GitHub environment or repository secrets are configured:
  `AWS_ROLE_RELEASE_BUILD`, `AWS_ROLE_DEV_DEPLOY`, and
  `AWS_ROLE_PROD_PROMOTE`.
- `release-build.yml`, `deploy-dev.yml`, `promote-prod.yml`, and
  `rollback-manifest.yml` have been tested with the split-role secrets above.

## Workflow Phases

Phase 1: schemas, scripts, and docs only

- Add release manifest schema.
- Add deployment record schema.
- Add local validators.
- Add local release manifest renderer.
- Add repo hygiene checks for the new contracts.
- Do not change current app CD behavior.

Phase 2: generate manifest in existing CD

- Keep the existing build/push/deploy path intact.
- After image digest resolution, render a release manifest.
- Upload the manifest and a small image diagnostic JSON file as a GitHub Actions
  artifact with 30-day retention.
- S3 is not implemented in this phase; GitHub artifacts are temporary
  observability, not the final source of truth.

Phase 3: split release build from dev deploy

- Add `release-build.yml`, a reusable workflow that builds once, pushes the dev
  image to the current dev ECR repository, resolves the immutable digest, renders
  the release manifest, validates it, and uploads it as a GitHub Actions
  artifact.
- Add `deploy-dev.yml`, a reusable workflow that downloads the manifest artifact,
  validates it again, extracts `manifest.image.uri`, and deploys that digest with
  the existing ECS blue/green script.
- Keep `cd-demo-api.yml` as a compatibility orchestrator for callers.
- On `develop`, app changes build and deploy dev through the manifest artifact
  handoff.
- On `main`, app changes do not rebuild, push to ECR, or deploy prod. The
  workflow writes a clear notice that prod promotion is Phase 4.
- S3 is still not implemented in this phase. GitHub Actions artifacts are the
  temporary handoff mechanism only.

Phase 4: S3 source of truth and prod promotion

- Add the account-level release artifacts bucket to `terraform/infra/shared`.
- `release-build.yml` publishes the validated release manifest to:
  - `releases/demo-api/by-digest/sha256-<digest-without-colon>.json`
  - `releases/demo-api/by-commit/<git-sha>/<run-id>.json`
  - `releases/demo-api/candidates/develop/<git-sha>.json`
- S3 publish is blocking. If the manifest cannot be written to S3, dev deploy
  does not proceed.
- `deploy-dev.yml` reads the S3 manifest, deploys the digest recorded in
  `manifest.image.uri`, and writes deployment records to:
  - `deployments/dev/<run-id>.json`
  - `environments/dev/history/<timestamp>-<git-sha>.json`
  - `environments/dev/current.json`
- GitHub artifacts remain as diagnostics only.
- `promote-prod.yml` is manual, uses the protected `prod` GitHub Environment,
  reads an existing S3 manifest, verifies that the same git SHA/digest has a dev
  deployment record, performs prod readiness checks, and deploys the manifest
  digest if prod infrastructure exists.
- Prod promotion does not run Docker Buildx, does not build Docker images, and
  does not push to ECR.
- If prod infrastructure is not provisioned, promotion fails before partial
  deployment with readiness errors. At minimum, bootstrap the shared layer for
  the prod OIDC role before the workflow can authenticate, then bootstrap prod
  deploy layers before promotion can pass readiness.

Phase 5A: split IAM roles and prepare shared ECR

- Add `AWS_ROLE_RELEASE_BUILD`, `AWS_ROLE_DEV_DEPLOY`, and
  `AWS_ROLE_PROD_PROMOTE` policies/roles in Terraform.
- Remove Docker/ECR push permissions from the new deploy/promotion roles.
- Add the shared environment-neutral ECR artifact repository to shared
  Terraform, created only by `dev/shared` in the same-account demo.
- Add an artifact-only resolver action so `release-build.yml` no longer needs
  ALB, target group, ECS service, Lambda, DB secret, or smoke-test variables.
- Require the split-role secrets in GitHub; do not fall back to the broader
  `AWS_ROLE_APP_CD` role.

Phase 5B: rollback by manifest

- Add rollback-by-manifest semantics.
- Keep emergency color-flip rollback, but label it clearly.
- Write rollback deployment records and update environment current pointers.

Phase 5C: CI orchestration and cleanup assessment

- Add `ci.yml` as the central CI orchestrator.
- Convert focused CI workflows to reusable workflows.
- Move manual infra CI to `ci-terragrunt-manual.yml` so PR and working-branch
  graphs stay focused on their active path.
- Keep working-branch CI local/static: no remote Terragrunt plan and no AWS
  OIDC requirement.
- Keep PRs to `develop`/`main` as the remote Terragrunt plan gates for infra
  changes.
- Document the completed fallback cleanup path and keep legacy escape hatches
  explicit instead of silent.
- Document legacy path status instead of deleting tested operational escape
  hatches.

Infra-CD-2: automatic safe dev infra apply

- Add automatic dev Terragrunt plan/apply after merges to `develop` for safe
  layers only: `shared`, `secrets`, `global`, `platform`, and `edge`.
- Keep `data` and `apps/fargate` manual because they are stateful or
  runtime-sensitive.
- Run a fresh plan immediately before every apply; do not apply PR-generated
  plan artifacts.
- Make app CD wait for successful safe infra apply when both app and safe infra
  changed.
- Skip all automatic infra apply and block app CD when high-risk dev infra
  changed in the same merge.
- Keep prod infra apply manual until a protected prod approval flow is added.

## Trigger Direction

Working-branch pushes run local validation only. They must not run remote
Terragrunt plans, publish S3 manifests, push Docker images, or deploy.

PRs to `develop` or `main` may run Terragrunt plan because they are review
gates for environment-bound changes.

Merges to `develop` should eventually create a release manifest and deploy dev.

Prod promotion should be manual or protected and must consume an existing
manifest.

In Phase 4 and later, `main` app changes still intentionally do not build or
deploy. Prod promotion is manual through `promote-prod.yml` and must reference
an existing S3 release manifest by URI, git SHA/run ID, or digest.

## Legacy Path Status

- `cd-demo-api.yml`: keep. It is the compatibility CD orchestrator that calls
  `release-build.yml` and `deploy-dev.yml` for dev.
- `scripts/deploy.sh`: keep for local dev/bootstrap operations. It should not
  be used as a prod rebuild/promotion path.
- `cd-rollback.yml`: keep as emergency blue/green color flip. It is not the
  audited manifest rollback path.
- Environment-specific ECR repositories: keep during transition. Switch
  `DEMO_API_ARTIFACT_ECR_REPOSITORY` to `demo-shared-demo-ms` after the shared
  ECR repository exists and the release-build role can push to it.
