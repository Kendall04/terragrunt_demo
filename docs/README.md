# Engineering documentation

[Project](../README.md) · [DEMO](https://d20ioz705caon7.cloudfront.net/) ·
[Current architecture atlas](interactive/CURRENT-INDEX.md)

Start with architecture, then follow the relevant operating guide. These pages
describe the final ECS laboratory; dated experiments are indexed separately.

| Question | Primary reference |
| --- | --- |
| How do requests, data and AWS services connect? | [Architecture and ownership](../terraform/docs/architecture.md) |
| What does a PR validate? | [CI and branch protection](CI-CD-REVIEW.md) |
| How does a merge deploy DEV? How is rollback performed? | [Automatic delivery](DEV-DELIVERY-DESIGN.md) |
| Which identities and TLS controls protect the data? | [Security](../terraform/docs/secrets-strategy.md) · [SQL trust contract](../demo-api/deploy/sql-trust/README.md) |
| How are backups produced, retained and restored? | [SQL backup runbook](../operations/sql-backup/README.md) · [Native cold recovery](../operations/sql-backup/recovery/NATIVE-RECOVERY.md) |
| How does NAT recover? | [E13 operational contract](../terraform/docs/e13-nat-reliability.md) |
| How is infrastructure operated safely? | [Operations](../terraform/docs/bootstrap.md) · [Native lifecycle](../terraform/docs/native-dev-lifecycle.md) |
| How do I run checks without changing AWS? | [Validation and side effects](../terraform/docs/validation.md) |
| How is the independent DEMO run and published? | [Frontend](../portfolio/product/README.md) · [Hosting and rollback](../portfolio/product/HOSTING.md) |
| What was actually demonstrated? | [Evidence and history](history/README.md) |
| What remains outside the laboratory's guarantees? | [Decisions and limitations](../terraform/docs/decisions-and-limitations.md) |

**Implemented** means source exists; **demonstrated** means a cited execution
proved a bounded result. **Historical** pages retain their original dates and
limitations. **Not validated** never becomes a current guarantee because a
workflow or Terraform resource exists.

DEV automatic delivery and CA-only SQL TLS have real AWS evidence. PROD remains
disabled and unqualified. Sentinel's runtime was [retired on 10 November](SENTINEL-RETIREMENT.md);
its retained buckets and journal backup are historical storage. No live AWS
inspection was performed for this documentation consolidation on 18 November.
