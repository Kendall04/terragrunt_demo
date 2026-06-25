# Deployment Runbook

Use the repository scripts for bootstrap and full dev deploy operations. They set
the Terragrunt backend environment, call the staged bootstrap commands in the
right order, and avoid direct `terragrunt run --all apply` for this lab.

GitHub Actions Terragrunt CD is intentionally narrower: the `CD - Terragrunt
Layer` workflow is manually dispatched for normal infrastructure changes and
runs `plan` or `apply` for one selected layer only. It does not perform
bootstrap, write secret values, deploy application code, or run full-environment
`run --all apply`.

The recommended full dev deployment command is `scripts/deploy.sh
full-dev-deploy`. It runs base infrastructure reconciliation first, then builds
and deploys the app. This matters because state files existing in S3 only proves
Terraform has managed those modules before; it does not prove the current live
AWS resources still match Terraform desired state. If someone manually changes a
resource in AWS, such as scaling NAT ASGs to `0`, the base apply/plan phase must
run so Terraform/Terragrunt can detect and correct the drift before ECS tasks are
deployed.

## Prerequisites

- AWS CLI access through either an EC2 instance role/default credential chain or
  an explicit local profile.
- Terraform, Terragrunt, jq, and ripgrep.
- Docker installed and the Docker daemon running for `deploy-app`; the app
  deploy builds and pushes `demo-api/Dockerfile`.
- Backend naming:
  - State bucket: `tfstate-demo-<env>-<account-id>`
  - Lock table: `tfstate-locks-<account-id>`

Do not put real account IDs, bucket names, state object keys, ARNs, or full state
contents in tickets, docs, PR comments, or chat output.

## GitHub OIDC/IAM Model

GitHub Actions uses OIDC only; do not create long-lived AWS access keys for the
pipelines. The shared IAM module supports one account-level GitHub OIDC provider
owner and adopted consumers:

- `dev/shared` owns creation of `token.actions.githubusercontent.com`.
- `prod/shared` adopts the existing provider by URL lookup unless an explicit
  `github_oidc_provider_arn` is supplied.
- GitHub jobs must declare the matching GitHub environment (`dev` or `prod`) so
  the OIDC `sub` claim is `repo:<owner>/<repo>:environment:<env>`.
- CI, CD, app deploy, and rollback roles all use environment-shaped subjects
  only. Branch and pull-request OIDC subjects are intentionally not trusted.

Protect the `prod` GitHub environment before using the prod CD or rollback
roles. The AWS trust policies now scope CD, app deploy, and rollback roles to
the environment-shaped subject rather than a repo-wide wildcard. With GitHub's
default AWS OIDC subject format, a job that declares an environment emits
`repo:<owner>/<repo>:environment:<env>` rather than a branch-shaped subject, so
main/prod branch enforcement must be configured as GitHub environment protection
rules.

Required GitHub environments:

- `dev`: used by dev CI, Terragrunt CD, app deploy, and rollback jobs. It can
  remain unprotected for demo velocity, but keep dev AWS role secrets scoped to
  this environment rather than repository-wide secrets.
- `prod`: used by prod CI, Terragrunt CD, app deploy, and rollback jobs. Require
  reviewers, prevent self-review if available, and restrict deployment branches
  to `main`. Store prod AWS role secrets only in this environment.

Environment-scoped GitHub secrets:

- `AWS_ROLE_TG_CI`
- `AWS_ROLE_TG_CD`
- `AWS_ROLE_TG_CD_HIGH_RISK` in the `dev-infra-approval` environment
- `AWS_ROLE_RELEASE_BUILD` in `dev`
- `AWS_ROLE_DEV_DEPLOY` in `dev`
- `AWS_ROLE_PROD_PROMOTE` in `prod`
- `AWS_ROLE_APP_ROLLBACK`
- `INFRACOST_API_KEY` if cost comments are enabled

Environment-scoped GitHub variables for app deploy and rollback:

