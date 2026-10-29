# Security and secret lifecycle

> **Current DEV operations (2026-10-28):** use the [native Terraform lifecycle](native-dev-lifecycle.md). E16 execution/session requirements below are historical; independent security and delivery contracts remain.

## ACCEPTED DECISION — state invariant

**SECRET VALUES MUST NOT BE INTRODUCED INTO TERRAFORM STATE.**
Keep passwords, connection strings and other secret values out of Terraform
resources/data sources, inputs, outputs and generated artifacts. Marking a value
sensitive only redacts display; it is not an alternative to this invariant.

Owner reconciliation, 2026-09-18: historical state likely contained secret values
but was destroyed. No forensic/cleanup task is required for deleted state.
The next deployment must verify the invariant through evidence; no AWS inspection
has been performed as part of this documentation bootstrap.

## Local SQL security follow-up - 2026-10-27

[Implementation and admission boundary](sql-runtime-security.md) separates an explicit
migration command from the data-only runtime and adds opt-in validated-v2 SQL TLS/
effective-permission guards. Startup migrations now default off. TARGET DEV/PROD
Fargate general egress narrows to HTTPS while retaining exact SQL/1433. No controls
were installed; legacy bootstrap remains db_owner/TrustServerCertificate=True,
an opt-in bootstrap now prepares a separate migrator and disabled minimal runtime.
SQL host egress and internal HTTP remain unresolved. The table below describes
that legacy deployed recipe, not acceptance of the strict profile. Certificate
inputs, reviewed privilege handoff, Linux artifacts and native tests are pending.

## CURRENT CONTRACT — secret ownership and encryption

[Neutral protected resources](../infra/security/modules/protected_resources/main.tf.json)
create secret metadata containers only:

- demo/<env>/db/sql-sa-password
- demo/<env>/db/sql-app-password
- demo/<env>/app/db-connection-string

Terraform does not create secret versions or generate the passwords.
[bootstrap-db-secrets.sh](../../scripts/bootstrap-db-secrets.sh) writes values
outside Terraform; its lower-level entry point requires
--confirm-secret-value-bootstrap. Use the explicit administrator/lifecycle sequence in
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
Evidence: [data IAM](../modules/target/dev/data/ordinary-main.tf),
[app IAM](../modules/target/dev/apps/ordinary-demo.tf),
[KMS](../infra/security/modules/protected_resources/main.tf.json).

## CURRENT CONTRACT — final E1 protected authority

[WP6 protected workflows](e1-protected-workflows.md) supplies exact environment,
repository, audience and immutable reusable-entry OIDC trust templates. All eleven
request identities remain deny-only until genuine protected installation and
G1-G9 conformance are supplied. Internal execution roles retain service-only trust,
exact PassRole/resource boundaries and no external OIDC acquisition. Ordinary
infra callers cannot administer security; delivery/recovery cannot administer
lifecycle, qualifications, eligibility, code installation or IAM.

Workflows now use only pinned closed requests or a separate read-only plan identity.
They expose no legacy AWS-role secrets, static keys, role chaining, app-CD/TG_CD
fallback or direct ECS/ALB/infra mutation. Sanitized result readers cannot write
protected evidence/configuration; protected object policies deny internal reads.
External environment branch/reviewer controls remain unverified.

WP7 removes legacy broad roles, policies, attachments, default OIDC trusts,
PassRole grants and environment roots from operational configuration. They survive
only as inert digest-pinned source data for regression/provenance. No residual AWS
session exists to revoke in this undeployed account. See [WP7](e1-final-acceptance.md).

## CURRENT CONTRACT versus security decisions

