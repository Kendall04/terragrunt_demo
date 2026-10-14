# First real original DEV teardown â€” preparation, 2026-10-14

## Preparation checkpoint (before destructive approval)

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
A new create-only E13 `/reconciled` record now reports `ABSENT` with null
request digest/result, bound through S3 metadata to the separately versioned exact
CloudTrail evidence and original plan/attempt versions. Old outcomes remain
untouched; no ACK was fabricated and no mutation resent. The E16 reader was
corrected to accept this existing E13 terminal representation while rejecting
UNKNOWN, malformed ABSENT and foreign/mismatched APPLIED evidence.

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

## Saved-plan and execution checkpoint

All five actual binary destroy plans and JSON/text previews were prepared and
reviewed from source revision `82392594aab7f53f1f58f475ba94b710ae9eea77`:
edge 9, apps 9, platform 1, data 5, global 49 managed instances. Three are local
`terraform_data` markers; 70 are AWS-managed declarations. Exact original
resource IDs and owned child-parent relationships were reviewed, including ASG
list-form tags and untagged security-group rules. No shared/security state is in
these plans. No destructive apply has occurred. Later source/state changes require
fresh saved-plan review, not silent execution of these historical binaries.

Complete visible execution-log readbacks pair every START with REPORT for all
three functions. Fresh native reads show no warm pools, lifecycle hooks,
schedules, scaling policies, instance refreshes or active ASG activities.
CloudWatch currently returns no ConcurrentExecutions datapoints after inhibition;
this is not zero and does not satisfy the retained metric-based execution guard.
Independent manual reconciliation and a narrowly reviewed observation-path fix
remain necessary before apply; do not fabricate metrics or bypass that guard.
Both approvals remain pending. Capacity is still running and billing.


## Authorized controlled shutdown checkpoint

The owner authorized controlled shutdown and activity reconciliation, explicitly
withholding destructive Terraform applies and permanent SQL data-loss consent.
Actual sequence: both original ECS tasks reached STOPPED after ALB's configured
300-second deregistration; SQL `i-0e47f560bf71333e4` was normally stopped with
`vol-013e417f112c5fe43` retained; only then were both NAT ASGs resized to zero.
Both NAT instances are now terminated, both ASGs have zero min/max/desired and
no members, and all observed scaling activities have terminal status and EndTime.
The VPC, four subnets, EIPs, ALB and API still exist pending destroy approval.
Backend/state/security/IAM/KMS/secrets/ECR/artifacts remain retained.

The metric-absence defect now has the narrow direct-AWS-log alternative described
in the E16 runbook. Live verification uses the real exclusive operator role, not
a local observation fixture: six assign-EIP executions, six route executions and
seven SDC executions each have their own completed START/REPORT pair. Retries
sharing RequestId are counted separately. Windows AWS CLI output is explicitly
UTF-8 so the strict JSON reader can handle actual non-ASCII log messages.

The six historical failure messages have a create-only S3 archive with exact
version/digest readback. Original SQS messages remain unchanged: automatic review
rejected their deletion because the owner has not yet authorized that specific
step. Ask for explicit acknowledgement permission together with final destruction
approval. Do not bypass the nonempty-queue guard or treat archived evidence alone
as permission. SQL deletion needs its independent later confirmation.
Old source-bound previews must not be applied after these source/runtime changes;
prepare and inspect fresh saved plans before the final owner approval.


## First authorized edge apply: partial failure, sequence stopped

After explicit owner approval, only the exact six approved historical failure
messages were acknowledged, with archive VersionId/hash and live IDs/bodies
reverified first. No purge, redrive, new-message deletion or evidence deletion.
The complete real E16 shutdown guard passed. The exact approved edge binary was
then applied once. AWS deleted all four routes, the integration and VPC Link;
DeleteStage failed for missing ListLogDeliveries, and the VPC Link delete waiter
failed GET after tags disappeared. Native lock released; partial state serial 6
retains API/stage/log group plus the already absent link. Apps/platform/data/global
have not been dispatched. SQL/EBS loss still lacks its separate approval.

Independent AWS collections establish the link's completed absence and retained
stage; this is a known partial result, not an excuse to replay an ambiguous plan.
Preserve the old attempt. Correct only the two missing reads, then inspect/apply
an ordinary saved refresh-only state plan before a fresh remaining-scope destroy
preview. Backend/security/shared/KMS/secrets/ECR remain excluded.

### Terminated NAT IDs aging out of EC2 inventory

The next live guard stopped before apply when both previously terminated NAT
instances had aged out of DescribeInstances. Independent reads found only the
stopped SQL instance in the VPC and exact successful, completed ASG termination
activities for each original NAT ID. The DEV guard now accepts an absent prior
member only with that exact group's successful termination activity, a complete
EC2 filtered read, empty inhibited ASGs and the existing effect/execution checks.
An absent ID alone, failed termination, active member or incomplete read blocks.
No destructive apply was retried and no SQL/EBS loss approval was inferred.

AWS documents the limited visibility of terminated instances in
[DescribeInstances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html)
and the attributable termination activity in
[scaling activity verification](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-verify-scaling-activity.html).

### Second edge attempt: log-delivery delete authorization pending

After the retired-instance guard correction passed all 53 practical DEV tests,
the full live shutdown observation passed. The newly reviewed edge binary was
applied once. DeleteStage definitively failed for missing
`logs:DeleteLogDelivery` (request `3f7a72e8-5033-4001-b850-6b6d42fe25b0`).
No subsequent layer was applied and the failed attempt remains preserved.

Readbacks confirmed API `wjjhpal9ig` and stage `$default` remain, VPC Link
`7fe58y` is absent, and the five DEV states remain readable without active native
locks: edge 3 resources (serial 8), apps 9 (5), platform 1 (1), data 5 (4),
global 49 (14). SQL remains stopped with its encrypted 30 GiB root EBS in use.
No independent SQL/EBS permanent-loss approval has been received.

AWS documents DeleteLogDelivery as a permission-only action without resource-level
ARN support. An uninstalled proposal requests only that action for the existing
DEV operator role, selected account/region, and a maximum one-hour validity,
followed by removal after edge. Explicit owner approval for this scope limitation
is pending; no broad logging permission was silently installed. See
[HTTP API logging permissions](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-logging.html)
and [CloudWatch Logs authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_logs.html).
After approval, reconcile current state and prepare/review a fresh saved plan;
never replay the failed binary or force-unlock.
