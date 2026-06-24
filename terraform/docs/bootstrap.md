# Bootstrap Guide

This project uses a staged bootstrap flow because Terraform owns secret
metadata, while real secret values are written outside Terraform.

## Prerequisites

- AWS CLI authenticated through a local profile, or an EC2 instance role
- Terraform
- Terragrunt
- jq
- ripgrep
- Docker, for local application deployment after base bootstrap

Default local values used by the scripts:

```bash
--env dev
--region us-east-1
--profile terraform-lab
--project demo
```

When running from the EC2 test instance, use the instance role instead of a
local AWS profile:

```bash
--use-instance-role
```

`--project` must remain `demo`; Terragrunt `root.hcl` uses `project_name = "demo"`
and this repository does not implement multi-project bootstrap.

`prod` commands require `--confirm-prod`. Destructive cleanup is intentionally
not automated.

Do not use `terragrunt run --all apply` for initial bootstrap. The Terragrunt
graph cannot express the out-of-band secret value steps between `secrets`,
`data`, and `apps/fargate`. Use the staged commands below instead. After an
environment exists, modern Terragrunt read-only graph checks use
`terragrunt run --all -- plan`; the legacy `terragrunt run-all plan` spelling is
not valid with the Terragrunt CLI used by this repo. Graph-wide plans still
require caution because dependency outputs must already exist.

There is no GitHub Actions bootstrap workflow. Initial bootstrap remains
script-based because the secret value bootstrap steps require controlled operator
permissions and intentionally happen outside Terraform.

State files existing in S3 does not mean live AWS resources still match
Terraform desired state. If a Terraform-managed resource was manually changed in
AWS, such as NAT ASGs scaled to `0`, run base reconciliation before deploying the
app so Terraform/Terragrunt can detect and fix the drift.

## Recommended Full Dev Deploy

For normal dev deployment, use the deploy script's complete flow. It runs
`full-dev-bootstrap` first, then deploys the app, optional edge/API Gateway, and
optional smoke test.

From the EC2/Codex instance:

```bash
unset AWS_PROFILE
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes
```

From a local machine with the named profile:

```bash
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --profile terraform-lab --include-edge --smoke-test --yes
```

Command responsibilities:

- `full-dev-bootstrap` reconciles base infrastructure only.
- `deploy-app` deploys app/edge only and assumes base is already reconciled.
- `full-dev-deploy` is the recommended complete flow: base reconciliation,
  app/edge deployment, and smoke test.

When `--smoke-test` is enabled, `deploy-app` and `full-dev-deploy` wait for the
active ECS service to become stable and for the active ALB target group to have
at least one healthy target before calling `/health`. This avoids false 503s
right after base drift correction or ECS replacement. The smoke test still fails
if the service never becomes healthy within the readiness timeout.

## Full Dev Bootstrap

```bash
scripts/bootstrap.sh full-dev-bootstrap \
  --profile terraform-lab \
  --region us-east-1
```

From the EC2 test instance:

```bash
scripts/bootstrap.sh full-dev-bootstrap \
  --env dev \
  --region us-east-1 \
  --use-instance-role
```

This runs:

1. `validate`
2. `init-state`
3. `apply-shared`
4. `apply-secrets`
5. `bootstrap-db-passwords`
6. `apply-global`
7. `apply-data`
8. `bootstrap-db-connection`
9. `apply-platform`

It intentionally stops before `apps/fargate` and `edge`. Deploy the app image
separately only when you deliberately want the manual split flow so ECR receives
an immutable image tag, the image digest is resolved, Terraform applies the ECS
skeleton, and the deploy script registers/promotes the real task definition:

```bash
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1
```

The edge/API Gateway layer is separate by default:

```bash
scripts/bootstrap.sh apply-edge --env dev --profile terraform-lab --region us-east-1
```

`apply-edge` can run after `apply-global` because it depends on the ALB listener,
private subnets, and VPC Link security group. It is more useful after apps are
healthy, otherwise the public API endpoint may point at an empty or unhealthy
backend. For a one-command app deployment after bootstrap, let deploy apply edge
and run a smoke test:

```bash
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1 --include-edge --smoke-test
```

The full one-command flow for future deployments is:

```bash
scripts/deploy.sh full-dev-deploy --env dev --profile terraform-lab --region us-east-1 --include-edge --smoke-test --yes
```

For normal post-bootstrap infrastructure changes in GitHub Actions, use the
manual `CD - Terragrunt Layer` workflow to plan or apply one layer at a time. It
supports `shared`, `secrets`, `global`, `data`, `platform`, and `edge`.
`apps/fargate` is excluded from that generic workflow because it requires an
immutable image digest and remains part of the app deployment flow.

## Step-By-Step Bootstrap

Run one step at a time when you want clear checkpoints:

```bash
scripts/bootstrap.sh validate --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh init-state --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-shared --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-secrets --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh bootstrap-db-passwords --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-global --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-data --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh bootstrap-db-connection --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-platform --env dev --profile terraform-lab --region us-east-1
# Then choose one app deployment command.
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1
# Or include edge/API Gateway and a smoke test instead:
# scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1 --include-edge --smoke-test
```

Use `--plan-only` with any `apply-*` command to inspect planned changes:

```bash
scripts/bootstrap.sh apply-data --env dev --profile terraform-lab --region us-east-1 --plan-only
```

`full-dev-bootstrap --plan-only` is rejected because full bootstrap includes
state setup and out-of-band secret value steps. Run individual `apply-*`
commands with `--plan-only` instead.

Use `--dry-run` to print commands without executing them:

