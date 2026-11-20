# Operations and recovery

[Architecture](architecture.md) · [Native lifecycle](native-dev-lifecycle.md) ·
[Automatic delivery](../../docs/DEV-DELIVERY-DESIGN.md)

The November DEV installation has real ECS, SQL/KMS, TLS, backup and recovery
evidence. Earlier statements that the account was empty describe September or
retired trials. Reconcile current identity, state and resources before operating;
a dated receipt is not a fresh inventory or permission to recreate a resource.

## Choose the owner before changing anything

| Operation | Procedure and effects |
| --- | --- |
| Application release | Protected merge to `develop`; [delivery](../../docs/DEV-DELIVERY-DESIGN.md) owns ECS revisions/counts and ALB traffic. |
| Application rollback / incomplete delivery | Same protected environment queue; inspect both ALB routes and operational state before retrying. Reconciliation records verified state; rollback deploys the previous compatible image with approved configuration. |
| Infrastructure plan/apply/retirement | [Native DEV lifecycle](native-dev-lifecycle.md); fresh plan, existing backend/locks, explicit affected-resource approval and writer exclusion. |
| SQL backup failure | [Backup runbook](../../operations/sql-backup/README.md); inspect the native timer/job and exact remote receipt before changing configuration. |
| SQL replacement | [Cold recovery](../../operations/sql-backup/recovery/NATIVE-RECOVERY.md); source fencing, protected backup/keys, new EC2 and current TLS preflight. Disruptive and separately authorized. |
| NAT failure / maintenance | [E13](e13-nat-reliability.md); inspect ASG/launch handlers, routes, EIP, source/destination checking and failure queues. No cross-AZ failover is implied. |

## Before an AWS operation

Confirm account, region, environment, caller and current grants together. Verify
existing resource IDs and configuration, source/tool pins, state serial/locks and
rollback inputs. A saved plan from before SQL replacement is not reusable.
Preserve secret values outside state, command arguments, logs and public artifacts.
Local validation commands and their side effects are listed in [validation](validation.md).

Stop competing application writers before infrastructure maintenance. GitHub
concurrency does not exclude a manual operator or Terraform apply. Current delivery
requires the approved handover and versioned state; do not reset a RECONCILE state
or the historical E2 record to bypass uncertainty.

## Recovery boundaries

- A failed workflow may have changed traffic. Read both ALB routes, the active
  task revision/digest, task/target health and release state before another mutation.
- Before drain, the old ECS color can support compensation. After drain, recovery
  requires reinstating compatible capacity; schema rollback is not supplied.
- SQL has a retained encrypted root disk and hourly versioned backups. Keep exact
  object versions, restore holds, encryption keys and required secrets available.
  A ciphertext backup alone does not prove future decryptability or restoreability.
- Native SQL cold recovery is supervised. Source isolation must prevent two writers;
  an unreachable host is not proof of termination. No restore over the active DEV
  database or automatic restart of an old writer is part of ordinary operation.
- Retained disks, object versions, ECR, logs and keys can incur costs after compute
  stops. Teardown and retention are separate owner decisions, not effects of CI.

## Monitoring and historical authority

CloudWatch logs/alarms and the native producer's receipts remain available according
to their installed configuration. Alarm existence does not prove message delivery.
Sentinel's [runtime was retired](portfolio-operations.md#separated-sentinel-resources); there is no
current Sentinel observer, autonomous escalation or automatic retention tagger.
NAT E13 and the SQL backup timer remain independent.

[E1 final acceptance](e1-final-acceptance.md), [E2-R](e2r-owner-recovery.md) and
E15/E16 pages describe retained contracts or retired operators. E2-R still has
no administrative unlock. The actual handover retired its application authority
without altering its ACTIVE history. Do not reactivate these old entrypoints as
an operational fallback.
