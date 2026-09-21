# Backend working guidance

Read the application/data section of [architecture](../terraform/docs/architecture.md)
and [validation](../terraform/docs/validation.md). Load
[delivery](../terraform/docs/deployment.md) when changing task configuration,
health gates or schema compatibility; security docs for credential/KMS changes.

- This is one simple text API deployed in two colors. Backend/domain expansion is
  a target; meaningful auth follows domain design, not cosmetic retrofit.
- Persist ciphertext, not plaintext. The KMS wrapper receives UTF-8 input and
  stores base64 ciphertext; existing payload/pagination edge cases are backlog.
- Preserve the distinction: /health and /health/live are liveness; /ready and
  /health/ready test dependencies. ALB uses liveness; deployment separately
  requires per-task one-shot /ready evidence before promotion.
- DB_CONN_STRING is required outside Development. APP_ENV is not ASP.NET's
  environment selector. SDK credentials use the runtime chain.
- Startup migrations currently use db_owner and affect the shared database.
  Old/new colors must be considered together; image rollback does not undo schema.
  Privilege separation and reliable rollback remain unresolved targets.
- Tests use doubles and disable migrations. A normal local app start may mutate
  a configured DB and contact KMS. dotnet build/test writes outputs and restore
  uses dependencies/cache; do not run in strict read-only work.