```bash
scripts/bootstrap.sh full-dev-bootstrap --dry-run
```

`inspect-contaminated-state --dry-run` only prints what it would inspect and
does not call AWS or Terragrunt. Normal `inspect-contaminated-state` is
read-only, but it does make AWS and Terragrunt state-read calls.

## Secrets Lifecycle

Terraform creates only Secrets Manager containers in `terraform/infra/secrets`.
The secret values are created by:

```bash
scripts/bootstrap.sh bootstrap-db-passwords --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh bootstrap-db-connection --env dev --profile terraform-lab --region us-east-1
```

The first command writes SQL bootstrap password values before `data` is applied.
The second command reads `db_private_ip` from the `data` Terragrunt output and
writes the application DB connection string value.

The lower-level `scripts/bootstrap-db-secrets.sh` helper is guarded for direct
use. It requires `--confirm-secret-value-bootstrap` because it reads and writes
secret values without printing them. Existing password values are not overwritten
unless `--rotate` is passed. An existing, different DB connection string is not
overwritten unless `--force-update-db-conn` or `--rotate` is passed.

Secret names:

```text
demo/<env>/db/sql-sa-password
demo/<env>/db/sql-app-password
demo/<env>/app/db-connection-string
```

Secret values are never passed into Terraform variables or Terragrunt inputs.

## Resume Guide

If `apply-data` fails because password values were missing:

```bash
scripts/bootstrap.sh bootstrap-db-passwords --env dev --profile terraform-lab --region us-east-1
scripts/bootstrap.sh apply-data --env dev --profile terraform-lab --region us-east-1
```

If `deploy-app` fails because the DB connection secret has no value, bootstrap
the DB connection secret first and rerun the deploy:

```bash
scripts/bootstrap.sh bootstrap-db-connection --env dev --profile terraform-lab --region us-east-1
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1
```

If `apply-apps` succeeds but no task is running, use the deploy script so it
builds and pushes the demo API image, resolves the digest, renders the task
definition template, registers a new revision, and promotes a color:

```bash
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1
```

ECR tag immutability is enabled, and app deployment promotes immutable
`repo@sha256:...` image URIs. The default deploy tag is
`<git-short-sha>-<YYYYMMDDHHMMSS>`. To reuse an existing image, pass either
`--skip-build --tag <existing-tag>` or
`--image-digest sha256:<64-lowercase-hex-chars>`.

## Local App Deploy

After `full-dev-bootstrap` has completed through `apply-platform`, run:

```bash
scripts/deploy.sh deploy-app --env dev --profile terraform-lab --region us-east-1
```

The deploy script:

1. Verifies `demo-<env>-shared-demo-ms` exists in ECR.
2. Logs in to ECR without printing credentials.
3. Builds `demo-api/Dockerfile` with context `demo-api`.
4. Tags and pushes the image with an immutable unique tag.
5. Resolves the ECR image digest with `aws ecr describe-images`.
6. Runs `scripts/bootstrap.sh apply-apps` to reconcile the ECS skeleton.
7. Renders `demo-api/deploy/task-definition.template.json` with the immutable image URI.
8. Registers the rendered task definition and promotes the inactive ECS color.

It does not apply edge/API Gateway by default. Add `--include-edge` when you want
that layer applied after apps/fargate succeeds. Add `--smoke-test` to read
`terraform/live/<env>/edge` output `api_endpoint`, wait for ECS/ALB readiness,
and call `/health`.

If remote state was not created:

```bash
scripts/bootstrap.sh init-state --env dev --profile terraform-lab --region us-east-1
```

## State Secret-Risk Audit

Earlier versions of this demo stored generated SQL passwords and connection
strings in Terraform state. Inspect latest and historical state versions without
deleting anything or printing full state:

```bash
scripts/audit-terraform-state-secrets.sh \
  --env dev \
  --profile terraform-lab \
  --region us-east-1 \
  --historical
```

From the EC2/Codex instance:

```bash
scripts/audit-terraform-state-secrets.sh \
  --env dev \
  --region us-east-1 \
  --use-instance-role \
  --historical
```

This checks:

- latest state for each known Terragrunt layer
- historical S3 object versions when `--historical` is passed
- resource addresses and resource types only
- output names only

The script stores temporary state files in a private temp directory and deletes
them automatically. It redacts account IDs, ARNs, bucket names and state object
keys. It never calls `aws secretsmanager get-secret-value`.

`scripts/bootstrap.sh inspect-contaminated-state` delegates to the same redacted
audit script for compatibility.

If exact secret-value resources are found in latest or historical state, rotate
the SQL SA password, SQL application user password, DB connection string secret
and the matching SQL logins/users before treating the environment as clean.

## Demo-Only Cleanup

Destructive cleanup is intentionally not automated by the bootstrap script.
For this disposable demo, cleanup should be done manually and only after
inspection. Never run cleanup against `prod`.

Typical order:

```bash
cd terraform/live/dev/apps/fargate
terragrunt destroy

cd ../../data
terragrunt destroy
```

If old demo secrets are stuck in scheduled deletion, inspect them first with
`aws secretsmanager describe-secret`. Force deletion should be used only for
known disposable demo secret names.

## Remote State

The bootstrap script creates or verifies:

- S3 state bucket
- DynamoDB lock table
- S3 versioning
- S3 default encryption
- S3 public access block
- bucket-owner-enforced ownership controls
- TLS-only bucket policy when no bucket policy already exists

The script exports `TF_STATE_BUCKET` and `TF_STATE_TABLE`, which are read by
Terragrunt `root.hcl`.
