# terragrunt_demo — Production-Grade AWS Platform (Terraform + Terragrunt + ECS Blue/Green)

![Terraform](https://img.shields.io/badge/IaC-Terraform_%7C_Terragrunt-623CE4)
![AWS](https://img.shields.io/badge/Cloud-AWS-232F3E)
![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF)
![Auth](<https://img.shields.io/badge/Auth-AWS_OIDC_(No_Static_Keys)-success>)
![Deploy](<https://img.shields.io/badge/Deploy-Blue%2FGreen_(ALB_Rule_Switch)-informational>)

> **A realistic, production-grade AWS platform showcasing GitOps delivery, modular IaC, zero-downtime blue/green deployments, and fast operator-controlled rollback.**

This repository is intentionally built as a **realistic production platform**, not a toy example.  
It focuses on **platform engineering and delivery architecture**: reproducibility, safety, auditability, and operational control.

---

## 🚀 Key Highlights

- **🔄 Zero-Downtime Deployments:** Blue/Green releases on **ECS Fargate** using **ALB listener rule switching** (fast rollback while the previous color remains alive).
- **⚙️ GitOps Delivery:** PR-based validation and controlled CD with full audit trail via GitHub Actions logs and Git history.
- **🛡️ No Static AWS Credentials:** GitHub Actions authenticates via **AWS OIDC** and assumes environment-scoped IAM roles.
- **🧱 Modular IaC:** Layered Terraform modules orchestrated with Terragrunt for clean dependencies and DRY configuration.
- **💰 Cost-Aware Architecture:** NAT Gateways replaced with **multi-AZ NAT instances** plus **EventBridge + Lambda auto-healing**, optimized for demos/MVPs with clear production upgrade paths.

---

## 🧠 Why this exists

Many AWS projects start with manual operations (“ClickOps”):

- Infrastructure created/changed in the console
- Manual ECS updates
- Slow or risky rollbacks
- No reproducibility or reliable audit trail

This demo shows how the same class of system can be operated **cleanly, safely, and repeatably** using modern cloud practices—without relying on console-driven changes.

It is inspired by real production constraints and focuses on **the platform foundation**, not business logic.

---

## 🏗 High-Level Architecture

The platform runs containerized workloads on **ECS Fargate** behind an **internal Application Load Balancer**, exposed through **API Gateway + VPC Link** (private integration).

Blue/green deployments are implemented by switching the ALB listener rule between two target groups, enabling **zero-downtime releases** and **fast rollback**.

![High-level AWS architecture](terraform/docs/diagrams/architecture.png)

**Core characteristics**

- ECS tasks run in **private subnets** (no public exposure)
- Secure ingress: **API Gateway → VPC Link → internal ALB**
- Outbound traffic via **multi-AZ NAT instances** with auto-healing
- Secrets injected via **AWS Secrets Manager**, encrypted with **KMS**
- Lightweight CloudWatch alarms for critical health signals

---

## 🔄 CI/CD & GitOps Model

All changes are driven through GitHub Actions.

1. **Infra CI:** `terraform fmt` + `tflint` + `tfsec` + `terragrunt validate/plan` on PRs (plan published as artifact).
2. **Infra CD:** `terragrunt apply` only after merge (S3 remote state + DynamoDB lock).
3. **App CD (Blue/Green):** Build → Push to ECR → Update inactive color → Health gate (`/health`) → Switch ALB rules → Schedule scale-down.
4. **Rollback:** **Manual by design** (operator-controlled traffic inversion in seconds).

![CI/CD pipelines overview](terraform/docs/diagrams/cd-pipelines.png)

**Notes**

- Environment selection is branch-based (`dev` / `prod`).
- Change detection avoids unnecessary infra/app deployments.
- Rollback is kept manual to prevent accidental traffic flips.

---

## 🔵🟢 Blue/Green Deployment Strategy

- Two ECS services exist: `blue` and `green`
- Two ALB target groups: one active, one inactive
- Deployments update the inactive color and wait for health checks
- Traffic is switched by updating ALB listener rules
- The old color remains alive for a configurable period to enable near-instant rollback

This approach keeps deployments deterministic and avoids heavy external deployment tooling while remaining extensible (e.g., future canary releases).

---

## 📂 Repository Structure (simplified)

```text
terraform/
├── global/        # VPC, ALB, NAT instances
├── platform/      # ECS cluster
├── shared/        # ECR, IAM (OIDC), KMS
├── edge/          # API Gateway, VPC Link
├── data/          # Database layer (demo / cost-optimized)
├── apps/          # ECS services & Lambdas
└── modules/       # Reusable Terraform modules

.github/workflows/
├── ci-dotnet.yml & ci-terragrunt.yml         # Validation & planning
├── cd.yml                                    # Orchestrated CD
└── rollback.yml                              # Manual rollback workflow

```

## 📖 Case Study (Deep Dive)

A full architecture case study explaining **design decisions, trade-offs, failure modes and future improvements** is available here:

➡️ **[Architecture Case Study](terraform/docs/case-study.md)**

---

## 🛠 Tech Stack

**Cloud**  
AWS (ECS Fargate, ALB, API Gateway, VPC, IAM, EC2, Lambda, EventBridge, CloudWatch, ECR, KMS, Secrets Manager)

**IaC**  
Terraform, Terragrunt

**CI/CD**  
GitHub Actions, AWS OIDC

**Containers**  
Docker

**Runtime**  
.NET 8

**Database (demo)**  
SQL Server on EC2 (cost-optimized, single-AZ)

---

## ⚠️ Disclaimer

This is a **demo platform**. Some components are intentionally simplified or cost-optimized (e.g., single-AZ database) to keep focus on platform architecture and delivery patterns.

Production upgrade paths (canary deployments, RDS Multi-AZ, advanced observability) are documented in the case study.

---

## 👨‍💻 Author / Hiring

This repository represents how I design and operate real AWS platforms: **modular IaC, GitOps delivery, and safe deployment strategies**.

If you’re hiring for **Cloud / DevOps / Platform Engineering** contract roles, this project reflects the level of ownership and rigor I bring to production systems.

- **LinkedIn:** [Kendall Fernandez](https://www.linkedin.com/in/kendall-fernandez-fernandez-b4930b174)
- **Email:** [kendallffernandez@gmail.com](mailto:kendallffernandez@gmail.com)
- **Location:** Costa Rica (CST Timezone - US Aligned, Remote-first)
