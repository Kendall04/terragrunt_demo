# E13 NAT recovery reliability

## Current DEV installation and version transition

The security owner defaults `dev_nat_inhibited=true` and
`dev_delivery_inhibited=true`. The first holds exactly the three DEV NAT
handlers at reserved concurrency zero and the DEV NAT launch rule at `DISABLED`.
The second independently holds the DEV deploy gateway and cleanup function at
zero. Activating NAT must not resume gateway/cleanup. Both inputs pass from the
original security root to its generated controller-compute child; no
`ignore_changes`, alternative owner, backend or executor is introduced.
PROD concurrency remains one and its previously unspecified rule state remains
unspecified (`null`). WP5's `request-gateway/infra-dev` and
`request-gateway/infra-high-risk-dev` are different controllers from the installed
`request-gateway/deploy-dev`; their existing concurrency is unchanged.

Keep the three `aws_lambda_permission.wp4d_nat` and three
`aws_lambda_function_event_invoke_config.wp4d_nat` addresses and qualified-version
references unchanged. AWS provider 5.100.0 treats a qualifier change as replacement
of these auxiliaries, not replacement of the Lambda function. Review up to six
such DEV replacements explicitly in the future full security plan; this source
change authorizes none. No live state addresses have been inferred and no `moved`
blocks or parallel retained-version resource collections are added.

Published version 4, its packages and journals remain historical evidence. Its
immutable configuration points to the retired network, so retaining its invoke
grants is not a working rollback for the new VPC. During installation keep both
inhibition inputs true. Do not enable the rule or allow execution until all three
new numeric versions, exact bundle VersionIds, role bindings, rule permissions,
async retry/destination settings and target versions have been read back.
Before removing old auxiliaries, reconcile attributable accepted work and confirm
no remaining approved target, alias or event source can invoke the old version;
inhibition alone does not cancel queued work. If that cannot be established,
reject the replacement plan and preserve the current inhibited installation.
Never use a mutable alias or unqualified permission to bypass this check.

For an interrupted installation, keep concurrency zero and delivery disabled,
read the actual owner state/resources, and review a corrective plan with the
captured last-reviewed inputs and exact bundle versions. Restoring configuration
can publish another numeric version; do not claim Terraform rewinds to version 4.
Do not activate old network bindings or replay the historical SDC UNKNOWN. Until
a version bound to the new VPC has passed live tests, there is no demonstrated
operational NAT rollback. After such qualification, rollback means restoring the
last qualified configuration/bundle for that same network through a separately
reviewed owner plan, followed by fresh readbacks and tests.

The sequence is: inhibited security installation; separate global NAT PLAN-ONLY;
plan/budget approval; separately authorized E13 activation verified **before**
launch; apply the reviewed ASG plan; real EIP/route/SDC/forwarding and replacement
tests. An activation plan must contain only the approved inhibition changes,
with no bundle, launch binding, version, IAM or unrelated changes.
`dev_delivery_inhibited` stays true during NAT activation. The retained SNS topic's
`alias/aws/sns` key and absent subscriptions are a separate activation blocker:
approve a compatible CMK/service publication policy and confirmed recipient,
then demonstrate delivery. This increment changes no SNS/KMS configuration.
Offline checks prove declarations, not AWS permissions, delivery or rollback.