- `ALB_LISTENER_<ENV>`
- `ALB_CANDIDATE_RULE_<ENV>`
- `TG_BLUE_<ENV>`
- `TG_GREEN_<ENV>`
- `SCALE_DOWN_LAMBDA_<ENV>`
- `DB_SECRET_ARN_<ENV>`

Optional environment-scoped GitHub variable for the app deploy public smoke test:

- `SMOKE_TEST_URL_<ENV>`: public base URL for the deployed API, for example the
  edge `api_endpoint` output. Configure `SMOKE_TEST_URL_DEV` in the GitHub
  `dev` environment to enable the hosted-runner smoke test after dev deploys.
  If the value is a base URL, CD calls `/ready`; if the value already includes a
  readiness path such as `/ready`, `/health`, `/health/live`, or
  `/health/ready`, CD uses it as-is. When unset, GitHub app CD still waits for
  the new ALB target group to become healthy before switching traffic, but emits
  a warning and skips the hosted-runner HTTP smoke test.

Keep these values in the matching `dev` or `prod` GitHub environment. Do not
store prod role ARNs or prod resource ARNs as repository-wide secrets or vars.

Terragrunt CD no longer attaches the AWS-managed full administrator policy and
is explicitly denied from mutating the GitHub CI/CD roles or their managed
policies. Workload IAM permissions are scoped to demo workload role and policy
prefixes; `iam:AttachRolePolicy` is limited by `iam:PolicyARN` to approved demo
managed policies plus the narrow AWS-managed service baseline policies required
by this lab. `iam:PassRole` is limited to demo service roles and the AWS
services that consume them.

Normal GitHub CD should not be used to create the account-level GitHub OIDC
provider from nothing. Bootstrap the singleton `token.actions.githubusercontent.com`
provider with an operator/bootstrap role first, then let `dev/shared` manage the
provider resource and `prod/shared` adopt it. Existing provider management in
the pipeline remains scoped to `token.actions.githubusercontent.com`.

GitHub CI/CD roles explicitly deny Secrets Manager value reads and writes, SSM
parameter reads, and `kms:Decrypt`. ECS task/runtime roles are separate and keep
their own secret access where the application requires it. Some create/list/
describe operations remain `Resource = "*"` because those AWS APIs do not
support complete resource-level scoping.

Workflow logging intentionally avoids printing AWS account IDs, backend bucket
names, DynamoDB lock table names, listener ARNs, target group ARNs, task
definition ARNs, and full image URIs. The CI plan job publishes only a safe
per-unit plan summary to the job summary. It also uploads the full text
Terraform/Terragrunt plan log as a short-lived GitHub Actions artifact for
review by users with access to the workflow run.

Manual rollback uses the selected GitHub environment (`dev` or `prod`) and the
matching environment-scoped rollback role. Production rollback therefore goes
through the same `prod` environment protection rules as production deploy.

## GitHub Terragrunt CD

The normal GitHub Terragrunt CD workflow is manual and layer-scoped. Use
`CD - Terragrunt Layer` from the Actions UI with:

- `environment`: `dev` or `prod`
- `layer`: `shared`, `secrets`, `global`, `data`, `platform`, `edge`, or `apps/fargate`
- `action`: `plan` or `apply`
- `confirm_prod`: exact value `prod` when running `apply` against `prod`

The workflow runs from `terraform/live/<environment>/<layer>` and uses plain
`terragrunt plan` or `terragrunt apply`; it does not use `--all` for apply.
Production applies also rely on the `prod` GitHub environment protection rules.

`apps/fargate` is now a Terraform-managed ECS skeleton layer: it creates the
blue/green services, roles, logs, alarms, and scale-down Lambda with both service
colors stopped by default. Application deployment remains in the app CD workflow
and local `scripts/deploy.sh deploy-app` path, which build or select an image,
resolve the ECR digest, render `demo-api/deploy/task-definition.template.json`,
register a new task definition, and use the blue/green deployment flow.

Pushes to `develop` can automatically plan and apply only safe dev layers:
`shared`, `secrets`, `global`, `platform`, and `edge`. The `data` and
`apps/fargate` layers, shared Terraform modules, and all prod infrastructure
remain manual via the `CD - Terragrunt Layer` workflow.

