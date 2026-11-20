# Decisions and limitations

Implementation determines current behavior; owner decisions determine constraints.
[Architecture](architecture.md), [delivery](../../docs/DEV-DELIVERY-DESIGN.md) and
[dated evidence](../../docs/RESULTS.md) distinguish those from future targets.

## Retained owner decisions

| ID | Decision | Current interpretation |
| --- | --- | --- |
| D1 | Cost awareness is first-class | Prefer the least costly design meeting the explicit laboratory requirements; include retained storage and operational effort. |
| D2 | Secret values must not enter Terraform state | Metadata/value separation is mandatory; display redaction is insufficient. |
| D3 | One operator owns the system | Use maintainable automation and explicit recovery, without fictional teams or unnecessary controllers. |
| D4 | SQL Server stays on EC2 | RDS is not an incidental replacement. SQL durability is bounded by the implemented backup/cold-recovery design. |
| D5 | Durability learning requires real infrastructure | The earlier deferral is fulfilled by the November recovery trials; no new destructive trial is authorized by that historical decision. |
| D6 | Meaningful backend/domain precedes auth design | The laboratory remains synthetic-data-only. Public plaintext access is a real limitation, not production authorization. |

Production independence from development-owned resources remains a target.
The shared ECR model in the implemented delivery code and other retained shared
ownership must not be presented as a qualified independent PROD installation.
PROD is disabled and not demonstrated.

## Final architectural choices

- Terraform owns infrastructure skeletons; application delivery owns revisions,
  desired counts and ALB forwarding. Security administration remains separate.
- Protected PRs and required CI/Safety precede integration. DEV delivers
  automatically from `develop` using OIDC and immutable image digests.
- Environment serialization and fenced external writers replace E2 as application
  delivery authority. The old ACTIVE record remains intact under a reviewed
  handover; it was not force-unlocked or made into a fictitious success.
- The common non-root image receives trust per environment. DEV uses its definitive
  CA with strict SQL TLS; the temporary leaf bridge is no longer active.
- SQL has one writer, hourly S3/KMS backups, protected restore inputs and supervised
  cold recovery. NAT ASG/E13 replacement is independent per AZ.
- Static DEMO hosting is independent of ECS. Sentinel was separated and its
  runtime retired; [retained evidence](portfolio-operations.md#separated-sentinel-resources) is historical.

## Limits and unresolved decisions

| Area | Limit / decision needed before expanding scope |
| --- | --- |
| API security | No user authentication; plaintext reads and public writes require synthetic, nonsensitive data. Internal application hops use private HTTP. |
| SQL recovery | No HA, PITR or abrupt-disaster zero-RPO guarantee. Measured RTOs are supervised trial results. Image rollback cannot reverse schema changes. |
| Retention | Two newest valid backup pairs and restore holds stay protected. Existing Lifecycle expires admitted versions; no automatic replacement retention tagger was installed after Sentinel retirement. Untagged backups, ECR and disks can accumulate costs. |
| PROD | Requires real resources, independent credentials/trust, governance and live qualification. Exact-digest promotion logic alone is not a deployment. |
| Observability | No current Sentinel observation/escalation. Native logs/alarms do not certify notifications or continuous uptime. |
| Security debt | Historical object-access audit gaps, auxiliary image findings and NAT disk encryption findings remain dated findings until independently resolved. See the [7 November review](https://github.com/Kendall04/terragrunt_demo/blob/5b13b448c328241e02ee1432fba221e675e85810/docs/ENGINEERING-REVIEW.md). |
| Operations | Resource retirement, key retention, credential renewal and costs need current owner scope. Old budget windows and expired permissions are not current authorization. |

The E1/E2/E15/E16 documents and [immutable IAM specification](../../specs/iam-hardening/spec.md)
remain where contracts/tests require them. They do not define a new work program
or override the native lifecycle. Superseded proposals and the original decision
chronology remain in [Git history](https://github.com/Kendall04/terragrunt_demo/blob/1a39c46cc02f262c04f438207647acc1282393a0/terraform/docs/decisions-and-limitations.md).
