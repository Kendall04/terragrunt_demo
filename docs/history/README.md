# Evidence and retained history

[Current documentation](../README.md) explains operation. This index preserves
results that support the portfolio without presenting old plans as active systems.
Historical measurements remain bounded by their original experiment and date.

| Evidence | What it establishes |
| --- | --- |
| [ECS V2 deployment](../DEV-V2-20261105.md) | November AWS runtime, SQL/KMS and network qualification; earlier manual bootstrap is distinct from later CD. |
| [Cold recovery](../V2-RECOVERY-SECURITY-20261105.md) | SAME-AZ/CROSS-AZ replacement, integrity checks, measured RTO and planned-cutover limitations. |
| [NAT and backup incidents](../SENTINEL-CHAOS-20261106.md) | Dated disruption/recovery observations and notification evidence, not current Sentinel operation. |
| [Automatic DEV delivery](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835) | Merge-triggered image build/publication/deployment and observable response. |
| [Definitive SQL CA delivery](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2) | Real CA-only DEV deployment after the temporary trust bridge. |
| [Historical distinct-image rollback](../../terraform/docs/deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback) | V1 Aâ†’Bâ†’A and SQL/KMS continuity; not PROD or schema rollback. |
| [Browser/API validation](../../portfolio/product/VALIDATION-PR36.md) | A real synthetic POST/GET round trip, separate from mock/UI tests. |
| [Sentinel separation](SENTINEL-SEPARATION.md) | Recoverable source and [completed AWS retirement](../SENTINEL-RETIREMENT.md), with private archive limitations. |
| [7 November engineering review](../ENGINEERING-REVIEW.md) | Historical security/cost findings; later corrections are documented in current guides. |

## Why some old contracts remain

The twelve [historical Archify views](../interactive/README.md#historical-collections),
their sources, outputs, manifests and licenses remain unchanged. The SQL
[prepared-target packet](../../operations/sql-backup/recovery/RUNBOOK.md),
[local qualification](../../terraform/docs/v2-local-completion.md) and Sentinel
trial pages are consumed by those views and their regression tests.

`ci/authority/retired/` contains inert source fixtures, not installable infrastructure.
The approved IAM specification/plan have frozen hashes. E1/E2/E15/E16 contract
pages remain at their original paths because acceptance checks or retained
recovery components consume them. [Final acceptance](../../terraform/docs/e1-final-acceptance.md)
explains their scope. They do not supersede the [native lifecycle](../../terraform/docs/native-dev-lifecycle.md)
or [automatic delivery](../DEV-DELIVERY-DESIGN.md).

Superseded local preparation reviews and completed implementation plans with no
code/test/provenance consumers were removed during the 18 November consolidation.
The complete pre-cleanup tree remains at
[`1a39c46cc02f262c04f438207647acc1282393a0`](https://github.com/Kendall04/terragrunt_demo/tree/1a39c46cc02f262c04f438207647acc1282393a0).
Use `git show <commit>:<path>` to retrieve an old document; no archive copy or
rewritten evidence is needed in the current tree.

The two immutable IAM documents still contain relative links to retired source
paths. Their original bytes are acceptance inputs, so those links were not edited.
Use the matching `ci/authority/retired/<original-path>.txt` fixture or open the
[original specification](https://github.com/Kendall04/terragrunt_demo/blob/fd6e17d89a805d05fe120f95d1b6fd61f8e09b33/specs/iam-hardening/spec.md)
in its historical tree. These 20 frozen links are not part of the current navigation.
The authenticated native-recovery document and SQL trust README are likewise
unchanged; current recovery applicability is explained in the [backup guide](../../operations/sql-backup/README.md#current-tls-prerequisite-for-another-cold-recovery).