| Current implementation | Status of future treatment |
| --- | --- |
| Public API routes authorization NONE; plaintext read/write interface | TARGET: meaningful backend expansion before auth design; no cosmetic auth retrofit |
| Broad application/DB egress | UNRESOLVED hardening candidate, not permanent acceptance |
| Internal ALB HTTP:8080 | UNRESOLVED TLS decision; blue/green does not require HTTP |
| Encrypt=True;TrustServerCertificate=True SQL connection | UNRESOLVED certificate-validation review |
| Runtime user db_owner; migrations at task startup | UNRESOLVED migration/runtime privilege separation |
| Neutral protected OIDC/artifact dependencies | E1 security ownership corrected; broader operational independence remains a target |

Evidence: [routes](../modules/target/dev/edge/modules/apigateway/routes.tf),
[SG rules](../modules/target/dev/global/ordinary-security_rules.tf),
[ALB](../modules/target/dev/global/modules/alb/alb.tf),
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

## CURRENT CONTRACT — protected administration and installation

The neutral [security root](../infra/security/README.md) owns security controls and
workload role/secret metadata bindings. Ordinary/high-risk lifecycle cannot
administer IAM/OIDC/KMS, secret policies, protected storage or its own execution
dependencies. Sensitive bootstrap/update remains separately authenticated operator
authority. Public requesters have no PassRole/AssumeRole; internal trusts are
service-only. Exact PassRole belongs to accepted service-specific execution roles
and fixed workload tuples. App DB/KMS and execution pull/log/secret injection remain.

Admin-only versioned control storage, package digest, exact S3 VersionId/readback,
approved immutable runtime image and current environment membership are required
for installation. Caller flags cannot activate compute. Eleven request identities,
sixteen WP4D and eight WP5 bindings stay inactive. Repository acceptance does not
verify live IAM/provider behavior, external grants, GitHub settings or bootstrap.

## E15-E/F combined DEV quiescence boundary

[Combined contract and remaining decisions](e15ef-combined-quiescence.md) wires
separate ECS/NAT guards into protected WP5/E15-D, with immutable UNKNOWN evidence
and the original E2 hold. Whole-operation ownership/stage order, terminal ECS
cluster handoff, installed authenticated adapters and issued-effect settlement
remain unavailable. Complete DOWN stays denied; no IAM or activation is added.

## E15-G operational component follow-up

[E15-G](e15g-operational-teardown.md) adds original-E2-owner composition, bounded
ECS drain, sealed terminal cohort handoff and residual completion checks.
Complete installed DOWN remains PARTIALLY_READY and denied: NAT executor/effect
closure, authentic ECS closure, whole-operation preparation and exhaustive
residual installation remain required. No IAM/activation or live AWS evidence.

## Historical E16 supervised mode (retired 2026-10-28)

The [historical E16 operator record](e16-practical-dev-lifecycle.md) implements
per-layer original DEV saved-plan review/apply and observed shutdown under an
explicitly authorized, exclusive existing-human state-writer transfer. Default
mode remains inert; PROD/shared/security-root ownership is retained. Existing
WP3/WP4 delivery and E13 recovery remain. E15-G/H advanced finality contracts are
not weakened or activated. Source readiness is distinct from genuine installation
and live AWS validation; no AWS operations occurred.

## Proposed EC2 backup credential installation (2026-10-16)

The [grouped installation review](../../operations/sql-backup/EC2-INSTALL-REVIEW.md)
proposes two dedicated local SQL logins. After explicit approval, root on the
selected EC2 instance would use its existing SA-secret read permission, generate
passwords locally, and store only the two connection strings in root:root 0600
files under a 0700 directory on encrypted EBS. systemd LoadCredential supplies
private runtime copies to the backup job. SA remains process-only, and no secret
value enters Terraform, argv, SSM command text, output, evidence or Git. No new
secret container, text-key grant or application-login change is proposed.

This is an uninstalled lab proposal. The source plans without access by default;
actual bootstrap requires root, reviewed package/config, explicit approval hash
and exact IMDS role/account. Existing logins/credentials or an uncertain receipt
block replay. Reboot persistence is limited to that disposable encrypted EBS;
no managed rotation, cross-host continuity or production credential guarantee
is introduced. Preserve security-admin ownership of the separate role/KMS overlay.
