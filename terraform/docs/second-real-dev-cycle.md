# Second original DEV cycle — 2026-10-14 local / 2026-10-15 UTC

## Current verified checkpoint

The original full DEV infrastructure has been reconstructed after the first
[verified DOWN](first-real-dev-teardown.md#final-independently-verified-result--2026-10-14).
The owner authorized the second full UP after reviewing the first real saved plan
and running/retained costs. This is not the discarded reduced laboratory.
Profile `cnp-cert-dev`, account `341936017254`, region `us-east-1` only.
Bootstrap caller: `arn:aws:iam::341936017254:user/cnp-cert-admin`;
runtime writer: `arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`.
The existing administrator was used for the disclosed staged installation steps;
no administrator policy or competing runtime state writer was introduced.

Execution used clean source `c80257bac43bb1d0cf04016872ec481d0092d733` on
`codex/second-dev-cycle`. The subsequent repository commit records authentic
account-specific policy rebinding and this report; it did not execute different
source through the previously approved plans. Main was not modified or published.

Before UP, all five states were empty and independent service reads found no
previous project compute, ALB/API, orphaned EIP/EBS or snapshots. The retained
backends, enabled KMS key, secret metadata, ECR images and security evidence
remained intact. Unrelated account resources were excluded.

## Original resources now running

| Resource | Authentic second-cycle identity / observation |
| --- | --- |
| VPC | `vpc-035d1e8a7ecfd151b`, available |
| Public A / B | `subnet-0c0015acb0147b62e` / `subnet-07cfc3b9ed3fe5a77` |
| Private A / B | `subnet-08302f1ff29ca5338` / `subnet-0494cd9739c08895c` |
| NAT A / B | `i-006d33e2c6a5e64f4` / `i-0598f00ee8c465d30`, Healthy/InService |
| NAT ASGs | `demo-dev-asg-nat-a` / `demo-dev-asg-nat-b`, desired 1 each |
| NAT EIP allocations | `eipalloc-001d70416c7b286d4` / `eipalloc-0c9ef1f2b63c2c8ea` |
| SQL | `i-028606033560e9708`, private `10.0.100.115`, SSM Online |
| SQL disk | `vol-0206bcb0b6b243e3a`, encrypted 30 GiB gp3, delete-on-termination |
| ECS cluster | `demo-dev-platform-main-cluster`, ACTIVE |
| ECS services | `demo-dev-app-api-blue-svc` / `demo-dev-app-api-green-svc`, 1/1 each, steady |
| Internal ALB | `demo-dev-internal-alb`, ARN suffix `15fde9ec7769fb79`, both targets healthy |
| API / VPC Link | `427id1ezuk` / `xt9msp`, link AVAILABLE |

Public endpoint: <https://427id1ezuk.execute-api.us-east-1.amazonaws.com>.
`GET /ready` reports database and KMS Healthy. Real `POST /text` followed by
`GET /text` returned the original plaintext for a unique short value and for
4096 UTF-8 bytes. This exercises the application, SQL persistence, KMS encryption
and KMS decryption through API Gateway, VPC Link and the internal ALB.
Both service readiness probes exited 0; both target groups are healthy.
A separate short-lived task in private B also passed the same SQL/KMS readiness
contract with public-IP assignment disabled, proving its ECR/logs/application
outbound path through NAT B. It was explicitly stopped and observed STOPPED;
only the two service tasks remain running. This was not a NAT failover test.

SQL reports Express Edition (64-bit), version `16.0.4305.5`, database `demodb`
and the intended `fargate_user`. Both checked-in EF migrations are present;
CipherText uses the expanded SQL Text column. No manual schema mutation was used.

## Reviewed execution and state boundary

Terraform 1.13.4 and AWS provider 5.100.0 genuinely validated all five roots.
Runtime backend: `e1-lifecycle-dev-341936017254-us-east-1`, keys
`e1/lifecycle/dev/{global,data,platform,apps,edge}/terraform.tfstate`.
Native S3 lockfiles, private/versioned/encrypted storage and the exclusive human
writer restriction remain installed. WP5/admin still cannot write those five
keys; shared/secrets/security state remains outside this role.
The separate security backend remains
`terragrunt-demo-security-341936017254-us-east-1`, key `e1/security/terraform.tfstate`.

| Stage | Saved reviewed plan | Applied scope |
| --- | --- | --- |
| Global network | `e683d3b2-20bf-4c37-a1fc-1f607134e68e` | 43 creates |
| Global NAT | `0a985cd9-7864-4062-830c-cce39e2440cf` | 6 creates |
| Data | `95d91495-4694-4b5d-9620-b2cdc5ef829c` | 5 creates |
| Platform | `05f1cc0b-9ff4-4d83-a045-9e4b332bfa4f` | 1 create |
| Apps | `c23061a4-9ba2-4cfc-8741-7be9c242a834` | 9 creates |
| Edge completion | `47d31989-5111-4275-a442-00f94e96c715` | Integration and 4 routes |

The four edge bootstrap resources (tagged log group, HTTP API, VPC Link and
stage) required the already documented, separately authenticated administrator
path because the existing tag-constrained API creation policy is insufficient.
Their genuine new IDs were imported under the exclusive operator and native
locks, then the fresh five-create binary above was reviewed/applied. The original
nine-create edge binary was never applied after import. No unrelated resource
was adopted. Final managed resource counts are 49 / 5 / 1 / 9 / 9.

A local interruption happened after the successful apps apply return while its
post-apply readback was running. The binary was not replayed. Native state and
ECS definition/service observations established the successful result before
finishing only the interrupted readback and recording reconciliation.

## Reproducibility corrections and retained controllers

Creation order remained `global -> data -> platform -> apps -> edge`, with the
existing network-only bootstrap before NAT and authentic resource rebinding.
No original architecture component was removed and no Cloud Map was added.

- Retained NAT launch templates now use version 2 with the new public subnets
  and NAT security group. AMI/type/profile/IMDS requirements are unchanged.
- Existing DEV E13 roles and all three handler environments use the new VPC,
  subnet, EIP, route-table and membership identities. New published Lambda
  version 3 is the only target of the original DEV launch rule. Configuration,
  failure destinations, scoped invocation permissions and native readbacks were
  verified while concurrency was zero and the rule disabled. Only then were
  concurrency 1 and the rule enabled, before creating the ASGs.
- All six new E13 attempt/ACK/effect observations are APPLIED at authentic S3
  VersionIds. Both NATs have the correct EIP, disabled SDC and active private
  default route. Old UNKNOWN/history was neither erased nor force-settled.
  Published versions 1/2 remain immutable historical code with old bindings;
  they were not rewritten or used by the current rule. This is not a claim of
  universal executor finality or completed failover testing.
- Existing security Terraform associations were reconciled with reviewed
  refresh-only state and exact native imports for the six version-qualified
  Lambda permission/retry resources. No state JSON was hand-edited, old AWS
  versions/evidence deleted, or IAM action expanded.
- Operator policy snapshots 5/6/8 record only observed new network/SQL-volume/API
  identities. Actions and conditions are preserved. Installed readbacks match;
  the role has no temporary inline grants.
- The new SQL root volume received only its exact five intended tags through
  the already approved scoped action; a reviewed refresh-only saved plan then
  reconciled state. NAT root disks were inventoried through actual instance
  attachments because they do not inherit Environment/Project tags. Their
  existing 8 GiB gp2 configuration is unchanged; no universal disk-encryption
  claim is made.
- The retained connection secret was updated outside Terraform to the new SQL
  private IP, preserving its other fields/password and verifying AWSCURRENT.
  No secret value entered a plan, state, source, command output or this report.
- Both services use existing active task definitions `:4`, pinned to retained
  image digest `sha256:9671c5484c60de9db50f54abade794bb86263a5d636bca96a5eb3522c8643a50`.
  Terraform owns the inert skeleton definitions `:5`; delivery owns actual
  task revisions/counts. No mutable latest, rebuild, Docker push or copied VM
  credentials were needed. GitHub/OIDC delivery qualification is still untested.

These bindings must be resolved again from real outputs after another DOWN.
Do not reuse this cycle's plans, old private IPs or historical closure evidence.
Do not enable recovery against old bindings before verifying new membership.
No generic coordinator or second lifecycle authority was introduced.

## Costs, next tests and supervised DOWN

The environment is intentionally left running for owner inspection and later
CI/CD, blue/green and NAT failover exercises; none of those exercises is claimed
as completed here. SNS email remains optional and unconfigured, as authorized.

Estimated base running cost is about USD 0.102/hour (about USD 2.45/day): two
`t3.micro` NATs, one `t3a.small` SQL instance, two Fargate tasks of 0.25 vCPU /
0.5 GiB, an ALB, two EIP/public IPv4 addresses and 46 GiB EBS. This excludes LCU,
requests/traffic/data transfer, CloudWatch logs/metrics/Container Insights, CPU
credits, taxes and retained storage/security services. Regional price inputs:
[EC2](https://aws.amazon.com/ec2/instance-types/t3/),
[Fargate](https://aws.amazon.com/fargate/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[IPv4](https://aws.amazon.com/vpc/pricing/) and
[EBS](https://aws.amazon.com/ebs/pricing/). Retained KMS/Secrets Manager baseline
alone is approximately USD 2.20/month for the one application key/three secrets,
plus API requests; other retained security keys, ECR images, S3 versions and
CloudWatch storage can also charge. No budget or zero-dollar DOWN is promised.

The previously exercised supervised DOWN remains
`edge -> apps -> platform -> data -> global`: prepare/review each current saved
binary, use the E16 controller-inhibition and reconciliation checks, retain NAT
connectivity while ECS/SQL still need it, stop on ambiguity and preserve state.
Request fresh owner teardown approval and independent SQL/EBS loss consent.
The first DOWN needed short-lived, separately approved log-delivery and ECS
permission-only actions plus exact VPC/subnet dependency permissions. Those
expired grants were removed; do not assume they remain installed or reuse their
old resource IDs. Any needed future grant must keep the reviewed exact scope and
conditions. No automatic force-unlock, blind apply retry or account cleanup.
Retain both backends/versions, security identities, KMS/secrets, ECR/images and
release/effect evidence. Empty state alone is not residual proof; independently
inspect instances, attachments, EIPs, ENIs, load balancers, API and ASGs.

## Validation and evidence limits

Actual provider validation, saved-plan applies and independent AWS readbacks
completed. E16 VERIFY also exercised the real operator route and a unique SQL/KMS
roundtrip. The 56 practical DEV tests and 29 first-installation tests passed,
with no failures/errors/skips. Inventory, protected-policy static checks, Python/JSON
parsing, local links and format/whitespace checks passed. Static rule/resource identity and multiplicity
remain the inherited 24 TFLint warnings and 46 tfsec findings; no suppressions or
new findings. Application source/image are unchanged; historical .NET/Docker
results are not presented as fresh builds. Full historical E1 acceptance was
not rerun for account-specific policy-ID snapshots and documentation only.

A bounded pre-publication scan covered 95 unpublished commits, 2294 Git objects /
1069 blobs: no AWS access keys, private keys, Terraform states or private binary
plans were detected. Four password-regex hits referred to the same unused
synthetic documentation example. This is bounded evidence, not a universal
secret-scanner guarantee or permission to push. No remote Git operation occurred.
Raw state, plans, logs and receipts remain in the private dated second-cycle
temporary directory outside Git, not in this report. They are runtime evidence,
not credentials or an alternative authority. The final repository commit retains
public resource identities only.
