# Original complete DEV: protected first-session baseline

The following is the E15 baseline. [E16 supervised DEV](e16-practical-dev-lifecycle.md)
explicitly replaces only its runtime DEV operation policy when exclusive state
transfer is installed; its protected-mode restrictions remain unchanged.

## Owner decision and current status

Owner decision 2026-10-13: operate the original full DEV architecture for temporary
sessions; simplify procedure, never replace infrastructure. DEV SQL data is
disposable, with independent protected operation consent before deletion. PROD,
shared/security authorities, state/locking, evidence and retained image history
are excluded from full DEV DOWN. No AWS environment has been deployed.

Main baseline `fe5467b6a73fad3a011131a08eaedeacd511843f` contained E15-S. Commit
`b2b51cd` reverts exactly that commit; its tree equals preserved E15-H
`bfe0983d696d0e13bcd429c42e635114c5b1b9c5`. E15-S2 revisions `4ef3a9f` and
`0678f27` remain on their separate branch and were not merged or cherry-picked.
No reduced root, VPC, module, lab state selector or lab operator remains here.

**PARTIALLY_READY in source; first AWS session is not currently executable.**
The [thin entry](../../scripts/original_dev.py) delegates to the existing
[WP6 client](../../scripts/workflow_requests/client.py), preserving its protected
configuration, OIDC account/source/ref, invoke-once and sanitized completion
contracts. This is executable source, not a fabricated plan generator. It adds
no permissions, approval model, storage, workflow pin, activation or coordinator.
Canonical workflows continue to use the original client. Using this helper inside
a future immutable entry requires ordinary source/governance review; it cannot
activate today's inert workflows or run through local personal credentials.

## Original resource/state matrix

Operational roots are `terraform/modules/target/dev/<layer>`, not the retired
`live/dev` or `live/prod` trees. The sole remaining live Terragrunt directory is
`terraform/live/security`; no graph-wide Terragrunt apply/destroy is authorized.
Each DEV root has S3 bucket `e1-lifecycle-dev-<account>-<region>`, key
`e1/lifecycle/dev/<layer>/terraform.tfstate`, default workspace and S3 lockfile.
Installed WP5 bindings select inputs/backend; an operator cannot substitute them.

| Layer / controller | Owned ordinary infrastructure | Creation prerequisites | DOWN / function / retained costs |
| --- | --- | --- | --- |
| security / separate administrator | KMS, secret metadata, IAM/profiles, ECR, release/control storage, protected controllers/images, NAT templates and three duties | Explicit account/region/admin identity, backend and reviewed installation | Excluded; keys/secrets/ECR/versions/logs/controller infrastructure may bill |
| shared / WP5 ordinary | SNS alerts topic and email subscription | Admin protected publication and approved recipient | Retained; notifications and supporting protected resources |
| secrets / WP5 ordinary | Protected-reference contract, no plaintext secret values | Admin secret metadata/publication | Retained; secret values are out of Terraform, Secret Manager storage remains |
| global / WP5 ordinary | VPC, 2 public + 2 private subnets, IGW/tables/SGs, internal ALB/listener/rule/TGs, 2 EIPs, 2 NAT ASGs, flow logs/alarms | shared alert ARN; exact admin flow role/NAT launch IDs, versions, subnets and recovery binding | Last; NAT closure required; verify routing/EIP/SDC and actual forwarding; ALB/NAT/IPv4/logs can bill after failure |
| data / WP5 high-risk | SQL EC2 in first private subnet, encrypted 30-GiB root EBS, DB alarms | global VPC/subnet/SG, protected SQL profile/AMI/KMS/secrets, verified SQL password bootstrap | After platform; independently consent permanent SQL loss; verify SSM/bootstrap/SQL; EC2/EBS bill until gone |
| platform / WP5 ordinary | ECS cluster, Container Insights/capacity providers | Installation inputs; no Terraform network dependency | After apps; terminal ECS evidence handoff before cluster deletion; associated workloads/logs bill |
| apps / WP5 high-risk + WP4 runtime | Blue/green Fargate skeletons at zero tasks, log groups; WP4 owns revisions/counts and listener forwarding | global/data/platform/shared/secrets, connection-string bootstrap, exact roles and TGs | After edge; drain exact two services/cohorts; Fargate/ENIs/logs can survive partial destroy |
| edge / WP5 ordinary | HTTP API Gateway, VPC Link, integration/routes/stage/access logs | global private subnets, link SG and internal ALB listener | First; verify HTTP path, VPC Link ENIs and API logs; requests/logs/ENIs can persist |

