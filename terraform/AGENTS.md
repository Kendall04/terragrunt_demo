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
  The 14 TARGET roots and neutral security root have tracked provider locks;
  [E14-B](docs/e14b-toolchain-reproducibility.md) defines their coverage and update
  limits. Changes require deliberate review, not incidental initialization.
- Mocks for plan/validate are not deployment evidence. Init/validate/plan may write
  caches/locks/generated files and contact AWS. Check-only formatting requires
  explicit check flags; no AWS operation is implied by a validation request.
- SQL Server stays on EC2. The owner-authorized local V2
  [backup/restore increment](../operations/sql-backup/README.md) is implemented;
  its policies/units are uninstalled proposals. Cloud integration, real S3/KMS,
  recovery targets and retention still need separate authorization/decisions.
  Never apply its preview or introduce RDS as incidental cleanup.
