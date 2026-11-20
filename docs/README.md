# Technical documentation

Start with the [project overview](../README.md) or the [five diagrams](interactive/CURRENT-INDEX.md).

| Topic | Maintained reference |
| --- | --- |
| Architecture, AWS services and ownership | [Architecture](../terraform/docs/architecture.md) |
| CI and automatic DEV delivery | [CI](CI-CD-REVIEW.md) · [Delivery and rollback](DEV-DELIVERY-DESIGN.md) |
| Network and NAT recovery | [NAT ASG/E13](../terraform/docs/e13-nat-reliability.md) |
| Backup and restoration | [SQL operation](../operations/sql-backup/README.md) · [Retention](../operations/sql-backup/storage/README.md) |
| Security, credentials and trust | [Security](../terraform/docs/secrets-strategy.md) · [SQL TLS](../demo-api/deploy/sql-trust/README.md) |
| Lifecycle and validation | [Operations](../terraform/docs/bootstrap.md) · [Native lifecycle](../terraform/docs/native-dev-lifecycle.md) · [Validation](../terraform/docs/validation.md) |
| DEMO and hosting | [Frontend](../portfolio/product/README.md) · [Hosting](../portfolio/product/HOSTING.md) |
| Measured AWS results and limits | [Results](RESULTS.md) |

DEV delivery and supervised recovery have AWS evidence. PROD remains disabled
and unvalidated. Source code, local tests and dated AWS receipts have different
meanings; none should be presented as a live availability guarantee.