## EC2/Codex Instance-Role Flow

Do not use a named AWS profile on the EC2/Codex box. Clear any inherited profile
and use `--use-instance-role`.

Recommended complete deploy:

```bash
unset AWS_PROFILE
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes
```

Manual split flow, useful when you want an explicit checkpoint between base and
app deployment:

```bash
unset AWS_PROFILE
scripts/bootstrap.sh full-dev-bootstrap --env dev --region us-east-1 --use-instance-role --yes
scripts/deploy.sh deploy-app --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes
```

`full-dev-bootstrap` reconciles base infrastructure only: shared/ECR, secrets,
global networking/NAT/ALB, data, DB connection secret value, and platform. It
intentionally stops before `apps/fargate` and `edge`.

`deploy-app` is the app-only fast path. It builds the Docker image, pushes a
unique immutable ECR tag, resolves the image digest, runs
`scripts/bootstrap.sh apply-apps` to reconcile the ECS skeleton, renders the
versioned task definition template with `repo@sha256:...`, registers it, and
promotes the inactive ECS color. It does not reconcile base infrastructure first.
Use it directly only when base infrastructure has already been reconciled. It
does not apply edge by default.
`--include-edge` runs `scripts/bootstrap.sh apply-edge` after `apps/fargate`;
`--smoke-test` reads the edge `api_endpoint` output, waits for the active ECS
service to become stable, waits for the active ALB target group to have at least
one healthy target, and then calls `/health`. This avoids false HTTP 503
failures immediately after base drift correction or service replacement while
still failing correctly if the service never becomes healthy within the target
health timeout.

GitHub app CD also waits for the newly promoted target group to report healthy
targets before moving ALB production traffic. If `SMOKE_TEST_URL_<ENV>` is
configured, it additionally calls the resolved readiness URL after the switch.

Release handoff between reusable workflows intentionally avoids exposing S3
manifest URIs, ECR registries, or digest image URIs as job outputs. GitHub masks
some of those values and can omit them from reusable workflow outputs. The
durable source of truth remains the S3 release manifest, and deploy jobs rebuild
the by-digest manifest URI from the validated image digest when a masked URI
output is unavailable.

## Local Named-Profile Flow

Use an explicit profile when working from a local machine:

```bash
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --profile terraform-lab --include-edge --smoke-test --yes
```

## Dry-Run Checks

Before a real full deploy, confirm the planned sequence:

```bash
unset AWS_PROFILE
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes --dry-run
```

The dry-run should show `bootstrap.sh full-dev-bootstrap` first, then Docker
build/tag/push or skip-build behavior, ECR digest resolution, `bootstrap.sh
apply-apps`, the ECS blue/green deploy script, optional `bootstrap.sh
apply-edge`, and optional smoke test readiness and curl commands. It must not
include a named profile in EC2/Codex/default-chain mode.

## State Verification And Audit

After the first successful app plus edge deploy, run the redacted state audit:

```bash
scripts/audit-terraform-state-secrets.sh --env dev --region us-east-1 --use-instance-role --historical
```

Expected safe state content includes secret ARNs or names, IAM policies that
allow `secretsmanager:GetSecretValue`, ECS `secrets` entries with `valueFrom`,
API IDs/endpoints/ARNs, ECR image digests, subnet/security group/VPC IDs, log
group names, and IAM role ARNs.

Do not print full state contents in tickets or chat. If state is inspected
outside the scripts, keep output redacted and classify findings before sharing.

## Raw Terragrunt Warning

Direct Terragrunt commands require the same backend environment variables that
the scripts export:

```bash
export TG_ENV=dev
export AWS_REGION=us-east-1
export TF_STATE_BUCKET=tfstate-demo-dev-<account-id>
export TF_STATE_TABLE=tfstate-locks-<account-id>
```

Prefer the repository scripts unless you are doing read-only troubleshooting.
With modern Terragrunt, use:

```bash
terragrunt run --all -- plan
```

Do not use the legacy spelling:

```bash
terragrunt run-all plan
```
