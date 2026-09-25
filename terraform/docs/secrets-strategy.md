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

## TARGET FOUNDATION — separately administered E1 security ownership

[WP2A](../infra/security/README.md) introduces the neutral security-root foundation,
with one closed target authority/ownership source and eleven inert deny-only
request identities. Administration is an existing separately authenticated human
prerequisite, not a role created by ordinary lifecycle. IAM/KMS/secret/storage/
controller security and backend protections are security-admin owned; except for
inert request roles, their implementation is deferred. Existing broad IAM remains
unchanged, so this is transitional repository evidence, not deployed isolation or
E1 acceptance. GitHub governance and backend controls remain UNVERIFIED.

## TARGET FOUNDATION — control-bundle storage

[WP2B](e1-control-bundles.md) declares a separate versioned S3 bundle bucket,
canonical admin-only/TLS/create-only policy and exact SHA-256 artifact identities.
SSE-S3 is not an integrity proof. No KMS resource, controller read grant or request
permission is added; all eleven request roles remain inert. Live protections and
installation are UNVERIFIED. No secret values are bundled or published.

## TARGET FOUNDATION — inactive controller compute

[WP2C](e1-controller-compute.md) adds security-root-owned compute declarations and
execution identities with no trust Allow and deny-all permissions. No domain,
storage, logging, StartBuild or InvokeFunction grant is added. All eleven request
identities remain inert. Protected configuration selects future consumers; request
data cannot choose class/project/bundle/key/version/digest. Lambda/CodeBuild
instance maps stay empty and live compute/install/readback remain UNVERIFIED.

## E1 WP2D ownership and publication — TARGET

[Ownership and administrator publication](e1-ownership-publication.md) documents
the extracted neutral declarations, explicit protected consumer records, dormant
cleanup/NAT reservations and offline exact-version installer. Existing ordinary
roots remain CURRENT transitional exclusions; deployment/state migration has not
occurred. WP2C compute stays inactive. Run `python -I -B
scripts/tests/ownership_publication/run.py` alongside all accepted suites.
This is repository evidence pending independent review, not deployed enforcement.
