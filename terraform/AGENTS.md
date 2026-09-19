# Terraform/Terragrunt working guidance

Read [architecture](docs/architecture.md) for layer/state/network ownership,
[security](docs/secrets-strategy.md) for IAM/secrets, and
[validation](docs/validation.md) before running IaC commands.

- Check environment directory, TG_ENV, AWS identity/region and backend together.
  State keys are layer-relative; separate buckets provide environment separation.
  Wrapper backend defaults differ from raw root fallbacks.
- Secret values must never enter state. Initial bootstrap interleaves Terraform
  metadata with out-of-band secret writes; graph-wide apply cannot replace it.
- Keep skeleton/runtime ownership explicit: ECS task revisions/counts and ALB
  forwarding are deployment-owned. Private default NAT routes are Lambda-owned.
- Dev/shared singleton ownership is CURRENT behavior and a known historical mistake.
  Production independence is required as a target; do not choose single/multi-account
  implementation without resolving the decision.
- Do not hand-edit generated provider/backend files, caches, state or Lambda ZIPs.
  Provider lock coverage is incomplete; changes require deliberate review.
- Mocks for plan/validate are not deployment evidence. Init/validate/plan may write
  caches/locks/generated files and contact AWS. Check-only formatting requires
  explicit check flags; no AWS operation is implied by a validation request.
- SQL Server stays on EC2. Durability implementation/deep design is deferred until
  later deployed experiments; do not introduce backups/RDS as incidental cleanup.