Actual source: [four subnets](../modules/target/dev/global/modules/vpc/subnets.tf),
[CIDRs](../modules/target/dev/global/modules/vpc/locals.tf),
[two NAT slots](../modules/target/dev/global/wp5-nat.tf.json),
[global/ALB](../modules/target/dev/global/ordinary-main.tf),
[SQL](../modules/target/dev/data/ordinary-main.tf),
[apps](../modules/target/dev/apps/ordinary-demo.tf),
[edge](../modules/target/dev/edge/ordinary-main.tf).
Two NAT ASGs have min/max/desired 1 for slots a/b, conditionally created only with
both approved launch bindings. Configured intent is two t3.micro NAT instances,
not proof of installed instances. Three launch-success duties associate EIP,
replace route and disable SDC; E13 contains retries/DLQs/journals. This is per-AZ
replacement recovery, not cross-AZ packet-level failover.

Historical differences preserved: no Cloud Map registration exists; it cannot be
claimed or verified. Both Fargate colors exist but only delivery starts the active
cohort; no app autoscaling. SQL default remains t3a.small, SQL Express 2022/Ubuntu
22.04 and startup migrations. No original topology/resource/IAM source changed.

## Minimum first-launch sequence, still gated

1. Owner selects exact account/region and separately authorized admin/operator
   session, alert recipient, run window and cost estimate. No values are invented.
2. Admin bootstraps neutral security state/locking, installs reviewed identities,
   protected images/provider mirror, exact packages, service-linked roles and
   publication through existing E1/WP2/WP5 ports. Validate trust/PassRole, private
   storage, exact S3 VersionIds, source hashes and real membership. Preserve the
   neutral backend; do not execute retired bootstrap or activate JSON fixtures.
3. Resolve greenfield publication staging before submitting UP. WP5 `ready()`
   requires ALL seven roots' non-null inputs and exact regional resource inventory;
   high-risk binding additionally requires exact SQL AMI/subnet/SG/type.
   These subnet/TG/role IDs are not available in an empty account. The abstract
   `LifecycleAdminChannel.observe` has no live adapter. Existing source therefore
   does not provide an end-to-end empty-account installation command. Administrator
   must specify and approve concrete staged publication/observation using existing
   ownership boundaries; dummy IDs cannot satisfy this requirement. Do not assume
   an ordinary create request can solve its own installation prerequisites.
4. After genuine bindings are possible, review per-layer plans using installed
   plan-dev. Execute approved ordinary/high-risk create requests in dependency
   order `shared -> secrets -> global -> data -> platform -> apps -> edge`.
   Stop after each verified result; refresh admin membership/inputs for the next
   stage. Platform is independent but kept in this comprehensible order. Plans
   and states are separate, not an atomic seven-root transaction.
5. Before data, administrator uses the existing secret-value bootstrap to write
   SQL passwords outside Terraform, then verifies/publishes readiness. After SQL
   gets its real private IP, publish DB connection string and readiness before
   apps. `bootstrap-db-secrets.sh --skip-db-conn` and later `--db-host` express
   these stages, but require explicit admin credential/account/region checks and
   its own confirmation. Never print values or put them in request JSON/state.
6. Global cannot be called complete with empty `protected_nat_launch`. Exact
   launch versions/roles/handler membership, E13 failure containment and real
   private egress must be installed/read back before SQL/package/ECR access.
   Any staging of VPC before launch templates requires reviewed admin publication;
   routine reconcile cannot create missing ASGs under its existing action contract.
7. Build/qualify through WP3 release and independent finalizer; deliver exact
   qualified release through WP4 deploy-dev. Do not docker push into protected
   namespaces with an unqualified convenience script. Delivery starts the
   candidate task/probe, validates exact cohort, SQL/KMS readiness and ALB targets
   before forwarding. Terraform must not take over task revisions/counts/listener.
8. Verify protected ECS/ALB preflight, then authentic application `/health` and
   `/ready`, text POST/GET SQL/KMS roundtrip through actual API Gateway endpoint,
   both private subnet egress paths, NAT EIP/route/SDC, SSM/SQL bootstrap and VPC
   Link integration. Existing WP4 checks cover ECS/ALB/task readiness, not complete
   gateway/network/residual verification. No new live verifier is installed here.

