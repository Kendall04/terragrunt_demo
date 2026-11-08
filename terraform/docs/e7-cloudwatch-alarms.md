# E7 CloudWatch alarm configuration

## CURRENT CONTRACT — active TARGET configuration

This closes backlog B7's bounded configuration gap in both dev and prod. It
changes undeployed configuration, not live alarm evidence. Frozen legacy text
under `ci/authority/retired` stays unchanged and inert.

The authoritative [lifecycle generator](../../scripts/tests/security_root/wp5.py)
corrects extracted TARGET configuration before both repository materialization
and immutable lifecycle packaging. The [renderer](../../scripts/tests/security_root/render.py)
checks the entire generated contract. Lifecycle package digests in
[authority.json](../infra/security/authority.json) change because the installed
Terraform bytes change; all installation/activation maps stay empty.

| Signal | Namespace / metric | Dimensions | Collection / period | Missing data |
| --- | --- | --- | --- | --- |
| ECS desired/running gap, each color | `ECS/ContainerInsights`: `DesiredTaskCount`, `RunningTaskCount` | `ClusterName`, `ServiceName` | Existing cluster Container Insights enabled; 60 seconds | `missing` |
| NAT InService low, each AZ | `AWS/AutoScaling`: `GroupInServiceInstances` | `AutoScalingGroupName` | Explicit ASG collection at `1Minute`; 60 seconds | `missing` |
| NAT desired/InService gap, each AZ | `AWS/AutoScaling`: `GroupDesiredCapacity`, `GroupInServiceInstances` | `AutoScalingGroupName` | Same explicit collection and period | `missing` |
| ALB target latency, each color | `AWS/ApplicationELB`: `TargetResponseTime` | `LoadBalancer`, `TargetGroup` ARN suffixes | Existing 300 seconds | `missing` |
| ALB target errors, each color | `AWS/ApplicationELB`: `HTTPCode_Target_5XX_Count` | Same ARN suffixes | Existing 300 seconds | `notBreaching` |
| SQL EC2 status, CPU, credits | Existing `AWS/EC2` metrics | `InstanceId` | Existing periods | `missing` (status/CPU already used explicit/default missing) |

The task metrics and dimensions follow [AWS Container Insights documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-ECS.html).
The ASG collection follows [AWS group metrics documentation](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-metrics.html)
and the [provider's collection attributes](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/website/docs/r/autoscaling_group.html.markdown).
The cluster name comes from the existing cluster ARN input; the service name is
the created ECS service name. NAT dimensions reference the matching protected
ASG slot. Both colors retain the same shared ECS service module.

## Missing observations and capacity math

`missing` preserves an unknown state when observations are unavailable. Sustained
absence across CloudWatch's evaluation range produces `INSUFFICIENT_DATA`, rather
than an invented healthy value. It does not assert failure: zero-count bootstrap,
inactive colors, idle latency series and stopped resources can legitimately have
no samples. CloudWatch can still evaluate older real datapoints within its
extended evaluation range; this policy does not detect every isolated lost sample.
Existing ALARM/OK SNS actions stay unchanged. No insufficient-data notification,
new alarm, incident process or automated recovery action is added.

Sparse 5xx error metrics retain `notBreaching`: AWS reports these only for nonzero
errors. Absence of error events is not an availability assertion; these alarms
cannot distinguish a silent collection failure from no errors. Latency no longer
claims a good observation when no traffic or collection exists. See [ALB metric
reporting criteria](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-cloudwatch-metrics.html)
and [CloudWatch missing-data behavior](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarms-and-missing-data.html).

For both capacity gaps, `IF` computes subtraction only when both inputs are
nonnegative observations. `FILL(input, -1)` marks missing samples; the false
branch is omitted so the output sample is dropped. This matters because plain
CloudWatch subtraction treats a missing operand as zero, which can produce a
false non-breaching gap. Existing thresholds and evaluation periods are preserved.
Delayed samples may temporarily leave the expression unknown; no runtime timing
claim is made. This uses documented [metric math IF/FILL semantics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/using-metric-math.html).

## Authority and ownership

The [lifecycle IAM source](../../scripts/tests/security_root/wp5_iam.py) adds only
`autoscaling:EnableMetricsCollection` and `autoscaling:DisableMetricsCollection`
for the provider's collection reconciliation. Grants require the environment
resource tag and the two fixed `demo-{env}-asg-nat-{a,b}` names in the fixed
account/region. The ASG-generated ID segment is wildcarded to support first
creation. No generic resource/action grant, workload-role edit, new PassRole,
request-gateway permission or launch-template authority is added. Supported IAM
resource/tag conditions follow [AWS Auto Scaling authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_autoscaling.html).

Protected launch-template prerequisites, fixed one-instance NAT capacities,
secret metadata/value separation, zero-count bootstrap, delivery-owned ECS
revisions/counts and ALB forwarding, and inactive protected bindings stay intact.

## Offline evidence and remaining live limits

Run `python -I -B scripts/tests/monitoring/run.py` from the repository root. The
stdlib suite installs the existing credential/socket/process guard; it needs no
provider, backend, AWS, dependency installation or Terraform execution. It checks
actual dev/prod metrics, dimensions, collection, periods, missing policies,
missing operands, unchanged alarm inventory and non-E7 alarm fields, exact
source/package generation, narrowly bounded metric permissions, unchanged other
lifecycle policy statements and unchanged protected authority except package hashes.

Use the existing E1 acceptance gate, renderer, lifecycle static checker, source
inventory, local link check, Terraform check-only formatting and `git diff --check`
for applicable regressions. Formatting parses HCL/JSON syntax but does not validate
AWS resource schemas. Provider-free static evaluation checks actual policy/gate
expressions in disposable roots, never initializes the TARGET roots.

No infrastructure is assumed to exist. Provider-backed validation, real metric
publication/dimensions, delayed/missing-data evaluation, ASG permission readback,
SNS subscription/delivery and actual alarm transitions remain unverified. This
change does not prove NAT packet forwarding, application health or rollback.
