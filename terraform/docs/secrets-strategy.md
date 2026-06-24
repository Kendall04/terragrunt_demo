# Secrets Strategy

This demo intentionally keeps secret values out of Terraform and Terragrunt state.

## What Terraform Manages

- `terraform/infra/secrets` owns all Secrets Manager secret metadata:
  - SQL Server SA password secret
  - SQL Server application user password secret
  - application DB connection string secret
- the reusable `secret_metadata` module creates only `aws_secretsmanager_secret`
- KMS key references used to encrypt the secret values at rest
- IAM permissions that allow:
  - the SQL Server EC2 instance to read only the SQL bootstrap password secrets
  - the ECS execution role to inject only the DB connection string secret
- ECS task definition references to secret ARNs

Terraform does not manage `aws_secretsmanager_secret_version` resources and does not generate passwords with `random_password`.
The data layer no longer declares the Random provider; no random password resources remain in configuration.

Secret names are normalized before rebuild:

```text
demo/<env>/db/sql-sa-password
demo/<env>/db/sql-app-password
demo/<env>/app/db-connection-string
```

## What Terraform Does Not Manage

- Actual SQL passwords
- Actual DB connection string values
- Secret rotation values
- Any plaintext secret in outputs, Terragrunt inputs, CI variables, logs, or artifacts

## Secret Bootstrap

Secret values are bootstrapped outside Terraform with:

```bash
scripts/bootstrap.sh bootstrap-db-passwords --env dev --region us-east-1 --profile terraform-lab
scripts/bootstrap.sh bootstrap-db-connection --env dev --region us-east-1 --profile terraform-lab
```

Prefer the wrapper commands above. The lower-level `scripts/bootstrap-db-secrets.sh`
helper is intentionally guarded and refuses to run unless
`--confirm-secret-value-bootstrap` is passed, because it reads and writes secret
values without printing them.

The script is idempotent:

- existing password secrets are left unchanged unless `--rotate` is used
- generated values are never printed
- the DB connection string is written when empty, left unchanged when already
  matching, and left unchanged when it already has a different non-empty value
  unless `--force-update-db-conn` or `--rotate` is used deliberately

Required IAM for the bootstrap identity:

- `secretsmanager:DescribeSecret`
- `secretsmanager:GetSecretValue`
- `secretsmanager:PutSecretValue`
- `ec2:DescribeInstances` when DB host auto-discovery is used
- `kms:Encrypt`, `kms:GenerateDataKey`, and `kms:Decrypt` when secrets use a customer-managed KMS key

For a fresh rebuild, use the staged bootstrap flow:

1. Apply `shared` so the KMS key exists.
2. Apply `secrets` so Secret Manager metadata exists.
3. Run `scripts/bootstrap.sh bootstrap-db-passwords` so SQL bootstrap password values exist before DB provisioning.
4. Apply `data`; the EC2 SQL bootstrap reads the SA/app password secret values.
5. Run `scripts/bootstrap.sh bootstrap-db-connection` so it reads the DB private IP and writes the DB connection string secret value.
6. Apply `platform`.
7. Run `scripts/deploy.sh deploy-app`; it builds and pushes the demo API image to ECR, resolves the immutable image digest, applies the `apps/fargate` ECS skeleton, renders the task definition template, and promotes a blue/green color.
8. ECS injects the DB connection string from Secrets Manager into the container task definition.

The EC2 SQL bootstrap script waits for password secret values to become available and does not enable shell tracing.

Do not use `terragrunt run --all apply` for initial bootstrap. The Terragrunt
dependency graph cannot express the required out-of-band secret value writes
between the `secrets`, `data`, and `apps/fargate` layers. Use the staged
bootstrap commands instead. After the environment exists, `run --all plan` may
still require caution because dependency outputs must exist.

The full dev orchestration is documented in [Bootstrap Guide](bootstrap.md):

```bash
scripts/bootstrap.sh full-dev-bootstrap --profile terraform-lab --region us-east-1
```

## State Cleanup

Previous versions of this demo stored generated SQL passwords and DB connection
strings in Terraform state. Current configuration is metadata-only, but state
history must still be treated carefully.

Run the redacted state audit before considering the secrets cleanup complete:

```bash
scripts/audit-terraform-state-secrets.sh --env dev --region us-east-1 --profile terraform-lab --historical
```

From the EC2/Codex instance:

```bash
scripts/audit-terraform-state-secrets.sh --env dev --region us-east-1 --use-instance-role --historical
```

The audit script downloads state versions only to a private temporary directory,
scans resource addresses, resource types and output names, and deletes the
temporary files automatically. It must not print secret values, full state, state
object keys, S3 bucket names, account IDs, ARNs, or Secrets Manager values.

Rotate/recreate credentials if the latest or historical state audit finds exact
secret-value resources such as `random_password`,
`aws_secretsmanager_secret_version`, credential-like `random_string`, or
SecureString-style `aws_ssm_parameter` resources. Rotation means:

1. Rotate the SQL Server SA password secret value.
2. Rotate the SQL application user password secret value.
3. Update or recreate the matching SQL login/user on the DB host.
4. Rebuild the DB connection-string secret value.
5. Redeploy/restart ECS tasks so they consume the new secret version.
6. Treat copied local state files, CI artifacts and terminal logs from the
   contaminated period as sensitive and delete them where possible.

Metadata-pattern findings, such as `aws_secretsmanager_secret` containers, ECS
secret references, IAM policies that allow `GetSecretValue`, or outputs whose
names contain `secret`, require review but are not automatically leaked values.
