# Reliability Sentinel: preserved for independent development

Sentinel was removed from ECS dependencies and its **AWS runtime retired on
10 November 2026**. [The retirement record](../SENTINEL-RETIREMENT.md) identifies
removed resources, retained storage and the archive decryption limitation.
The earlier experiments do not represent current ECS monitoring.

## Recover the implementation

The ECS consumer, runtime extensions, observers, fixtures, source pins, licenses
and IaC remain recoverable at
[`528a583d4f74ccd0368cf00929b7315d582cdb35`](https://github.com/Kendall04/terragrunt_demo/tree/528a583d4f74ccd0368cf00929b7315d582cdb35/operations/integrations).
The [source manifest](../../ci/authority/retired-sentinel.json) identifies every
preserved path, its Git-blob SHA-256, the verified private source ZIP and the
scoped Git export command. No history was rewritten.

The upstream core is
[`Kendall04/reliability-sentinel`](https://github.com/Kendall04/reliability-sentinel),
pinned by that consumer to `b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828`.
The ECS-specific `Ecs.Backup.Portable.*` extensions, observer adapters,
`portable/trial` owner and qualification tests are the material to carry forward.
Archived installation commands and old Terraform state are not authorization
to reinstall or manage the final ECS runtime.

## Evidence and retained dependencies

[6 November incident trials](../SENTINEL-CHAOS-20261106.md), the historical
Archify views and original private receipts retain their dates, failures and
limits. They do not certify uninterrupted multi-day service. The private closure
archive preserves journal, DLQ, logs, effective configuration and compensation
references; the two original S3 buckets and native journal backup remain retained.

ECS keeps NAT ASG/E13, SQL's native hourly producer, strict TLS, cold recovery,
backup storage and restore holds. [SQL storage helpers](../../operations/sql-backup/storage/README.md)
were extracted without adding another observer or automatic retention worker.
CI no longer builds Sentinel; immutable source/lock fixtures remain where they
prove substitution rejection or support historical portfolio views.

The legacy cohost bootstrap and publishing units are retired. The deprecated
Terraform cohost input accepts only null. Shared KMS policy bindings explain the
two retained IAM roles; their existence is not evidence of running Lambdas.
