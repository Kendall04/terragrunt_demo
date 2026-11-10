# Reliability Sentinel: independent project

Sentinel is retired from the current ECS repository integration. Its installed
AWS resources have **not** been removed. The 6 November experiments remain
historical evidence, not an operational capability of the final ECS platform.

## Recover the implementation

The complete consumer, runtime extensions, observers, fixtures, source pins,
licenses/provenance and IaC are recoverable at ECS commit
[`528a583d4f74ccd0368cf00929b7315d582cdb35`](https://github.com/Kendall04/terragrunt_demo/tree/528a583d4f74ccd0368cf00929b7315d582cdb35/operations/integrations).
[Source manifest](../../ci/authority/retired-sentinel.json) inventories every preserved file,
its original Git-blob SHA-256 and a verified private source ZIP. Its `recovery`
command exports the same scoped source from Git, without private state or keys.
No history was rewritten. Do not execute the archived deployment procedures.

The upstream core already has its own repository,
[`Kendall04/reliability-sentinel`](https://github.com/Kendall04/reliability-sentinel),
pinned by the consumer to `b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828`.
Move the ECS-specific `Ecs.Backup.Portable.*` extensions, observer adapters,
`portable/trial` owner and qualification tests there when development resumes.
No new repository or framework is introduced here.

Original evidence remains accessible in
[the dated chaos record](../SENTINEL-CHAOS-20261106.md), the twelve historical
Archify views and private AWS receipts. Preserve DynamoDB revisions, the four
append-only compensations, S3 object versions, CloudWatch logs and DLQ contents.
The private operational audit of 10 November records degraded observation,
archive and notification after authorization expiry; it does not certify
multi-day availability.

## What remains in ECS

NAT ASG/E13 performs recovery independently. SQL's native hourly producer,
credentials, encrypted bucket/CMKs, cold recovery and restore holds remain.
The storage verification/retention/pinning helpers now live in
[`operations/sql-backup/storage`](../../operations/sql-backup/storage/README.md).
The optional SQL cohost publisher/units and their packaging flags are retired;
standalone package integrity and binary-lineage checks remain enforced.
Existing installed backup packages are not replaced by this repository change.

CI no longer builds or tests Sentinel. Authority inventories describe the
remaining sources; generic IAM/unknown-source rejection tests remain. The
archived provider lock remains a historical substitution-test fixture, never an
active Terraform root. API runtime, TLS, delivery selection and E13 are unchanged.

## AWS retirement requires separate approval

Use [the scoped retirement inventory and procedure](../SENTINEL-RETIREMENT.md).
An expired permission is not a stopped schedule. Repository separation neither
stops workloads nor deletes their evidence.

The supplemental IaC review removed 23 archived entries and retained
1 entries without changing their records. The exact catalog remains
pinned by `security_root/model.py` to SHA-256 `c495424e068d93b469ff29011b32f287f3e7556ed4ac581f71b2c2a1c940c338`; unknown or changed IaC
still fails closed. This is an explicit source-scope review, not an IAM grant.

Historic namespace/origin tests retain their original source inputs in an
authenticated text fixture. They still reject substitutions and unknown roots.
The old local portfolio's source routes use exact historical documents, not
executable Sentinel code. No original diagram, evidence timestamp or metric was rewritten.

The optional Terraform SQL cohost bootstrap is also archived. Default SQL
user-data remains the same base payload. A deprecated null-only input rejects
old non-null cohost settings before planning; it cannot start Sentinel. Native
SQL backup installation, TLS and the root-volume preservation opt-in remain.

The four DEV infrastructure source-package fingerprints in `authority.json`
were renewed for this reviewed hook removal. All grants, approvals, activation
fields and PROD packages remain unchanged; this does not install IAM or authorize
a deployment. TFLint's existing finding baseline remains unchanged.
