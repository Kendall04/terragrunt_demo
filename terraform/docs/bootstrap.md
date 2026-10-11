# Bootstrap, operations and recovery

## Accepted context and operating model

Owner reconciliation on 2026-09-18: no AWS infrastructure is deployed. Previous
resources and historical state were destroyed to avoid unused cost. Future
deployment is reconstruction, not reconciliation against assumed surviving state.
No historical-state forensics or cleanup is required for deleted state.

One system operator owns backend, AWS, IaC, delivery, observability and recovery.
Automation and evidence should support that operator. Availability/cost/recovery
objectives remain open; do not assume enterprise redundancy requirements.
Read [decisions](decisions-and-limitations.md) and [validation](validation.md)
before using any operational command.

## CURRENT CONTRACT — protected greenfield reconstruction

WP7 retires the legacy roots and direct local bootstrap/deploy entry points.
[bootstrap.sh](../../ci/authority/retired/scripts/bootstrap.sh.txt), [deploy.sh](../../ci/authority/retired/scripts/deploy.sh.txt)
and the standalone blue/green entry fail before credential discovery or AWS calls.
They cannot initialize the retired topology or select broader fallback authority.
Use the accepted [lifecycle](e1-protected-environment-lifecycle.md),
[installation](e1-ownership-publication.md) and [workflow](e1-protected-workflows.md)
contracts for future separately authorized reconstruction:

1. The separately authenticated administrator establishes the neutral security
   root, protected state/control storage and workload identities. Ordinary
   lifecycle and GitHub jobs cannot install or update this authority.
2. The administrator installs exact reviewed packages and images, records genuine
   version/readback/membership evidence and publishes the protected bindings.
   Missing prerequisites keep compute inactive.
3. The administrator writes SQL password values outside Terraform through the
   explicit [secret bootstrap](../../scripts/bootstrap-db-secrets.sh), then the
   authorized lifecycle controller reconciles fixed environment layers in order.
   Connection-string publication follows the genuine DB binding. No graph-wide
   operation substitutes for these interleaved metadata/value steps.
4. The protected release controller and independent finalizer qualify an approved
   immutable release. Dev delivery and independent prod approval use their own
   bounded gateways; history rollback uses current eligibility.

These are represented authorization paths, not a claim that installation or a
live bootstrap run succeeded. All eleven external identities, sixteen WP4D and
eight WP5 bindings remain inactive. No historical AWS migration/session revocation
is required or claimed for this empty account.

## CURRENT CONTRACT — protected state

The neutral [security root](../infra/security/README.md) has a distinct admin-only
backend. Protected lifecycle state has separate environment buckets and fixed
`e1/lifecycle/<env>/<layer>/terraform.tfstate` keys with S3 lockfiles. Only the
installed lifecycle binding selects backend/resource inputs. Public plan identities
read nonsensitive own-environment state; ordinary requesters cannot write state,
read security state or administer buckets/policies. Legacy TG_ENV/profile/backend
fallbacks no longer select an operational root. Live backend creation is unverified.

## CURRENT CONTRACT — observability and recovery limits

Configured signals include API Gateway access logs, VPC flow logs, ECS logs,
Container Insights, ALB target 5xx/latency alarms, DB status/CPU/credit alarms and
NAT capacity alarms routed to SNS email. Subscription confirmation and delivery
have not been verified. No deployed signal is currently assumed.

[E7 configuration](e7-cloudwatch-alarms.md) corrects active dev/prod task counts
to `ECS/ContainerInsights` with cluster/service dimensions and explicitly enables
NAT ASG desired/InService metrics at one-minute granularity. Capacity math drops
samples when either operand is missing. Gauge alarms use `missing` so sustained
absence is unknown; sparse ALB 5xx events retain `notBreaching`. Existing SNS
ALARM/OK actions remain; insufficient-data notifications are not configured.
Alarm existence is not evidence of metric publication or operational coverage.
Evidence: [ECS alarm](../modules/target/dev/apps/modules/ecs_service/alarm_ecs_service.tf),
[NAT alarms](../modules/target/dev/global/wp5-nat-alarms-a.tf),
[ASGs](../modules/target/dev/global/wp5-nat.tf.json).

NAT recovery performs three independent launch-event actions, without configured
DLQ or forwarding probe. EC2 health does not prove NAT function. AMI changes are
ignored in NAT launch templates and DB lifecycle; patching/replacement policy
remains unresolved.

SQL bootstrap waits for secret availability, installs packages from public
repositories, then uses a fixed wait before SQL setup. SSM access is configured
for the DB. No repository-defined SQL backup/restore or separate persistent data
volume exists. Root storage is deleted on termination.
Evidence: [data](../modules/target/dev/data/ordinary-main.tf), [user data](../infra/data/user_data.sh).

If future deployment fails, runtime traffic, service revision, candidate rule,
cleanup schedule and S3 current record may disagree. Inspect verified evidence
before choosing recovery; a failed workflow is not proof no traffic moved.
No tested automatic rollback or restore runbook is claimed here.

## TARGET / UNRESOLVED — future operational evidence

Before treating a future reconstruction as validated, capture redacted evidence
of identity/environment ownership, health semantics, secret-free state and
release results. These are future evidence requirements, not checks performed now.
The existing [state audit](../../scripts/audit-terraform-state-secrets.sh) downloads
state into private temporary files; it is AWS-connected and its resource/output
pattern scan is supporting evidence, not a complete proof of no plaintext secrets.

Database durability is HIGH importance but deliberately deferred until near the
end of the improvement program, after AWS redeployment. Keep SQL Server on EC2.
Then learn and safely test persistence, replacement/destruction, backups, restore
and accidental-deletion behavior against real infrastructure. Do not substitute
a paper design or default RDS migration for that experiment.

Recovery objectives, safe destructive-test boundaries, alert responses, capacity,
patching and budgets need later decisions. Historical teardown snippets are not
a safe operating procedure; no current data should be assumed disposable merely
because this is a demo.

[WP7 final acceptance and installation limits](e1-final-acceptance.md) records the
retirement and provider-free evidence; no old root is an installation option.
