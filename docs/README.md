# Engineering documentation

Start with the [project overview](../README.md) or the
[V2 architecture atlas](interactive/V2-INDEX.md). The public
[CloudFront DEMO](https://d20ioz705caon7.cloudfront.net/) is a static presentation;
the AWS runtime is a temporary laboratory.

## Current reading paths

| Question | Maintained entry point | Detailed evidence / implementation |
| --- | --- | --- |
| How is it built? | [Architecture and ownership](../terraform/docs/architecture.md) | [Seven diagrams and traceability](interactive/V2-INDEX.md) |
| How do I run it? | [Product DEMO and local AWS Edition](../portfolio/product/README.md) | [API guidance](../demo-api/AGENTS.md), [validation and command effects](../terraform/docs/validation.md) |
| Who changes AWS? | [Native DEV lifecycle](../terraform/docs/native-dev-lifecycle.md) | [Operational boundary and closure](../terraform/docs/portfolio-operations.md) |
| How do backups/recovery work? | [Backup tooling](../operations/sql-backup/README.md), [native cold recovery](../operations/sql-backup/recovery/NATIVE-RECOVERY.md) | [Measured SAME/CROSS-AZ trials](V2-RECOVERY-SECURITY-20261105.md#cold-recovery-execution--6-november-utc) |
| What does Sentinel do? | [Portable runtime](../operations/integrations/portable/README.md) | [Real incidents and monitoring](SENTINEL-CHAOS-20261106.md) |
| What is automated? | [CI/CD engineering review](CI-CD-REVIEW.md) | [Protected deployment contracts and V1 evidence](../terraform/docs/deployment.md) |
| What is secure, and what is not? | [Technical audit](ENGINEERING-REVIEW.md), [trust boundaries](V2-TRUST-AND-THREATS.md) | [Secret lifecycle](../terraform/docs/secrets-strategy.md), [strict SQL profile](../terraform/docs/sql-runtime-security.md) |
| What was tested? | [Guarantee matrix](ENGINEERING-REVIEW.md#recovery-and-resilience) | [DEV execution](DEV-V2-20261105.md), [frontend validation](../portfolio/product/VALIDATION.md) |
| How is the site published? | [Independent hosting and rollback](../portfolio/product/HOSTING.md) | [Public HTTPS receipt](../portfolio/product/evidence/public/PUBLIC-HTTPS-QA.json) |

## Reading evidence correctly

**Implemented** means present in source; **deployed** requires a dated AWS readback;
**demonstrated** requires an authentic execution. Historical and local-double
results retain those labels. No dated receipt is a live status page.

The November records contain chronological appendices because the original errors
and partial outcomes matter. Their latest dated update takes precedence for that
record; current operation starts from the links above, not an old UP/DOWN command.
The audit's newer inventory does not rewrite historical state serials or receipts.

## What remains intentionally historical

- `terraform/docs/first-real-dev-*.md` and `second-real-dev-cycle.md`: V1 deployment,
  rollback and retirement evidence. No V2 cold-recovery claim is inferred from them.
- `terraform/docs/e*.md`: protected controller contracts and dated experiments.
  Several are mandatory inputs to the acceptance/link gate; they are not a menu
  of active pipelines. E16 is retired; its backend/IAM safeguards remain applicable.
- `terraform/docs/v2-local-completion.md` and the October pipeline review:
  local/component qualification and earlier design, retained for source/diagram
  provenance. They do not override November installation evidence.
- `specs/`, `ci/authority/`, catalogs, manifests and lock files: executable authority,
  fixtures or cryptographic inputs. They are not disposable prose.
- Five older Archify diagrams: historical views, distinct from the seven V2 views.

The [cleanup ledger](ENGINEERING-REVIEW.md#documentation-disposition) records the
removed transient material and its immutable Git source. No workflow, authority
expectation, original diagram or authentic receipt was changed to enable cleanup.
