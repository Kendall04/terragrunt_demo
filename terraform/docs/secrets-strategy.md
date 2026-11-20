# Security and secret lifecycle

[Architecture](architecture.md) · [SQL trust contract](../../demo-api/deploy/sql-trust/README.md) ·
[Delivery permissions](../../scripts/api_delivery/permissions.py)

## Secret-value boundary

**Secret values must never enter Terraform state, outputs, source, image layers,
command arguments or public evidence.** A Terraform `sensitive` flag only redacts
display; it does not meet this requirement. IaC owns secret metadata and access
policies. Authorized administrative operations publish values outside Terraform.

ECS consumes an explicitly approved connection-secret VersionId. Updating a
Secrets Manager value does not update SQL logins or already running task
injections. Rotate those components coherently and qualify new physical SQL
connections before replacing the compatible recovery revision.

## Runtime identities

| Identity | Responsibility and boundary |
| --- | --- |
| ECS execution role | Image/log startup and injection of the exact connection-secret version; separate from application calls. |
| ECS task role | KMS Encrypt/Decrypt for text; no SQL migration or infrastructure authority. |
| SQL runtime login | SELECT/INSERT on DemoTexts and SELECT on EF migration history; no db_owner or DDL. |
| SQL migrator | Separate credentials and explicit `database-migrate --confirm-schema-change`; disabled after handoff. Startup migrations are off. |
| SQL host / native backup identities | Host administration, dedicated backup/verification credentials and scoped S3/KMS publication; not the application's task identity. |
| GitHub DEV delivery | Short-lived OIDC, protected `api-dev` environment and scoped ECS/ALB/ECR/evidence permissions; no authority in a feature PR. |
| Security administrator | IAM, KMS and protected metadata installation; separate from normal delivery. |

The [neutral resources](../infra/security/modules/protected_resources/main.tf.json)
and [delivery permission definitions](../../scripts/api_delivery/permissions.py)
are source contracts, not evidence of every effective live grant. PROD identities
and resources require their own installation/qualification. Existing shared or
DEV-owned dependencies do not establish production independence.

## SQL TLS and encryption

The common API image contains no laboratory SQL certificate. Its non-root
entrypoint validates the supplied trust manifest before .NET starts. Ordinary
operation requires `validated-v2`, `Encrypt=True`, `TrustServerCertificate=False`
and the configured expected hostname. DEV's definitive CA-only deployment is
[demonstrated](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2).
The original self-signed leaf and expiring DEV bridge are historical recipes,
not an extension mechanism for current trust. The probe uses loopback HTTP and
receives no SQL credentials; the API opens SQL connections.

KMS encrypts application plaintext before SQL persistence. The native backup
uses versioned S3 objects with SSE-KMS and records exact backup/manifest versions
and hashes. SQL's retained root EBS is encrypted. These are distinct encryption
boundaries: preserving SQL backup ciphertext does not preserve access if a
required KMS key, SQL identity or trust input is lost.

## Known limits

- The public DEV API has no authentication and returns decrypted text. Only
  synthetic, nonsensitive data belongs in this laboratory.
- HTTPS terminates at API Gateway; VPC Link/ALB/application use private HTTP.
  SQL host egress is broader than application egress.
- SQL Express is one writer, with supervised cold recovery, no HA or PITR.
- Object-access auditing and auxiliary image findings were documented in the
  [dated security review](https://github.com/Kendall04/terragrunt_demo/blob/5b13b448c328241e02ee1432fba221e675e85810/docs/ENGINEERING-REVIEW.md). Documentation updates
  do not certify remediation or current scanner results.
- The retained Sentinel archive could not be fully decrypted under expired grants.
  Its [buckets and KMS-bound roles](portfolio-operations.md#separated-sentinel-resources) were deliberately
  retained; shared keys were not deleted.

The [E1 final acceptance contract](e1-final-acceptance.md), frozen approved
specification and retired-source fixtures remain security regression inputs.
Their older controllers and E2 coordination are not the active delivery path.
