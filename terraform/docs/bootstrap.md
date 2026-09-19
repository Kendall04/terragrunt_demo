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

## CURRENT CONTRACT — reconstruction sequence

The Bash wrappers require an AWS-authenticated operator, Terraform, Terragrunt,
jq and ripgrep; app deployment additionally needs Docker.
Project name is fixed to demo. Defaults use dev/us-east-1 and the local
terraform-lab profile; --use-instance-role selects the default credential chain.
Ensure the credential chain actually targets the intended identity.

[bootstrap.sh](../../scripts/bootstrap.sh) full-dev-bootstrap executes:

1. Validate inputs and initialize backend resources.
2. Apply shared, then secrets metadata.
3. Write SQL password secret values outside Terraform.
4. Apply global networking, then data.
5. Write the DB connection-string secret using the DB host.
6. Apply platform; stop before apps/fargate and edge.

Do not replace this with graph-wide apply: the graph cannot represent secret
value writes between layers. full-dev-bootstrap is dev-only and rejects
--plan-only. Individual apply-* --plan-only operations still initialize/read AWS;
they are not offline checks.

[deploy.sh](../../scripts/deploy.sh) full-dev-deploy runs base bootstrap first,
then builds/selects an image, resolves its digest, reconciles the app skeleton,
and invokes blue/green deployment. deploy-app assumes the base already exists.
--include-edge adds edge; --smoke-test waits for active service/target health and
calls /ready. Without --include-edge the public API layer is separate.

Example invocation shape, **for a separately authorized deployment only**:

```bash
scripts/deploy.sh full-dev-deploy --env dev --region us-east-1 --profile terraform-lab --include-edge --smoke-test
```

For an instance/default-chain operation, use --use-instance-role and ensure an
inherited named AWS_PROFILE does not select unintended credentials.
Do not infer permission to clear/change local configuration from this example.
Prod wrapper operations require --confirm-prod; full dev commands are not prod
bootstrap. Review current workflow support in [deployment](deployment.md).

## CURRENT CONTRACT — remote state

Bootstrap configures S3 versioning, AES256 default encryption, public-access
blocking and bucket-owner-enforced ownership. It installs a TLS-only policy when
no policy exists; an existing policy is left unchanged and needs review.
DynamoDB supplies locking. Wrappers export TF_STATE_BUCKET and TF_STATE_TABLE
with account-qualified defaults.

Raw roots have different fallback names and environment overrides. Check directory,
TG_ENV, region, identity and backend together before any initialization. Layer
state keys alone do not separate environments. Backend creation is an imperative
bootstrap responsibility, not proof that state exists now.
Evidence: [bootstrap script](../../scripts/bootstrap.sh), [root](../live/dev/root.hcl).

## CURRENT CONTRACT — observability and recovery limits

Configured signals include API Gateway access logs, VPC flow logs, ECS logs,
Container Insights, ALB target 5xx/latency alarms, DB status/CPU/credit alarms and
NAT capacity alarms routed to SNS email. Subscription confirmation and delivery
have not been verified. No deployed signal is currently assumed.

Known defects: ECS task-count alarms use AWS/ECS rather than the Container
Insights namespace; NAT ASGs do not configure collection of the group metrics
their alarms require. Missing data is treated as non-breaching. Alarm existence
is not evidence of operational coverage.
Evidence: [ECS alarm](../infra/apps/fargate/modules/ecs_service/alarm_ecs_service.tf),
[NAT alarms](../infra/global/modules/nat/alarms_nat.tf),
[ASGs](../infra/global/modules/nat/autoscaling_group.tf).

NAT recovery performs three independent launch-event actions, without configured
DLQ or forwarding probe. EC2 health does not prove NAT function. AMI changes are
ignored in NAT launch templates and DB lifecycle; patching/replacement policy
remains unresolved.

SQL bootstrap waits for secret availability, installs packages from public
repositories, then uses a fixed wait before SQL setup. SSM access is configured
for the DB. No repository-defined SQL backup/restore or separate persistent data
volume exists. Root storage is deleted on termination.
Evidence: [data](../infra/data/main.tf), [user data](../infra/data/user_data.sh).

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
