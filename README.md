# terragrunt_demo — cost-aware AWS platform and backend demo

This personal project demonstrates AWS infrastructure, a small .NET backend,
Terraform/Terragrunt composition and GitHub Actions delivery. One operator owns
the system end to end. It favors explicit tradeoffs over maximum redundancy.

**Owner-confirmed status, 2026-09-18: no AWS infrastructure is deployed.**
Earlier resources and historical Terraform state were destroyed to avoid unused
costs. Checked-in configuration is not proof of live resources or a successful
future reconstruction.

## Current implementation

Public API Gateway connects through VPC Link to an internal ALB and private
Fargate tasks. Blue and green services run the same .NET 8 text API. KMS encrypts
text stored in SQL Server Express on private EC2. Two NAT instances provide
per-AZ egress and event-driven replacement recovery.

Terraform owns infrastructure skeletons; deployment tooling owns task revisions,
counts and traffic. Images use digests. S3 manifests are versioned, not write-once.
Rollback exists but has not been comprehensively tested or proven.

## Durable knowledge map

| Read | When |
| --- | --- |
| [Architecture](terraform/docs/architecture.md) | Understanding topology, networking, layer/state ownership or app/data contracts |
| [Deployment](terraform/docs/deployment.md) | Changing workflows, promotion, rollback or release evidence |
| [Bootstrap and operations](terraform/docs/bootstrap.md) | Reconstructing or operating infrastructure |
| [Security and secrets](terraform/docs/secrets-strategy.md) | Changing trust, credentials, encryption or exposure |
| [Decisions and limitations](terraform/docs/decisions-and-limitations.md) | Reviewing constraints, targets, unresolved choices or improvement candidates |
| [Validation](terraform/docs/validation.md) | Choosing checks and understanding side effects |
| [Agent map](AGENTS.md) | Finding task-specific working guidance |

Implementation is authoritative for current behavior. Owner decisions govern
constraints and intent. Documents explicitly distinguish current contracts,
accepted decisions, targets, unresolved questions and historical material.

## Layout and historical evidence

- `demo-api/`: application, migrations, tests, Dockerfile and task template.
- `terraform/infra/` and `terraform/live/{dev,prod}/`: modules and composition.
- `.github/`: workflows, actions, CD classification and fixtures.
- `scripts/`: bootstrap, deployment, artifact and state-audit helpers.
- `ci/schemas/`: release/deployment contracts.
- `terraform/docs/`: durable knowledge and explicitly historical narratives.

[Case study](terraform/docs/case-study.md), [interview guide](terraform/docs/interview-guide.md)
and [delivery evolution notes](terraform/docs/ci-cd-target-architecture.md) preserve
historical reasoning, not current operating instructions.
[Evidence examples](terraform/docs/evidence/README.md) are synthetic.
The architecture PNG is illustrative; the pipeline PNG is superseded.
Neither proves deployment success or availability.

Read validation guidance before running commands. Deployment/bootstrap commands
contact AWS and mutate resources; their documentation is not authorization.

## Author

- [Kendall Fernandez](https://www.linkedin.com/in/kendall-fernandez-fernandez-b4930b174)
- [kendallffernandez@gmail.com](mailto:kendallffernandez@gmail.com)
- Costa Rica; remote Cloud / DevOps / Platform Engineering work.

<!-- Temporary unrelated-change evidence. -->