Concrete pre-activation source defect remains: WP5 shared creates
`demo-dev-shared-alerts`; E13 alarm wiring in security-root `wp4d.py` selects
`demo-dev-alerts`. It can prevent notification delivery, not proof that routing
or ECS creation itself fails. Resolve the exact DEV ARN through the authoritative
admin generator and its approved package/policy checks before activating recovery.
No topic was renamed, policy expanded or PROD generator behavior changed here.

## Actual protected commands and thin entry

Existing canonical future entry jobs: `.github/workflows/ci-terragrunt-manual.yml`
for plan-dev; `cd-terragrunt.yml` for ordinary/high-risk lifecycle; `release-build.yml`
for WP3; `deploy-dev.yml` for qualified WP4 delivery. All are currently inert.
These commands are future invocations INSIDE the exact approved GitHub entry job
with its existing `E1_REQUEST_CONFIGURATION` and verified OIDC, not local execution:

```bash
python scripts/original_dev.py plan --account "$ACCOUNT" --region "$REGION" --request-file reviewed-plan-request.json
python scripts/original_dev.py up --account "$ACCOUNT" --region "$REGION" --request-file approved-create-request.json
python scripts/original_dev.py release --account "$ACCOUNT" --region "$REGION" --request-file reviewed-source-request.json
python scripts/original_dev.py deploy --account "$ACCOUNT" --region "$REGION" --request-file qualified-release-request.json
python scripts/original_dev.py verify-infrastructure --account "$ACCOUNT" --region "$REGION" --request-file installed-preflight-request.json
```

Use the exact existing WP6 closed request schemas. UP accepts `create` only and
routes data/apps to infra-high-risk-dev, the other original layers to infra-dev.
Missing/inactive/foreign configuration or local credentials block before OIDC.
No role/backend/source/image override or automatic retry exists. The same original
client invokes once and polls sanitized completion; UNKNOWN/UNCERTAIN/failure or
missing ACK is not success. Review/create operation approvals remain in WP5.
Read-only plan previews do not become a new saved-plan authorization subsystem.
The existing plan-dev client returns sanitized status/change counts, not the
full readable resource-change preview. Protected administrator review/evidence
access for the first session must be established; this wrapper does not falsely
claim to display the hidden Terraform JSON or add a public state-read permission.
Current WP5 UP generates/checks/applies its protected own plan; it does not consume
an external plan-dev binary. Do not claim its preview is E15-C's exact DOWN plan.

`original_dev.py down` and `residual` explicitly reject before credentials.
Existing `ephemeral_lab.py up-prepare/down-preview/down-review/status/verify/residual`
remain local declaration/evidence-review helpers, never live executors. Its
historical generic blockers are not a replacement for current E15-E/F/G/H source.
Legacy bootstrap/deploy mains remain retired. No unrestricted direct Terraform
or Terragrunt operation is introduced.

## Protected DOWN and failures

Installed E15-G order remains `edge -> apps -> platform -> data -> global`, one
original E2 owner/generation. Each child needs E15-C/D exact binary/JSON approval
and protected request correlation; independent DEV destruction and SQL data-loss
consent remain mandatory. Shared/secrets/security/backend/locking/evidence are
retained. Interrupted E2-R or E4 UNCERTAIN holds are never forcibly released.

DOWN-only structural blockers: common five-plan preparation, exact admin handoff
installation/version-read scope, authentic ECS drain/terminal handoff, E15-H NAT
callable-version authentication and executor/effect settlement, native ASG
inhibition/activities/termination finality, and exhaustive protected residual
adapter. E15-H's CAS cooperative source path is preserved intact; source permits
or a quiet snapshot cannot waive its installed denial. This increment builds no
NAT coordinator or substitute control plane. Manually disabling a rule, setting
concurrency/desired zero, waiting or observing no tasks is not a whole DOWN bypass.

Stop on any failure. Preserve UUID, exact plans, private state and operation
records. Use E2-R diagnosis and separately authorized readbacks/manual
reconciliation; do not resend an ambiguous mutation, adopt another owner or
force-destroy. Until complete DOWN is demonstrated, a full paid session has no
proved automatic shutdown path. The owner must decide whether to fund a bounded
UP experiment with explicit separately approved reconciliation/cleanup, or close
these installation/whole-DOWN gaps first. This document grants neither AWS nor
cleanup authorization.

