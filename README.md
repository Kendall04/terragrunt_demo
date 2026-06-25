# terragrunt_demo - Production-Inspired AWS Platform

![Terraform](https://img.shields.io/badge/IaC-Terraform_%7C_Terragrunt-623CE4)
![AWS](https://img.shields.io/badge/Cloud-AWS-232F3E)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF)
![Auth](<https://img.shields.io/badge/Auth-AWS_OIDC_(No_Static_Keys)-success>)
![Deploy](<https://img.shields.io/badge/Deploy-Blue%2FGreen_(ALB_Rule_Switch)-informational>)

> A realistic AWS platform demo showcasing production-grade patterns: modular IaC, GitOps delivery, zero-downtime ECS blue/green deployments, immutable release manifests, and audited rollback.

This repository is intentionally built beyond a toy example. It models the kind
of platform foundation a small team could grow from: reproducible environments,
clear deployment ownership, no static AWS credentials in CI, and operator
control over risky changes.

## Key Highlights

- **Zero-downtime app releases:** ECS Fargate blue/green deployments using ALB listener rule switching.
- **GitOps delivery model:** PR validation, branch/environment gates, GitHub Actions logs, and Git history as the review trail.
- **No static AWS credentials:** GitHub Actions authenticates to AWS through OIDC and assumes scoped IAM roles.
- **Layered Terraform/Terragrunt:** reusable modules with environment-aware live roots and explicit dependency boundaries.
- **Artifact-based promotion:** release builds publish immutable image digests and S3 release manifests; deploy/promotion jobs consume those artifacts.
- **Cost-aware platform choices:** NAT instances and an EC2 database keep the demo affordable while documenting the production upgrade path.

## Why This Exists

Many AWS projects start with ClickOps: console-created infrastructure, manual
ECS updates, ad hoc rollbacks, and no reliable way to recreate an environment.

This lab shows how that same class of system can be operated through code:
infrastructure is versioned, deployments are repeatable, rollbacks are explicit,
and CI/CD access is controlled without long-lived cloud keys.

The focus is platform engineering and delivery architecture, not business logic.

## High-Level Architecture

The demo API runs on **ECS Fargate** in private subnets behind an **internal
Application Load Balancer**. Public ingress goes through **API Gateway + VPC
Link**, so ECS tasks and the ALB are not exposed directly to the internet.

![High-level AWS architecture](terraform/docs/diagrams/architecture.png)

Core platform characteristics:

- ECS tasks run in private subnets.
- API Gateway connects privately to the internal ALB through VPC Link.
- Blue/green traffic is controlled by ALB listener rules.
- Outbound access uses multi-AZ NAT instances with EventBridge/Lambda recovery.
- Secrets are stored in AWS Secrets Manager and encrypted with KMS.
- CloudWatch alarms cover the most important health signals.

## CI/CD And GitOps Model

All delivery paths are driven by GitHub Actions:

1. `ci.yml` routes working-branch pushes to fast local checks and PRs to `develop` / `main` to the full review gate.
2. Infra CI runs formatting, static analysis, and remote Terragrunt plan only for environment-bound PRs or manual runs.
3. Safe dev infra layers can auto-apply after merges to `develop`; stateful/runtime-sensitive layers stay manual.
4. App release builds publish an immutable image digest plus an S3 release manifest.
5. Dev deploy, prod promotion, and manifest rollback consume existing manifests instead of rebuilding.

![CI/CD pipelines overview](terraform/docs/diagrams/cd-pipelines.png)

The delivery boundary is deliberate: Terraform owns durable infrastructure
skeletons, while GitHub Actions and scripts own fast release movement such as
task definition revisions, desired counts, and ALB blue/green switches.

## Blue/Green Deployment Strategy

- Two ECS services exist: `blue` and `green`.
- Two ALB target groups exist: one active, one inactive.
- Deployments update the inactive color and wait for health checks.
- Traffic switches by updating ALB listener rules.
- The previous color remains alive for a configurable window to support fast rollback.

This keeps the deployment model deterministic without requiring CodeDeploy,
service mesh infrastructure, or custom traffic controllers. It can evolve toward
weighted/canary releases later.

## Operational Evidence

The repo includes architecture and delivery diagrams plus redacted examples of
the release/deployment audit contracts:

- [Architecture diagram](terraform/docs/diagrams/architecture.png)
- [CI/CD pipeline diagram](terraform/docs/diagrams/cd-pipelines.png)
- [Redacted release manifest](terraform/docs/evidence/release-manifest.redacted.json)
- [Redacted deployment record](terraform/docs/evidence/deployment-record.redacted.json)

When publishing the portfolio version, add a real GitHub Actions run screenshot
under `terraform/docs/evidence/` after redacting account IDs, ARNs, bucket names,
image URIs, and any environment-specific identifiers.

## What I Would Change For Real Production

This lab intentionally optimizes for learning value and demo cost. For a real
production workload, I would prioritize:

- **Managed data layer:** replace the EC2 SQL Server host with RDS Multi-AZ or Aurora, plus tested backup/restore.
- **Egress strategy:** use NAT Gateway, VPC endpoints, or a workload-specific hybrid based on traffic and reliability needs.
- **Edge protection:** add WAF, stricter throttling, and a clearer public API abuse model.
- **Progressive delivery:** introduce canary or weighted target group shifts before full traffic movement.
- **Observability:** add OpenTelemetry tracing, structured logs, dashboards, SLOs, and alert runbooks.
- **Secrets lifecycle:** formalize rotation, break-glass access, audit review, and incident response.
- **Production operations:** add disaster recovery drills, load tests, cost budgets, and release readiness checks.

## Repository Structure

```text
terraform/
├── infra/         # Reusable Terraform modules and layer implementations
├── live/          # Terragrunt live roots for dev/prod
└── docs/          # Architecture, deployment, bootstrap and security docs

.github/
├── actions/       # Reusable composite actions
├── scripts/       # CI/CD helper scripts and tests
└── workflows/     # CI, infra CD, app deploy, promotion and rollback workflows

demo-api/          # .NET 8 demo service and tests
scripts/           # Local bootstrap, deploy, manifest and audit helpers
ci/schemas/        # JSON schemas for release manifests and deployment records
```

## Documentation Map

- [Architecture case study](terraform/docs/case-study.md): design decisions, trade-offs, failure modes, and future production improvements.
- [Interview guide](terraform/docs/interview-guide.md): 10 discussion-ready decisions with trade-offs.
- [Deployment runbook](terraform/docs/deployment.md): GitHub Actions roles, environment variables, deploy paths, and audit notes.
- [CI/CD target architecture](terraform/docs/ci-cd-target-architecture.md): artifact promotion, S3 manifests, deployment records, and rollback model.
- [Bootstrap guide](terraform/docs/bootstrap.md): staged local environment creation and recovery steps.
- [Secrets strategy](terraform/docs/secrets-strategy.md): how secret metadata stays in Terraform while secret values stay out of state.

## Quick Local Deploy

Recommended complete EC2/Codex dev deployment:

```bash
unset AWS_PROFILE
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --use-instance-role --include-edge --smoke-test --yes
```

Recommended complete local named-profile deployment:

```bash
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --profile terraform-lab --include-edge --smoke-test --yes
```

The bootstrap is staged because Terraform creates Secrets Manager metadata only;
actual DB password and connection-string values are written outside Terraform by
the bootstrap scripts. Full details are in the
[Bootstrap Guide](terraform/docs/bootstrap.md).

## Tech Stack

- **Cloud:** AWS ECS Fargate, ALB, API Gateway, VPC, IAM, EC2, Lambda, EventBridge, CloudWatch, ECR, KMS, Secrets Manager
- **IaC:** Terraform, Terragrunt
- **CI/CD:** GitHub Actions, AWS OIDC
- **Runtime:** .NET 8
- **Containers:** Docker
- **Database (demo):** SQL Server on EC2, single-AZ and cost-optimized

## Disclaimer

This is a demo platform with production-inspired patterns. Some components are
intentionally simplified or cost-optimized so the repo can demonstrate platform
architecture without requiring an expensive always-on production footprint.

## Author / Hiring

This repository represents how I approach AWS platform work: modular IaC,
GitOps delivery, explicit deployment ownership, and practical trade-off
management.

If you are hiring for **Cloud / DevOps / Platform Engineering** contract roles,
this project reflects the level of ownership and rigor I bring to real systems.

- **LinkedIn:** [Kendall Fernandez](https://www.linkedin.com/in/kendall-fernandez-fernandez-b4930b174)
- **Email:** [kendallffernandez@gmail.com](mailto:kendallffernandez@gmail.com)
- **Location:** Costa Rica (CST Timezone - US Aligned, Remote-first)
