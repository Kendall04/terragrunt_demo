# Interview Guide - terragrunt_demo

Use this guide to turn the repository into a technical conversation. The goal is
not to claim every component is production-complete; the goal is to explain the
platform decisions, the trade-offs, and what would change for a real production
system.

## 1. Why build this as GitOps instead of ClickOps?

**Decision:** manage infrastructure and deployments through code, pull requests,
GitHub Actions, and auditable scripts.

**Why:** manual AWS console changes are hard to reproduce, review, roll back, or
explain later. GitOps gives the team a consistent change path.

**Trade-off:** GitOps adds workflow design and permissions complexity.

**Production answer:** keep emergency console access available only as a
break-glass path, then reconcile any emergency change back into code.

## 2. Why GitHub Actions with AWS OIDC?

**Decision:** CI/CD jobs assume AWS IAM roles through GitHub OIDC instead of
using long-lived access keys.

**Why:** OIDC gives short-lived credentials, environment-scoped trust policies,
and CloudTrail visibility without static secrets in GitHub.

**Trade-off:** IAM trust policies and GitHub environment protections must be
designed carefully.

**Production answer:** require protected GitHub environments for prod, split
roles by purpose, and avoid repository-wide wildcard trust.

## 3. Why Terraform plus Terragrunt?

**Decision:** Terraform owns resource definitions; Terragrunt orchestrates
environment-specific inputs, remote state, and layer dependencies.

**Why:** the platform has multiple layers and environments. Terragrunt reduces
repetition and keeps `dev` and `prod` roots consistent without copying large
Terraform blocks.

**Trade-off:** engineers must understand both Terraform and Terragrunt behavior.

**Production answer:** document the layer contract clearly, keep modules small,
and avoid broad `run --all apply` for risky or bootstrapped workflows.

## 4. Why split infrastructure into layers?

**Decision:** separate shared, secrets, global network, data, platform, edge,
and app skeleton layers.

**Why:** different layers have different blast radius, ownership, and change
frequency. Networking and IAM changes should not be coupled to every app deploy.

**Trade-off:** dependency management becomes more explicit and bootstrapping
requires ordering.

**Production answer:** use approval rules and role boundaries per layer,
especially for network, IAM, data, and prod app runtime changes.

## 5. Why ECS Fargate with ALB blue/green?

**Decision:** run two ECS service colors, `blue` and `green`, and move traffic
by switching ALB listener rules between target groups.

**Why:** this gives deterministic deployments, health-gated promotion, and fast
operator rollback while the previous color remains running.

**Trade-off:** full traffic switches are immediate; this is not canary traffic
shifting yet.

**Production answer:** add weighted target group shifts, canary stages,
automated analysis, and human approval for high-risk prod releases.

## 6. Why artifact manifests instead of rebuilding for prod?

**Decision:** release builds publish immutable image digests and S3 release
manifests. Dev deploy, prod promotion, and rollback consume existing manifests.

**Why:** prod should promote a known artifact, not rebuild something that merely
comes from the same source commit.

**Trade-off:** delivery needs manifest schemas, storage, validators, and
deployment records.

**Production answer:** keep manifests immutable, version the bucket, restrict
write access, and make deployment records part of the release audit trail.

## 7. Why keep Terraform out of fast release movement?

**Decision:** Terraform owns durable skeletons; scripts and GitHub Actions own
task definition revisions, desired counts, and ALB traffic movement.

**Why:** app releases should be fast and frequent without forcing Terraform
state churn for every image update.

**Trade-off:** ownership boundaries must be explicit so Terraform does not fight
the runtime deploy system.

**Production answer:** use `ignore_changes` intentionally, document runtime
owners, and monitor drift that actually matters.

## 8. Why NAT instances in a production-inspired lab?

**Decision:** use multi-AZ NAT instances with EventBridge/Lambda recovery
instead of NAT Gateways.

**Why:** NAT Gateways are excellent but expensive for an always-on demo. NAT
instances make the egress path affordable while still demonstrating routing,
auto-healing, alarms, and failure recovery.

**Trade-off:** NAT instances require patching, AMI lifecycle management, and
capacity planning.

**Production answer:** choose NAT Gateway, VPC endpoints, or a hybrid egress
strategy based on traffic volume, availability requirements, and cost.

## 9. Why an EC2 SQL Server database?

**Decision:** use a single-AZ EC2 SQL Server instance for the demo data layer.

**Why:** it keeps the lab affordable and shows how private ECS workloads consume
database secrets and network access.

**Trade-off:** there is no managed failover, automated RDS backup lifecycle, or
production-grade data resilience.

**Production answer:** move to RDS Multi-AZ or Aurora, define backup/restore
targets, test failover, and plan zero-downtime schema migrations.

## 10. Why keep secret values outside Terraform state?

**Decision:** Terraform manages Secrets Manager metadata, KMS references, IAM
permissions, and ECS secret references. Bootstrap scripts write the actual
secret values outside Terraform.

**Why:** this avoids putting generated passwords or connection strings into
Terraform state.

**Trade-off:** bootstrap is staged and cannot be represented as a simple
one-shot `terragrunt run --all apply`.

**Production answer:** add rotation, break-glass controls, access review,
secret-value audit procedures, and application restart/reload handling.

## Short Interview Narrative

The concise story is:

1. The starting problem was manual AWS operations and risky ECS updates.
2. The platform moves infrastructure and delivery into reviewed, repeatable code.
3. Terraform/Terragrunt build the durable platform layers.
4. GitHub Actions uses OIDC and scoped roles to validate, deploy, promote, and roll back.
5. App releases are immutable digest-based artifacts, not mutable image tags.
6. Blue/green traffic switching gives fast rollback while keeping the model simple.
7. The remaining gaps are explicit: managed database, production egress, WAF, canary, tracing, SLOs, and stronger secrets lifecycle.
