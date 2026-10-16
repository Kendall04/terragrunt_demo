# Repository working map

A cost-aware AWS/.NET demo operated by one engineer. Read only the knowledge
needed for the task; this file is a map, not the architecture reference.

## Sources and constraints

- Checked-in implementation determines CURRENT CONTRACT. Owner decisions in
  [the register](terraform/docs/decisions-and-limitations.md) determine constraints
  and intent. Keep targets, unresolved choices and historical narratives distinct.
- No AWS infrastructure existed at owner reconciliation on 2026-09-18.
  Do not assume live resources or treat old state/examples as current evidence.
- Secret values MUST NOT enter Terraform state, outputs, logs or committed artifacts.
- Terraform owns skeletons; deploy tooling owns task revisions/counts and ALB
  forwarding. Do not accidentally let competing tools own those fields.
- Production independence from dev-owned resources is a TARGET requirement;
  current dev/shared ownership is a known defect, not a convention to perpetuate.
- Cost and single-operator safety are design constraints. SQL Server stays on EC2.
  The owner authorized the first local V2 SQL backup/restore increment on
  2026-10-16. Its [runbook](operations/sql-backup/README.md) and
  [validation boundary](terraform/docs/validation.md#sql-backuprestore-local-increment---2026-10-16)
  separate native Express proof, the accepted S3/KMS component drill and future
  EC2 installation. The [local service contract](operations/sql-backup/README.md#local-service-increment---2026-10-16)
  adds packaging/cleanup/inhibition; it installs no host service or cloud access.

## Read when

| Task | Load |
| --- | --- |
| Topology, networking, layers, state, ownership | [Architecture](terraform/docs/architecture.md); [Terraform guidance](terraform/AGENTS.md) |
| Backend, encryption, health, migrations | [Application/data contract](terraform/docs/architecture.md#current-contract--application-and-data); [backend guidance](demo-api/AGENTS.md) |
| Workflows, releases, rollback, artifacts | [Delivery](terraform/docs/deployment.md) |
| IAM, credentials, secrets, exposure | [Security](terraform/docs/secrets-strategy.md), architecture ownership |
| Bootstrap, operational failure, recovery | [Operations](terraform/docs/bootstrap.md), delivery if release-related |
| Requirement/tradeoff or improvement selection | [Decisions and backlog](terraform/docs/decisions-and-limitations.md) |
| Any validation execution | [Validation and side effects](terraform/docs/validation.md) |

The owner authorized the .NET 10 LTS source migration on 2026-10-16.
[Current local qualification](terraform/docs/validation.md#net-10-lts-local-migration---2026-10-16)
records the SDK/image pins, test boundary and shared checkout. Historical .NET 8
AWS trials do not prove deployment of the .NET 10 source.

## Validation and hazards

Use git diff/status and local link review for docs. App checks live in
ci-dotnet.yml; infrastructure checks in ci-terragrunt.yml; helper checks in
ci-repo-hygiene.yml and .github/scripts/cd/tests. Read the validation guide before
running them: build/test writes files; Terragrunt validate/plan can initialize,
generate files and contact AWS. Deployment/rollback commands mutate resources.
Do not install dependencies, access AWS or deploy merely because a doc lists a command.

Preserve digest-based delivery and secret metadata/value separation.
The dated [DEV rollback evidence](terraform/docs/deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback)
proves one qualified application A-to-B-to-A trial, not PROD recovery or database
restore. Release metadata defaults are not test evidence.
Update the authoritative docs alongside future behavior changes. Historical
case-study/interview/phase-plan material and PNGs are not operational authority.