> **Closure status — 2026-10-16:** the early undeployed TARGET baseline below is historical.
> The [installed automatic B retrial](#installed-dev-correction-and-automatic-b-retrial)
> records the later live result separately from its failed predecessor. [Final
> DOWN](e16-practical-dev-lifecycle.md#final-real-dev-down-completed--2026-10-16-utc)
> subsequently removed both NAT slots and retained the original historical uncertainty/FAILURE
> evidence. The exact archived SQS message was acknowledged under separate owner approval; no
> historical attempt was relabeled successful. [Current inventory](portfolio-operations.md)
> records inhibited controllers and retained resources.

Repository implementation over integrated baseline
`72141a7f666ce058ce4d18eb3c3adc180e521ca4`. This remains undeployed TARGET:
all protected activation maps are empty. No live IDs, AMI rollout, forwarding
result, notification or recovery execution is asserted.

## Delivery containment

The default EventBridge bus matches `aws.autoscaling` / `EC2 Instance Launch
Successful`, exact account/region and the two administrator-bound ASG names.
It invokes each of the three independently authorized, published numeric Lambda
versions. This preserves the [WP4C](e1-wp4c-bounded-recovery.md) responsibility
split and journal; it adds no failover coordinator or cross-AZ mutation.

| Stage | Bounded handling | Retained evidence |
| --- | --- | --- |
| EventBridge cannot deliver to Lambda | At most 3 retries; event age 900 seconds | Environment `e1-wp4-<env>-nat-delivery-failed` standard SQS queue; original ASG event plus AWS error/rule/target/retry attributes |
| Lambda accepted an event but execution failed or aged out | At most 1 function-error retry; asynchronous event age 900 seconds | Environment `e1-wp4-<env>-nat-execution-failed` standard SQS queue; invocation record, request identity and failure context |
| Delivery to either failure destination itself fails | CloudWatch failure metric alarm | EventBridge `InvocationsFailedToBeSentToDlq` and Lambda `DestinationDeliveryFailures`; not a claim of retained payload |

Lambda throttling/system-error retry pacing is AWS-managed within the 900-second
queue-age bound. EventBridge and Lambda have separate age budgets; the runtime
also rejects launch timestamps older than 1,800 seconds or more than 60 seconds
in the future. Function-error retries do not reconstruct or resend an attempted
mutation: the existing journal first reconciles durable attempt/ACK evidence.
An unresolved attempt remains UNCERTAIN. Replaying a different ID is not a safe
way to bypass that boundary.

Queues use SQS-managed encryption, 14-day retention and `prevent_destroy`.
There is no queue consumer, redrive mapping, automatic replay, database or running
service. Revoking handler installations must retain their queues until the
administrator has archived/drained evidence; `prevent_destroy` blocks accidental
removal when activation keys disappear. Preservation beyond 14 days is an
administrator task, not indefinite storage.

The delivery queue permits only the exact environment rule with SourceArn and
SourceAccount. Execution identities gain only `sqs:SendMessage` to their own
execution-failure queue; there is no destination service principal grant in place
of that required identity permission. Queue drain/read authority is administrator
owned, with an explicit non-admin drain deny. TLS is required. Each environment
has independent queues, rules, functions, roles and notification targets.

Alarms route queue backlog and failure-to-retain signals to the existing
`demo-<env>-alerts` SNS topic. Sparse failure metrics use `notBreaching`; the queue backlog gauge
uses `missing` for absent data. These signals do not imply healthy forwarding.
Existing E7 gauge absence remains `missing`. Before activation the administrator must establish SNS topic,
subscription confirmation, CloudWatch/SNS/KMS publication permissions and an
actual delivered notification; the existing encrypted-topic configuration is
not proof of service publication. CloudWatch metric delivery is best effort.

EventBridge transforms the Lambda payload to id/account/region/time, fixed event
type/source and ASG/EC2 IDs. It excludes arbitrary detail/configuration fields.
The original service event on the delivery DLQ contains resource metadata, not
credential values. Operators must never insert credentials into manual event
payloads. Handler errors suppress SDK/exception text; readiness records contain
fixed diagnostic states and nonsensitive identity. Console output and IMDS tokens
are neither persisted in recovery evidence nor logged by the handler.

AWS model references: [EventBridge DLQs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-dlq.html),
[rule retry policy](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-retry-policy.html),
[Lambda async configuration](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-configuring.html),
[Lambda destinations and required execution-role permission](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-retain-records.html),
[EventBridge metric names/dimensions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-monitoring.html).

## Forwarding evidence

The separately owned [fixed bootstrap](../../scripts/nat/user_data.sh) installs
iptables under a 180-second command timeout, enables forwarding/loose reverse-path
filtering, persists the MASQUERADE rule and starts the service. It reads back
sysctl, the rule, active service and public-interface default route before writing
one `E13_NAT_BOOTSTRAP_V1 <instance> <epoch> CONFIGURED` console marker. Failures
emit a fixed failure marker. IMDSv2 supplies the instance ID through fixed bounded
curl calls; shell tracing is disabled and the token is discarded. Neither caller
commands nor arbitrary probe addresses exist.

The [read-only checker](../../scripts/nat/reliability.py) runs only after
`disable_sdc` has independently completed its existing duty. It cannot acquire
the other two handlers' mutation grants. The other handlers complete independently;
the checker waits for their observed EIP/route prerequisites rather than assuming
ordering. FAILURE and UNCERTAIN controller results now raise, so Lambda cannot
mistake them for successful asynchronous processing.

| Evidence level | Required observation | Meaning |
| --- | --- | --- |
| EC2/ASG exists/runs | Fresh exact InService/Healthy member and running instance | Membership prerequisite only |
| Protected launch/network membership | Independent VPC/subnet/AZ/ENI/EIP/route-table/profile/role/SG/AMI/template-version/user-data reads | WP4C/WP4D exact authority; event IDs do not enroll an instance |
| Network prerequisites | EIP associated to current ENI; single active private default route to that ENI; source/destination flag false | Recovery mutations read back successfully |
| Bootstrap completed | Matching decoded console marker, after LaunchTime and before console timestamp/current time; no failure/duplicate marker | Reviewed forwarding/NAT configuration completed at launch |
| Useful private-subnet forwarding | A separately observed request traversing the exact private subnet route and NAT EIP | `UNVERIFIED_LIVE_PROOF_REQUIRED` until genuine AWS traffic is observed |

The launch event's instance must be the independently resolved current member.
Stale events for a previous instance cannot repair a different replacement.
Malformed/wrong/missing metadata fails closed. The same event ID yields separate,
stable operation UUIDs for each duty, so native retries cannot silently create
new operations. The checker rejects absent bootstrap output, wrong instance,
stale/future timestamps, duplicate/failure markers, absent EIP/default route,
blackhole route, source/destination checking and late observations.

Verification has at most 12 passes, 110 seconds of total sleep and a 120-second
acceptance budget. An already-running SDK observation can finish beyond that
budget but cannot produce success. Existing 5-second connect/read timeouts with
one SDK attempt and the Lambda 600-second ceiling bound execution. API errors
surface to native async containment; they do not create a mutation polling loop.

Only `disable_sdc` additionally gains tagged own-environment
`ec2:GetConsoleOutput`. There is no SSM SendCommand, SSH, EC2 Instance Connect,
reboot, termination, user-data modification or generic EC2 administration grant.
[GetConsoleOutput](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_GetConsoleOutput.html)
returns an SDK timestamp; [botocore decodes its Output](https://github.com/boto/botocore/blob/develop/botocore/handlers.py).
Missing/truncated/delayed output is failure evidence, never an inferred success.

Success/failure readiness snapshots are content addressed under the existing
handler-owned `recovery/<env>/recovery/disable_sdc/<operation>/` namespace. They
preserve instance/launch identity or a fixed diagnostic, without raw console data.
The mutation journal's SUCCESS means its narrow action succeeded. The runtime
returns `forwarding: LIVE_PROOF_REQUIRED`; there is no global forwarding success
receipt or ASG health override. This is launch-time evidence, not continuous
iptables or egress monitoring. A later guest configuration failure needs genuine
network diagnosis; an old marker cannot prove present packet flow.

## Administrator replacement and patch procedure

The active [security foundation generator](../../scripts/tests/security_root/wp5.py)
uses exact `nat_launch_inputs.ami` and immutable reviewed bootstrap bytes. It has
no latest-AMI resolver or ignored AMI changes. The old floating/ignored templates
are inert [retired text](../../ci/authority/retired/terraform/infra/global/modules/nat/launch_template.tf.txt).
TARGET ASGs consume only administrator-published launch-template ID and positive
integer version; no `$Latest`, `$Default`, caller AMI, instance refresh or automatic
patch selection is introduced. Routine WP5 reconcile rejects execution-binding
changes, including ASG launch-template changes.

The `ReplacementAdmin` port and `replacement()` validator in the read-only checker
represent the separate administrator approval contract. The port must independently
observe the exact old/candidate launch versions and network/profile membership.
The approval binds environment/ASG, canonical old/candidate SHA-256 identities,
reviewed source commit and an explicit single-AZ maintenance outage. Caller JSON
cannot substitute for an authenticated port. This repository has no live port or
rollout implementation; the returned record is a reviewable approval projection,
not authorization to a runtime handler or evidence that AWS changed.

For this AMI patch procedure, candidate AMI and strictly newer numeric version may
change. Template ID, user-data hash, profile/role, SG, instance type, IMDSv2 policy,
public-IP/delete settings, tags and VPC/subnet/AZ/EIP/route table must stay exact.
Changing those immutable controls needs a separate reviewed security installation,
not this patch approval. Ordinary callers and NAT handlers receive no launch-template,
AMI, IAM, PassRole, refresh or instance termination authority.

1. Independently inventory both current slots, three handlers, queue/destination
   configuration, profile/SG membership and existing launch version. Select and
   verify an exact suitable AMI as the authenticated administrator; record its
   account/region/owner, compatibility and availability. Repository fixtures
   are not AMI selections. Test the fixed bootstrap on that AMI under a separately
   authorized experiment before approving production use.
2. Approve old/candidate hashes and the reviewed source commit through the separate
   administrator channel. Establish a maintenance window for one environment/AZ
   at a time. A one-instance ASG can interrupt that AZ's private egress; there is
   no promise of uninterrupted forwarding or cross-AZ failover.
3. Administrator alone creates/reads back the exact new launch-template version
   through the security-owned foundation. Update protected recovery publications,
   exact package/image installations and numeric ASG launch binding coherently;
   pause event delivery/ordinary global lifecycle during the transition and retain
   both failure queues. Do not leave incompatible versions of three handlers or
   let routine lifecycle attempt a forbidden execution-binding update.
4. Administrator performs the scoped ASG version update/replacement during the
   approved outage, and reconciles that administrator-owned transition with the
   protected global state/configuration. Alternatively use the existing separately
   approved teardown/create lifecycle, with its actual quiescence prerequisites.
   This is not a new runtime mutator. Reenable only the exact approved event rule
   after handler/configuration readback, then independently observe replacement
   ASG/EC2/ENI/profile/SG/user-data/template identity.
5. Observe all three narrow action journals and the readiness snapshot. Perform
   bounded HTTPS requests from an existing approved private-subnet workload in
   that AZ to a fixed administrator-approved diagnostic endpoint; independently
   bind subnet route, current NAT instance/ENI/EIP, timestamps and returned source
   IP. Missing/failed/ambiguous evidence leaves private-subnet egress UNVERIFIED.
   NAT-host Internet access or application health alone cannot satisfy this proof.
6. Verify destination containment and SNS delivery with a separately authorized
   nonsecret controlled failure. Do not proceed to the other slot/environment until
   readiness, end-to-end egress and notification evidence is retained. If rollout
   fails, administrator approves return to the exact previous template/AMI and
   publication identities and repeats live observations; rollback is unproven.

## Failure triage

Inspect the environment failure queue within retention, distinguishing EventBridge
message attributes from Lambda invocation context. Correlate event ID, qualified
handler ARN, deterministic operation UUID and immutable action/readiness journals.
Inspect attempt/ACK/receipt records before changing resource state. UNCERTAIN means
possible applied mutation, not permission to replay with a new event ID. Verify
current exact membership independently; an old event may name a departed instance.
Archive nonsensitive evidence before administrator deletion/drain. Expired events,
unknown effects and missing forwarding proof require administrator diagnosis and
fresh authorized observations. No automatic redrive is provided.

## Offline validation and shared surfaces

Run `python -I -B scripts/tests/nat/run.py` and
`python -I -B scripts/tests/nat/check_static.py`. The suite exercises actual
protected controller/SDK-shaped ports, both environments, failed controller results,
stable retries, late/wrong observations, AMI/version approval and authoritative
Terraform/package generation. The static checker evaluates the real retry,
destination, queue-policy and alert expressions with installed Terraform in a
disposable root containing only variables/locals. It does not load providers.
Both checks are included in the existing final acceptance gate, preserving its
983 accepted E1/WP tests. Run E7 monitoring regressions separately as well.

Shared integration surfaces: `wp4d.py`, `wp5.py`, WP4 runtime/transport, generated
controller/security foundations, `authority.json`, source inventory, final acceptance
gate, provider-free console readback helper/static checkers, exact compute-resource
assertion and KDD documents. Exact source-derived hashes must be regenerated after
integration, retaining empty activation maps. No E2 arbitration, Docker, application,
unrelated toolchain or peer branch changes belong to this checkpoint.

Offline checks cannot prove AWS provider schemas, console delivery timing, genuine
AMI compatibility, guest forwarding, Internet egress, queue retention/destination
permissions, SNS/KMS delivery or rollout/rollback behavior. Those remain explicit
administrator-owned live prerequisites.

## Local checkpoint evidence

The complete accepted offline regression executed 983 E1/WP tests. An old compute
resource-type assertion required the four exact new E13 primitives; after correction
the entire 24-test compute suite passed. The other 959 tests passed in the complete
run. The initial gate report preserves its failures; corrected full compute and
static-check reruns form the final composed verification report, without pretending
the initial gate passed. Production source remained fixed during those reruns.

All 40 focused E13 tests and eight E7 monitoring regressions passed. Actual E13,
WP4D, WP5 and WP6 Terraform expressions, IAM/trust/policy-size parity, deterministic
packages/installation gates, dev/prod symmetry, generated source, inventory,
Python/JSON parsing, runbook/KDD links, check-only Terraform formatting, Bash syntax
and diff whitespace passed. Provider-free console parsing accepts only the exact
Terraform acquisition/release status lines around its single JSON result; warnings,
extra values and duplicate status are tested rejections.

Optional `check_linux.py` could not run because PyYAML is absent. ShellCheck and
fresh supported Linux E3 evidence are not claimed; no dependencies were installed.
No AWS API, Terraform provider initialization, deployment, push, fetch or PR occurred.
One bounded self-check corrected the Terraform conditional type, Windows encoding,
exact resource assertion and console readback issues described above.

## Live DEV replacement trial and independent-duty guard correction

On 2026-10-16 UTC, the owner authorized one replacement per DEV slot through
its existing ASG with desired capacity unchanged at one. The original VPC,
two public/two private subnets, two slots, launch-template version 2, EIPs and
Lambda/EventBridge E13 architecture were preserved. This is observed DEV
behavior; it does not establish PROD readiness or automatic cross-AZ failover.

Slot A completed automatically: replacement membership and bootstrap were
verified, all three action attempts had matching ACK/readback/SUCCESS receipts,
and HTTPS from the original private subnet returned the slot's expected public
source address. Slot B replaced successfully and recovered its EIP and route,
but its SDC action failed before dispatch and retained an attempt without ACK.
Its execution-failure message and FAILURE evidence remain intact. Under separate
explicit owner authorization, an administrator changed only the replacement's
SourceDestCheck to false. Private-subnet HTTPS then succeeded with B's expected
public source address. **B is a manually repaired failed automatic trial**, not
an automatic recovery success. No failed event was redriven or force-settled.

The B timeline established a pre-dispatch race: the SDC intent saw no EIP
association; the concurrent EIP duty completed its own association after the
SDC attempt was retained. The original guard compared the entire context,
including the other duties' mutable results, and rejected SDC before its EC2
call. CloudTrail, the retained attempt and the missing ACK agree with this
ordering; IAM readback did not identify a missing EC2 permission.

The three DEV bundles now select `scripts/wp4d/dev_nat_guard.py` through the
existing package overlay. Each guard still obtains a fully validated fresh
ASG/EC2/ENI/VPC/subnet/AZ/spec context, requires identical protected membership,
and rejects a change to its own mutation's prior state. The route duty also
requires unchanged default-route existence. Only progress of the other two
fixed duties is excluded from that comparison. Final operation-attributed
readbacks, attempts/ACKs, no-blind-resend behavior and UNKNOWN retention remain
unchanged. Common recovery code and every non-DEV-NAT package retain their
original bytes and identities. There is no new coordinator, storage authority,
EC2 action or retry path.

Five focused tests exercise the actual emitted bundles: the original race,
independent progress at plan/attempt persistence boundaries, rejection of own
state/membership/route-existence changes, uncertain retries without another
dispatch, and selection restricted to the three DEV packages. The NAT suite
contains 45 tests. Offline passing tests do not prove that the installed runtime
has changed or that a subsequent automatic replacement will succeed.

Installation must use fresh content-addressed, versioned bundles and reviewed
exact-version read bindings. Preserve earlier packages/Lambda versions, the
failed B journal and its queue message. Verify configuration, numeric EventBridge
targets and failure destinations before enabling delivery. Inhibiting delivery
is not cancellation of an issued AWS effect. A fresh live replacement of the
current instance requires its own destructive authorization; replaying the old
failed operation is not an acceptable test. DEV remains running and billable.

### Installed DEV correction and automatic B retrial

After the separate owner authorization and [CI 38835661671 SUCCESS](https://github.com/Kendall04/terragrunt_demo/actions/runs/38835661671),
source `57c8c0b46f875d60b5144040309d5e3d2bf2c3c6` was installed through the existing
neutral security root. The reviewed saved plan made exactly six in-place updates:
three bundle references and their three exact GetObjectVersion reader bindings.
All three handlers now use numeric version 4 with their previous OCI image,
unchanged action permissions and exact event source. New bundle/version bytes,
retry settings, failure destinations and targets were read back before resuming
delivery. Old immutable packages/versions remain. CreateOnly was unchanged;
no stable installation record, trust, PROD or five-layer DEV state was rewritten.
The existing neutral-state installation associations were reconciled, preserving
old AWS versions and evidence. Simulations allowed each new exact bundle version
and denied its old bundle and a wrong VersionId; actual new Lambda execution
subsequently demonstrated successful loading of the installed bundles.

The separately authorized second B replacement terminated only the repaired old
instance through its existing ASG, retaining desired/min/max one and LT version 2.
The fresh replacement completed **automatically**, without administrative SDC/EIP/
route repair. E13 recorded matching attempt/ACK/APPLIED and SUCCESS receipts for
assign_eip (`5846e5d3-36e0-5f56-8146-02c65c3e72de`), change_rt
(`a6f352f7-db64-538f-8abc-b71607810cac`) and disable_sdc
(`e4a6f249-0581-5ef1-86f9-69bfce8c3535`). Bootstrap readiness was independently
verified. Private-subnet HTTPS before and after returned HTTP 200 with the same
expected B EIP and verified TLS; both temporary tasks stopped with exit code zero.
A remained Healthy/InService. This proves the original A trial and the corrected
B trial, not a new A replacement on version 4 or uninterrupted cross-AZ egress.

The old B FAILURE versions and exact original queue message/body were reread and
remain retained, without ACK, redrive, deletion or forced SUCCESS. The terminated
old B root volume was confirmed absent. Final AWS checks found the expected three
running project EC2 instances (two NAT plus SQL). Green:8 still serves the original
application digest, blue:9 has no tasks/targets, the temporary cleanup rule is absent,
and E2 generation 14 is RELEASED. A fresh POST/GET SQL/KMS round trip and /ready
passed. No new deployment, rollback, DOWN or PROD operation occurred in this trial.

Local acceptance passed all 983 E1/WP tests, AC1-AC16 and all 44 gate checks;
the focused NAT suite passed 45 tests. Real GitHub acceptance, hygiene and static
infrastructure jobs passed. CI compared the existing 24 TFLint and 46 tfsec findings
by identity/multiplicity/source with no additions or suppressions. Actual Terraform
1.13.4/AWS provider 5.100.0 validation and saved-plan application completed for
this installation. Source inventory and package generation passed; only the three
DEV NAT package identities changed. Raw runtime evidence remains outside Git.
DEV and retained resources continue billing. Final DOWN and SQL/EBS loss still
require their independent destructive confirmations.