Minimum decision: approve implementation of concrete staged publication/readback
under the existing protected administrator's staged
empty-account installation and choose the existing E15-H authentication/finality
installation path plus common-plan/residual adapters, or separately review a
DEV-only administrative shutdown procedure with genuine effect settlement.
Neither option can silently borrow WP5 authority or skip safety approvals. No
new coordinator is proposed by this increment.

## Residual costs and local artifacts

Running cost inventory: two NAT EC2/EBS plus allocated EIPs, SQL EC2/EBS, Fargate,
ALB hours/capacity, API requests, CloudWatch/Container Insights/flow logs/alarms,
KMS, Secrets Manager, ECR, S3 versions/requests and transfer. Retained control
CodeBuild/Lambda/storage may incur usage costs. No budget or current price is
assumed; estimate exact region/run-hours/resources before launch.

Resource absence in a state file is insufficient. Independently observe running
or stopped instances/root volumes/snapshots, allocated EIPs, service tasks/ENIs,
VPC Link ENIs, ALB, route ownership and schedules/controllers; classify retained,
deleted, pending, present or unverified. KMS/secret deletion windows apply only if
a separately approved owner deletes them; full DEV DOWN excludes their security
root. Out-of-band secret versions, images/logs/state versions are not automatically
cleaned. ECR retention remains unbounded under E8. No zero-cost claim.

Known E15-S2 cleanup CANDIDATES, not deleted: local TEMP `e15s2-checked-root`,
`e15s2-correction-root`, static/acceptance reports, `e15s2-correction-vm-evidence`,
application tar and smoke script; VM temporary `/tmp/e15s2-correction.ernBrr`.
These were offline artifacts, not evidence of AWS state. Private operator
configurations/directories outside the repository have not been searched or
removed. E15-S2 branch remains for traceability.

## Executed offline acceptance (2026-10-13)

**E1_REPOSITORY_ACCEPTANCE_PASS**; 959 regression + 24 WP7 = **983 E1/WP**,
AC1–AC16 all PASS, 42 suite/check records PASS, no gate errors. New thin entry
**12**; E2 **41**, E2-R **23**, E4 **28**, E13 **40**, E15-E **49**, E15-F **51**,
combined **39**, E15-G **54**, E15-H **54**, WP4D **33**, WP5 **49** passed.
Remaining registered suites/checks also passed. Nine extracted package identities,
protected security/workflow generation, source inventory and static IAM/trust/
PassRole invariants passed; canonical activation remains 0/11, 0/16, 0/8.
Final helper/test SHA-256 identities equal the evaluated gate source.

TFLint **24 warnings**, tfsec **46 findings**, identical to original protected
baseline by rule/severity/resource-or-message/path/location AND multiplicity;
no suppression, added/removed finding or original Terraform change. Tracked
Terraform fmt and Terragrunt HCL check-only fmt passed. Bash syntax **34** scripts
passed. Gate parsing Python **187**, JSON **50**, generated JSON-subset YAML **22**
passed; this is not a general YAML parser. ShellCheck/actionlint unavailable.
Diff whitespace and local KDD/immutable approved-contract checks passed. Results
were appended after the full gate, with documentation/whitespace checks rerun.

No AWS provider initialization/schema validation, AWS call, deployment, state
migration, image push or Git remote operation occurred. Prior E15-S2 VM evidence
of 99 .NET tests is retained; exact SHA-256 comparison confirms all 40 tested app/
global.json files equal this branch. It is prior evidence, not a new test run here.
No new full Docker image, SQL/KMS/ALB/API/NAT runtime result is claimed.

The bounded self-check confirmed exact revert provenance, original-source byte
preservation, absence of reduced-root references outside explicit historical/
absence tests, original closed request routing, no personal-credential fallback,
uncertain-result rejection and no plan/backend/IAM override. It also documented
the actual sanitized-preview limitation and unresolved greenfield admin adapter.
The full session remains **ORIGINAL_FULL_LIFECYCLE_PARTIAL_READY_FOR_INTEGRATION**;
source restoration/regressions are complete, installation and full UP/DOWN are not.
