# Static assessment of E16 state exposure - 2026-10-17

Conclusion: **the current global stage should not contain secret values by design**.
The current five runtime stages also have no identified Terraform path that
generates/reads/stores credential values. This is a strong, concrete source-based
expectation, not certification of the bytes in a current or historical S3 object.
It supports reviewing a bounded internal init/plan read; it does not justify
displaying state, inspecting rejected diagnostics or bypassing the tool rejection.

Scope: source commit 4d5c95cd9d26d64bfd304be290c7f511d2696c28; 83 current Terraform/
Terragrunt source files under terraform/modules/target/dev, bounded Git history,
the known last real deployment source and public pinned provider code. No current
or historical state, private plan or denied diagnostic was opened. No AWS call,
Terraform/provider execution, secret retrieval or cloud mutation occurred.

## Actual init/plan read scope

`scripts/practical_dev.py` defines UP as global/data/platform/apps/edge.
initialize() initializes all five backends. prepare(network_only=True) still
calls state() for all five before selecting global; the only single-layer-state
branch is the explicit DOWN preview selector. A global network plan is therefore
not a global-only state read. state() internally uses Terraform state pull/show;
it does not call GetSecretValue.

The exact runtime keys are e1/lifecycle/dev/{global,data,platform,apps,edge}/
terraform.tfstate in e1-lifecycle-dev-341936017254-us-east-1. This path reads the
current object/state, not an inventory/download of historical S3 versions. It
does not consume the neutral security, shared or secrets state. E2 coordination
metadata is a separate read, not a secret-value state data source.

## Concrete current data flow

| Surface | Source and state-relevant attributes | Assessment |
| --- | --- | --- |
| global | global/main.tf.json terraform_data.protected_input.input/output: exact published dev/flow and dev/nat-profile references | Role/profile ARNs; no passwords or key material |
| VPC/ALB/SG/subnets/routes/EIPs/log groups/alarms | global/ordinary-main.tf, modules/vpc, modules/alb, security rules and alarm files | IDs, ARNs, CIDRs, tags, ports, forwarding and monitoring metadata |
| NAT ASGs | global/wp5-nat.tf.json: launch_template.id/version and subnet IDs | No launch-template body or user_data is read into this Terraform graph; ASGs absent in network-only mode |
| SQL EC2 | data/ordinary-main.tf: user_data template inputs AWS_REGION, APP_DB, APP_USER, SA_SECRET_ARN, APP_SECRET_ARN | No SA/app password value supplied to Terraform |
| SQL runtime bootstrap | terraform/infra/data/user_data.sh: shell get_secret_value, SA_PASS/APP_PASS and SQLCMDPASSWORD | Runs on EC2 after launch, outside Terraform evaluation; shell variable references in a template are not the fetched passwords |
| SQL output | data/ordinary-outputs.tf connection_string_example | Password is literal ***, not a usable credential |
| ECS | apps/ordinary-demo.tf environment contains region/deployment/KMS ARN and secrets={} | No credential value in the current skeleton task definition |
| Generic ECS module | apps/modules/ecs_service/locals.tf uses secrets[].valueFrom | ARN/reference injection; current root supplies no literal DB connection value |
| platform/edge | ECS cluster metadata; API/VPC Link/routes/ALB integration, authorization NONE | No observed credential-producing resource or auth-client-secret input |
| Protected secret containers | infra/security/modules/protected_resources/main.tf.json aws_secretsmanager_secret | Metadata only; no aws_secretsmanager_secret_version or secret_string |
| Secret value generation | scripts/bootstrap-db-secrets.sh | Generates/writes passwords and connection string outside Terraform, not Terraform resources/data sources |

The 83-file current-source scan found no random_password, secret_string/
secret_binary, aws_secretsmanager_secret_version, aws_ssm_parameter, tls_private_key,
local_sensitive_file, Terraform external data source, terraform_remote_state or
literal credential-argument assignment. Separate checks found no provisioner,
local/remote-exec, user_data_base64, get_password_data or client_secret path in
these current runtime roots. This was supplemented by reading the real template,
environment maps, outputs and metadata-resource declarations; absence of a grep
match alone is not the conclusion.

E16 variables() whitelists the normal infrastructure inputs and forbids password/
secret_value/connection_string top-level input names. The protected-input map must
equal the published metadata references. The provider blocks contain region and
allowed_account_ids, not credential literals. Process obtains authentication via
the existing external profile; initialize() supplies bucket/region/key/workspace
metadata to the backend, not access_key/secret_key/token arguments. No new
authentication or permission is needed merely to resolve this source question.

## Provider/schema qualification

AWS provider 5.100.0's [aws_instance source](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/ec2/ec2_instance.go)
stores user_data as a hash, while user_data_base64 can retain encoded content.
The latter is not configured here. Its password_data field is populated only
when get_password_data is enabled; this Linux configuration does not enable it.
The conclusion does not rely on these representations: the actual template
inputs themselves contain only references/metadata. A plan could still carry
secret template inputs if the source supplied them, which this source does not.

`sensitive=true` would not prove absence. [HashiCorp documents](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)
that sensitive values remain in ordinary state and plan files; redaction affects
display. S3 encrypt=true likewise protects storage, not the absence of plaintext
values after an authorized read. Neither is used here as proof of secret-free
content. Public identifiers/ARNs are not secret credential values, though state
continues to be private operational data.

## Historical evidence and limits

The initial Git revision **9aa2f0f** had genuinely value-bearing source:

- terraform/infra/data/password.tf: random_password.sql_sa_pwd.result and
  random_password.sql_app_pwd.result; aws_secretsmanager_secret_version.sql_sa_val
  and sql_app_val assign secret_string from those results (lines 5, 10, 26-28,
  38-40 in that historical file).
- terraform/infra/data/main.tf: aws_secretsmanager_secret_version.db_conn_v1.
  secret_string includes random_password.sql_app_pwd.result (historical lines
  214-216). If applied, these resources would put real generated passwords and a
  connection-string value in that stage's state regardless of UI sensitivity.

Those indicators disappear in **f8c948c** (2026-06-24). Bounded source snapshots
ca4b32b and the last real-UP commit **c80257b** also show the metadata/out-of-band
design. This is source history, not a read of old state contents.

secrets-strategy.md records the owner's 2026-09-18 reconciliation: older state
probably contained values but was destroyed. The later E16 teardown record says
the five runtime states had zero resources; second-real-dev-cycle.md records use
of the newer source and no secret value entering its state. These are supporting
historical records, not a fresh verification of current S3 contents or every
retained version. The old legacy deployment is not proof that the current E16
backend inherited its data; nor does current source alone prove it did not.

Confidence: high that the intended current global and runtime graph is
secret-value-free; uncertain actual persisted contents until a permitted internal
read. No historical version audit is needed for the requested current init/plan.

## Bounded next review

Use this evidence to review/authorize only the current five exact runtime keys
consumed internally by the existing E16 init/network-plan flow, using the revised
stderr-discard/metadata-only wrapper. Do not display/export state values, open
historical versions, read denied diagnostics, retrieve secret values or apply.
The static result does not reset the second tool rejection; any next invocation
still requires the separately requested human/tool review. No broader audit,
credential handoff, new IAM grant or authentication change is proposed.

Supporting source-only reports are in
C:\CodexDrop\temp\terragrunt-demo-sql-ec2-local-review-20261017:
static-state-risk-source-review.json and historical-secret-bearing-source-schema.json.
