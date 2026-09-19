# Security and secret lifecycle

## ACCEPTED DECISION — state invariant

**SECRET VALUES MUST NOT BE INTRODUCED INTO TERRAFORM STATE.**
Keep passwords, connection strings and other secret values out of Terraform
resources/data sources, inputs, outputs and generated artifacts. Marking a value
sensitive only redacts display; it is not an alternative to this invariant.

Owner reconciliation, 2026-09-18: historical state likely contained secret values
but was destroyed. No forensic/cleanup task is required for deleted state.
The next deployment must verify the invariant through evidence; no AWS inspection
has been performed as part of this documentation bootstrap.

## CURRENT CONTRACT — secret ownership and encryption

[Secrets layer](../infra/secrets) creates metadata containers only via
[secret_metadata](../infra/secrets/modules/secret_metadata/main.tf):

- demo/<env>/db/sql-sa-password
- demo/<env>/db/sql-app-password
- demo/<env>/app/db-connection-string

Terraform does not create secret versions or generate the passwords.
[bootstrap-db-secrets.sh](../../scripts/bootstrap-db-secrets.sh) writes values
outside Terraform; its lower-level entry point requires
--confirm-secret-value-bootstrap. Prefer the staged wrapper sequence in
[bootstrap](bootstrap.md), not a graph-wide initial apply.

Existing passwords stay unchanged unless --rotate is requested. A different
nonempty connection string stays unchanged unless explicitly forced/rotated.
Rotation updates Secrets Manager values only: an existing SQL login must also
be updated and tasks restarted/redeployed to consume new injected values.
This is an operational dependency, not an implemented end-to-end rotation service.

The DB instance role reads the two password secrets. ECS execution roles inject
the connection string; application task roles use KMS Encrypt/Decrypt.
A per-environment customer-managed KMS key encrypts both secret values and text;
rotation is enabled and deletion waits 30 days. EBS defaults to its AWS-managed
key. Loss of the text key affects decryptability independently of DB backups.
Evidence: [data IAM](../infra/data/main.tf),
[app IAM](../infra/apps/fargate/demo.tf),
[KMS](../infra/shared/modules/kms_key/key.tf).

## CURRENT CONTRACT — identity boundaries and limitations

GitHub authentication uses OIDC environment-shaped subjects. Branch/reviewer
restrictions must be externally configured; checked-in workflows do not prove
them. Desired protected main/PR/check/approval governance is a TARGET.

CI has ReadOnlyAccess plus explicit secret/parameter-read and decrypt denies.
Infrastructure CD also denies direct secret access and selected GitHub-role
mutation, but grants broad infrastructure APIs including EC2/ECS/Lambda/KMS.
Normal and high-risk CD share that permission policy. The high-risk role is
declared for both environments with a dev-infra-approval trust subject.
These are hardening concerns, not demonstrated least-privilege isolation.
An explicit direct-secret-read deny does not by itself prevent indirect access
through mutable workloads.

Evidence: [IAM locals](../infra/shared/modules/iam_github/locals.tf),
[CI role](../infra/shared/modules/iam_github/github_terragrunt_ci.tf),
[CD roles](../infra/shared/modules/iam_github/github_terragrunt_cd.tf),
[delivery roles](../infra/shared/modules/iam_github/github_delivery_split.tf).

## CURRENT CONTRACT versus security decisions

| Current implementation | Status of future treatment |
| --- | --- |
| Public API routes authorization NONE; plaintext read/write interface | TARGET: meaningful backend expansion before auth design; no cosmetic auth retrofit |
| Broad application/DB egress | UNRESOLVED hardening candidate, not permanent acceptance |
| Internal ALB HTTP:8080 | UNRESOLVED TLS decision; blue/green does not require HTTP |
| Encrypt=True;TrustServerCertificate=True SQL connection | UNRESOLVED certificate-validation review |
| Runtime user db_owner; migrations at task startup | UNRESOLVED migration/runtime privilege separation |
| Dev-owned OIDC/artifact resources consumed by prod | TARGET: production operational independence; mechanism unresolved |

Evidence: [routes](../infra/edge/modules/apigateway/routes.tf),
[SG rules](../infra/global/security_rules.tf),
[ALB](../infra/global/modules/alb/alb.tf),
[connection bootstrap](../../scripts/bootstrap-db-secrets.sh),
[SQL setup](../infra/data/user_data.sh).

## Evidence handling

Do not print secret values or raw state into documentation, logs or PRs.
Use synthetic/redacted examples. Existing audit scripts are AWS-connected,
download state and create temporary files; see [validation](validation.md).
Pattern-based auditing supports, but does not alone prove, secret-free state.
The owner will require evidence for future deployment rather than assuming
metadata-only configuration proves the whole operational path safe.

Least privilege, stricter provenance and environment independence remain targets.
Do not invent certificate/account architectures or silently accept these gaps.
