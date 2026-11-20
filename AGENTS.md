# Repository working map

A cost-aware AWS/.NET laboratory operated by one engineer. Read only the
references needed for the task; this file is a map, not an architecture manual.

## Sources and constraints

- Checked-in implementation determines current behavior; [owner decisions](terraform/docs/decisions-and-limitations.md) determine constraints and targets. Dated receipts are not live status.
- Secret values must not enter Terraform state, outputs, source, images or logs.
- Terraform owns skeletons; application delivery owns task revisions/counts and ALB forwarding. E13 owns NAT route recovery. Exclude competing writers before operations.
- SQL Server remains on EC2. Native hourly backups and supervised cold recovery have [AWS evidence](docs/V2-RECOVERY-SECURITY-20261105.md), not a guarantee of HA, PITR or zero disaster RPO.
- DEV automatic delivery and definitive CA-only SQL TLS are demonstrated. PROD is disabled and unqualified; production independence from DEV-owned resources remains a target.
- Sentinel's runtime was [retired](terraform/docs/portfolio-operations.md#separated-sentinel-resources); retained evidence/storage is historical. Preserve SQL backups, E13 and shared KMS dependencies.
- Historical E2 remains intact under an administrative handover, not current delivery authority. No force unlock, invented terminal record or reactivation of retired controllers.

## Read when

| Task | Load |
| --- | --- |
| Topology, layers, state and ownership | [Architecture](terraform/docs/architecture.md); [Terraform guidance](terraform/AGENTS.md) |
| API, encryption, health and migration | [Application/data contract](terraform/docs/architecture.md#current-contract--application-and-data); [backend guidance](demo-api/AGENTS.md) |
| CI, release and rollback | [CI](docs/CI-CD-REVIEW.md); [automatic delivery](docs/DEV-DELIVERY-DESIGN.md) |
| IAM, credentials and exposure | [Security](terraform/docs/secrets-strategy.md) |
| Infrastructure operation or recovery | [Operations](terraform/docs/bootstrap.md); [native lifecycle](terraform/docs/native-dev-lifecycle.md) |
| SQL backup/restore | [Backup runbook](operations/sql-backup/README.md); [native recovery](operations/sql-backup/recovery/NATIVE-RECOVERY.md) |
| Validation execution | [Validation and side effects](terraform/docs/validation.md) |
| Historical claims or diagrams | [Evidence index](docs/RESULTS.md); [current atlas](docs/interactive/CURRENT-INDEX.md) |

Use git diff/status and local link review for documentation. Build/test writes
files; Terragrunt init/validate/plan can generate files and contact AWS. Deploy,
rollback, restore and retention commands have real effects. Do not install tools,
access AWS or deploy merely because a document lists a command.

Preserve digest-based delivery, secret metadata/value separation, immutable
approved contracts and provenance. Do not weaken tests or refresh security hashes
to conceal a changed source. Update the primary guide when behavior changes;
keep historical experimental results distinct from current guarantees.
