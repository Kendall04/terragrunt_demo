# First real original DEV teardown — preparation, 2026-10-14

## Current checkpoint

No destructive Terraform apply has occurred. Initial owner destruction approval
and independent SQL data-loss approval are both pending. Deployment baseline
`e42bee61bab14ee41b02f87c4da647fa9cd8cd56` and its 20 commits are preserved.
Work continues on `codex/first-real-dev-teardown`; main is not changed.

Only profile `cnp-cert-dev`, account `341936017254`, region `us-east-1` are
permitted. STS confirms `arn:aws:iam::341936017254:user/cnp-cert-admin`.
Runtime Terraform must use the existing `TerragruntDemoDevOperator` role and its
exclusive five-state writer policy, private/versioned/encrypted backend and native
S3 locks. No competing writer, lock stealing or automatic force-unlock is allowed.

## Authentic initial ownership inventory

The existing original VPC is `vpc-0947cfaf91cb48ee9`, with public subnets
`subnet-070011dbda608ef31` and `subnet-0b60312bb24e5a5be`, private subnets
`subnet-01b43cbada7cf6f5c` and `subnet-0ad4436b6ab893b7e`.
NAT slots are `demo-dev-asg-nat-a` / `i-0a1ffe2dcf7c0889a` and
`demo-dev-asg-nat-b` / `i-0afcbfdf10a181f94`; both observed launch activities
are Successful with EndTime, with no active replacement. SQL is private
`i-0e47f560bf71333e4`. Original ECS cluster/services, internal ALB/target groups,
API `wjjhpal9ig` and VPC Link `7fe58y` remain present. Tags, exact IDs and original
Terraform state establish ownership; a name or Environment tag alone does not
permit deleting unrelated resources. Private inventory, complete versioned E13
records, plans and logs stay outside Git and exclude credentials/secret values.

The runtime bucket is `e1-lifecycle-dev-341936017254-us-east-1`, keys
`e1/lifecycle/dev/{global,data,platform,apps,edge}/terraform.tfstate`.
Its separate shared key, both backend buckets/state versions, security-root IAM
and installation evidence, KMS/secrets, ECR/images and release/journal artifacts
are not part of the five-layer destruction.

## Controller and historical evidence assessment

Seven actual E13 mutation attempts are inventoried at authentic S3 VersionIds.
Six have matching ACK/APPLIED evidence. Original NAT-A SDC attempt
`25f1ad3e-2db1-5f2a-8ad2-7481546cdfab` lacks an ACK/terminal journal record.
CloudTrail event `98730b62-65c7-49d1-8f3b-ea1f227dae89` identifies the exact
instance/request/role and Client.UnauthorizedOperation. The separately identified
human correction `41ff966c-8f56-5cc9-a2ab-4ba64f6e4333` has ACK/APPLIED evidence.
This is a known rejected historical request, not evidence of a still-running
mutation; it does not authorize fabricating an ACK or rewriting old records.
The retained E16 execution guard still requires proper attributable reconciliation
before execution; investigation alone does not bypass it.

All six execution-DLQ messages are actual version-1 failures from 00:17 UTC on
2026-10-14, marked RetriesExhausted. They are not offline fixtures and are not
pending deliveries in that failure queue. Each was saved privately; visibility
was restored, and none was deleted, purged or redriven. The delivery DLQ was empty;
approximate counts alone never prove invocation or remote-effect finality.

Preparation disabled only rule `e1-wp4-dev-nat-launch`, set reserved concurrency
zero for the three exact DEV NAT functions, and suspended Launch,
AlarmNotification, AZRebalance, ReplaceUnhealthy, ScheduledActions and
InstanceRefresh on the two original ASGs. Capacities remain one; Terminate is
not suspended. Both ECS desired counts remain one. No Terraform destroy,
instance termination or SQL-data deletion is part of this preparation.
Disabling admissions is not retroactive AWS request cancellation. Reconcile
Lambda execution/effect evidence and fresh native activities before dispatch.
No project CodeBuild deployment controller is installed; actual inventories,
not assumed absence, determine whether additional writers need inhibition.

## Review before destruction

The first live review found that `down-plan` required capacity termination even
before the owner could inspect a real destroy preview. The bounded correction
allows ordinary saved-plan preparation without shutdown. Optional `--layer`
selects only one original existing DEV layer for independent preview; this does
not create a transaction or grant out-of-order execution. All existing apply
checks remain: exact account/role/backend/source, state lineage/serial/digest,
variables and binary/JSON hashes, reverse dependency order, shutdown observation
and independent SQL-loss confirmation. Known uncertainty or reactivation still
blocks apply. Tests exercise preview-before-inhibition and rejected apply.

Prepare actual binary and readable JSON/text previews for all five current
states. Obtain one explicit owner approval for the disclosed full DEV scope
before the first destructive Terraform apply. After approval, inhibit/drain
runtime capacity using existing E16 operations and check real terminal state.
Prepare/review a fresh plan if observations/state changed; never silently replay
an old binary or resend an ambiguous mutation. Request SQL-loss consent
separately immediately before the data stage. Order remains
`edge -> apps -> platform -> data -> global`; keep inhibition through networking.

Before declaring success independently verify instances, ASGs, services/tasks,
ALB, API/VPC Link, EIPs, attached EBS, ENIs, routes/subnets/security groups/VPC,
and empty intended runtime states. Original recovery compute/rules may require
separate exact administrator cleanup because they belong to security installation,
not the five runtime states; do not delete retained IAM/evidence/bundles blindly.
Classify survivors as retained, deleting, unexpected or unverified, never zero bill.

## Costs while awaiting approval

The original compute and networking remain running. The deployment's observed
base rate with two active colors was about USD 0.096785/hour, excluding EBS,
ALB LCU, logs/Container Insights, traffic/API requests, KMS/secrets and retained
ECR/S3 storage. This is historical session pricing, not an approved budget or
future price guarantee. Retained storage, keys, secrets and evidence may continue
billing after runtime DOWN. No automatic garbage collection is introduced.
