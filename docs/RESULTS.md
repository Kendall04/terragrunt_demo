# Demonstrated results and limits

These are dated AWS trials, not live telemetry, SLAs or production certification.
[Architecture](../terraform/docs/architecture.md) and [operation](../terraform/docs/bootstrap.md)
describe the maintained system; the immutable sources below preserve the original observations.

| Capability | Observed result | Verifiable source |
| --- | --- | --- |
| Automatic DEV delivery | Protected merge, Docker build, ECR digest, ECS blue/green and observable HTTP response | [Run 42751096835](https://github.com/Kendall04/terragrunt_demo/actions/runs/42751096835) |
| Definitive SQL TLS | CA-only trust, hostname verification and new API connections; no temporary bridge | [Run 42761946295, attempt 2](https://github.com/Kendall04/terragrunt_demo/actions/runs/42761946295/attempts/2) |
| NAT recovery | HTTPS connectivity restored in **2m29.191s**; independent ASG/E13 replacement | [6 November measurement](https://github.com/Kendall04/terragrunt_demo/blob/33a32d44351810ab9a815af1da2d1f32d4b968ad/docs/SENTINEL-CHAOS-20261106.md) |
| SQL SAME-AZ | **24m42.6s**, source isolated, new EC2, restore, CHECKDB and API/KMS verified | [Cold-recovery record](https://github.com/Kendall04/terragrunt_demo/blob/33a32d44351810ab9a815af1da2d1f32d4b968ad/docs/V2-RECOVERY-SECURITY-20261105.md#cold-recovery-execution--6-november-utc) |
| SQL CROSS-AZ | **41m31.5s**, supervised cold recovery to the other AZ | Same cold-recovery record |
| Hourly backup | Native timer, CHECKSUM, versioned SSE-KMS backup/manifest pairs; publication restored 10 November at 15:40:32 UTC | [Backup operation and integrity](../operations/sql-backup/README.md) |
| Browser/API round trip | Synthetic POST/GET through API Gateway, ECS, SQL and KMS | [Original AWS browser proof](https://github.com/Kendall04/terragrunt_demo/blob/5b13b448c328241e02ee1432fba221e675e85810/portfolio/product/VALIDATION-PR36.md) |

SQL is a single writer. Planned restoration does not establish abrupt-disaster
zero RPO, PITR or automatic database HA. Image rollback does not undo incompatible
schema changes. PROD is not installed or demonstrated. The static DEMO is synthetic.
See [security](../terraform/docs/secrets-strategy.md) for the public unauthenticated
DEV API and private HTTP hops.

## Source retention

The five current Archify diagrams retain their authenticated sources, outputs,
licenses and original validation receipts. Their three dated evidence documents
and native-recovery runbook remain byte-for-byte inputs to
`TRACEABILITY-CURRENT.json`; they are provenance inputs, not a second navigation
or a claim of current health. Approved IAM contracts and inert `ci/` text fixtures
likewise remain because acceptance tests consume them. Removed development plans,
old websites and twelve historical diagrams are recoverable from commit
`5b13b448c328241e02ee1432fba221e675e85810` using `git show <commit>:<path>`.
