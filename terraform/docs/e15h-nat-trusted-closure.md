# E15-H trusted NAT admission, cooperative closure and effect settlement

## Status and owner decision

Source increment, 2026-10-12. Initial main/HEAD:
`57e18b9f29439c27d6edd6ad1b41598205e76536`. Existing worktree:
`C:/proyectos/terragrunt_demo-wt-batch1`; branch
`codex/e15h-nat-trusted-closure`. No infrastructure has been deployed.
No AWS operations, including reads, installation, identities or provider init.
Public AWS documentation was consulted; that is not service validation.

**PARTIAL:** the cooperative source path now has atomic admission/closure,
accounted dispatch, authenticated-identity contracts and E13 response/attempt
references. An additional approved narrow runtime authority is unavoidable:
a **DEV NAT admission coordinator**, sole writer of one protected CAS object,
with a separately installed caller authentication boundary. It must authenticate
trusted instrumentation, not accept role/version/incarnation claims from event
JSON. No credential, role, policy, endpoint or authentication implementation was
installed or activated. A Python port/subclass is not authentication evidence. Coordinator methods are
protected in-process core logic, not a deployed RPC API. A future server adapter
must authenticate the fixed close caller and independently read the original E2
owner plus protected whole-operation manifest/global child. It must never
serialize an E2 Authority object as a transferable grant, nor trust a caller's
manifest digest without protected readback. Its transport/server wiring is an
explicit remaining installation task, not source-level authenticated AWS proof.

Minimum owner decision: approve this one DEV-only duty, its exact storage/E2-read
capabilities below, independently authenticated caller binding, immutable reviewed
code and security-root ownership. Approve a separate existing administrator's
bounded DEV inhibition operation. Do not approve general lifecycle/E2 takeover
rights. This decision does not establish effect finality, authorize a first AWS
experiment, or enable full DOWN. Finality/coverage installation evidence is still
required. A lost EC2 response may remain permanently UNKNOWN under this contract;
no promise is made that every shutdown can complete without administrator diagnosis.

## Selected mechanism and invariants

[`closure.py`](../../scripts/nat/closure.py) uses exactly one versioned S3 object:
`e1-wp4-dev-<account>-<region>/nat-admission/dev/head.json`. It retains a finite
epoch UUID, exact config digest, released E2 anchor, monotone revision, all permits
(maximum 128), and one irreversible CLOSED record. No initialize, delete, lease,
prune, reset, takeover or reopen API exists in runtime. Saturation denies.
An administrator seeds an epoch while E2 is RELEASED; subsequent epoch replacement
is not implemented and must never discard an unresolved predecessor.

**Linearization point:** admission appends an ADMITTED permit using PutObject
If-Match against this object's ETag. Closure changes OPEN to CLOSED using the
same object's If-Match. At most one conflicting update succeeds. A later
admission cannot overwrite a closure; an earlier successful admission remains in
its permit map. Failed/ambiguous writes require exact canonical protected
readback; no blind retry. Revision changes prevent content ABA. VersionId and
SHA-256 are evidence identities; ETag is the conditional token. Missing encryption,
VersionId, unavailable reads, wrong scope or conflicting readbacks deny.

The E2 object and NAT head are **not** a transaction. E2 reads gate ordinary
admission and pre-dispatch, but their final-read race is not claimed solved.
DOWN first retains its ACTIVE original owner, then closes NAT before any
five-layer destructive dispatch. A handler that observed RELEASED before E2
acquisition either wins NAT admission before CLOSED and is retained, or loses
the NAT CAS. Therefore the closure's accounting does not require atomicity
between two S3 objects. No NAT writer can alter E2. The installed coordinator must
keep this ordering; starting Terraform before NAT closure is forbidden.

Permit states: ADMITTED -> DISPATCHED -> SEALED, or ADMITTED -> CANCELLED.
DISPATCHED means permission to issue one call has been durably accounted, **not**
that the wire call is known sent. It is persisted before the actual EC2 boundary.
Only the same authenticated invocation incarnation/version/duty may transition
its permit. A CLOSED head prevents any ADMITTED -> DISPATCHED transition; a
pending admitted executor can cancel its unused permit. A paused executor that
already won DISPATCHED remains a blocker until its own cooperative seal.
A dead/crashed executor's record never expires. There is no forced seal API.

`Authentication.executor` requires role unique ID, numeric qualified Lambda ARN,
package SHA-256 and invocation UUID from trusted installed context. The version
must match the protected per-duty publication. This rejects old or uninstrumented
versions in the supported path. The publication alone does not prove it enumerates
all callable code. Lambda resource policies/IAM can constrain callers, but the
Lambda payload is not authenticated invocation provenance. In particular,
`lambda:SourceFunctionArn` is not a qualified-version attestation. An installation
must solve and verify this boundary; merely copying claims into an RPC is rejected.

## Runtime and E13 integration

`Cooperative` implements the actual `NatRuntime` interface around the fixed WP4D
`aws_runtime.Nat` transport. It validates the existing immutable E13 plan/attempt
(including VersionId and exact token/request digests) before admission. It does
not replace E13 journaling, stable EventBridge-derived operation UUIDs, membership
resolver, no-blind-resend behavior, three exact EC2 duties, ACKs or fresh readbacks.
Ordinary recovery outside teardown remains unchanged: default installed `_nat`
still uses E13's accepted transport. Wiring the new wrapper is deliberately
uninstalled; it must be installed across every capable DEV version before use.
No PROD wiring/policy or shared authority is changed.

Actual source entrypoints inspected: installed `scripts/wp4d/runtime.py:handler`
-> `invoke` -> `_nat` -> `recovery.Nat` -> fixed `aws_runtime.Nat.mutate`.
Historical `terraform/infra/global/modules/nat/lambda/{assign_eip,change_rt,
disable_sdc}.py:lambda_handler` remain uninstrumented source. Their prefix/tag/
first-instance selection, route fallback/retry and SDC delayed tag lookup do not
satisfy closure. They must have no capable callable AWS installation; a source
retirement record cannot prove that. E15-H intentionally does not retrofit or
activate those historical entrypoints. All three numeric installed targets, any
alias/$LATEST, outstanding invocation and exceptional path require authentic
coverage. No live callable version has been certified.

At the real EC2 boundary, `DispatchEvidence` writes one narrow E13 extension:
`recovery/dev/recovery/<duty>/<operation>/<duty>/api-response`. It retains sanitized
SDK request ID/association ID when returned, exact token/request digest and verb;
missing service IDs remain explicit null. No raw AWS payload or sensitive data is
retained. A crash after remote success before that record or ACK leaves DISPATCHED.
Existing E13 plan/attempt/ACK/observed/reconciled formats are unchanged.

A SEALED permit requires return from the synchronous fixed transport, matching
versioned E13 plan/attempt/ACK/response references, and independent E13 APPLIED
readback. Single-use permit state prevents another dispatch from this capable
cooperative path. It means **that permit's future dispatch capability is closed**,
not that the Lambda process was killed or all its published versions were disabled.
A retry with a new incarnation cannot take an old permit. E13 can independently
recover/reconcile its attempt; that is not permission to seal a crashed executor.

## Dispatch race disposition

| Boundary | Implemented result / required installed evidence |
| --- | --- |
| A: reads open then pauses before admission | same-head CAS loses to closure; no permit/call |
| B: admitted, pauses before dispatch | discoverable ADMITTED; close rejects dispatch; own cancellation or UNKNOWN |
| C: SDK call in flight at close | DISPATCHED already durable; closure includes it; no guessed drain |
| D: crashes after dispatch before result | retained DISPATCHED + E13 attempt; UNKNOWN, independent diagnosis |
| E: response lost though applied | UNKNOWN; matching snapshot is not finality; no resend |
| F: old version callable | publication rejects on cooperative path; complete callable inventory/revocation remains mandatory |
| G: delayed delivery/retry | CLOSED rejects new admission; E13 reconciles prior token; no second mutation |
| H: native ASG replacement | independent native inhibition/activity/instance contract; handler fence alone insufficient |

## Remote-effect finality contract

Admission, executor seal, API return, APPLIED observation, remote settlement and
native-controller inactivity are distinct. Reports expose each separately; they
never emit quiet=True or grant execution. No source adapter currently certifies
remote finality or AWS executor termination. For normal successful cooperative
calls, a future accepted adapter must validate the exact service response and
fresh EIP association/route next-hop/SDC state after all capable executors are
sealed and native activity inhibited. Attribution binds the immutable E13 attempt,
request/response IDs and resource membership. An ACK or a resource snapshot alone
is insufficient. Expected absence must be independently definitive, not inferred
from a failed client call or briefly missing resource.

The public APIs for AssociateAddress, CreateRoute, ReplaceRoute and
ModifyInstanceAttribute expose responses/request identities; they do not expose a
per-request cancellation/drain/status-query protocol for lost responses. EC2 reads
are eventually consistent. **Inference:** these docs do not justify converting a
lost response plus a matching snapshot into terminal settlement. For ambiguous
calls, an independent service-attributed terminal reconciliation and trustworthy
executor-end evidence are required, or UNKNOWN stays held. No timing delay,
Lambda timeout, concurrency zero, E2-R interrupted-owner report, E4 UNCERTAIN,
queue approximation, ACK, or fake certifies these missing guarantees.

Verified public references (no live service operations):
[S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html),
[EC2 eventual consistency](https://docs.aws.amazon.com/ec2/latest/devguide/eventual-consistency.html),
[AssociateAddress](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_AssociateAddress.html),
[CreateRoute](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_CreateRoute.html),
[ReplaceRoute](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ReplaceRoute.html),
[ModifyInstanceAttribute](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_ModifyInstanceAttribute.html),
[Lambda concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html),
[SourceFunctionArn limitations](https://docs.aws.amazon.com/lambda/latest/dg/permissions-source-function-arn.html),
[ASG processes](https://docs.aws.amazon.com/autoscaling/ec2/userguide/as-suspend-resume-processes.html),
[ASG suspension considerations](https://docs.aws.amazon.com/autoscaling/ec2/userguide/suspend-resume-considerations.html).

## Native ASG inhibition

Source has two DEV groups `demo-dev-asg-nat-a` / `demo-dev-asg-nat-b` in
`terraform/modules/target/dev/global/wp5-nat.tf.json`, capacities 1/1/1, protected
numeric launch versions and public subnets, termination/instance dependencies.
There is no checked-in refresh policy, lifecycle-hook drain, termination-success
mutation handler or queue consumer. EventBridge launch triggers the three duties.

[`native.py`](../../scripts/nat/native.py) produces a fixed administrator plan,
not an execution method: under original E2 and durable UNKNOWN attempts, inhibit
EventBridge, close NAT admission, capture full group/instance/activity inventory,
SuspendProcesses Launch/AlarmNotification/AZRebalance/ReplaceUnhealthy/
ScheduledActions/InstanceRefresh on each exact group, read back suspension, then
UpdateAutoScalingGroup MinSize=0/MaxSize=0/DesiredCapacity=0. Leave Terminate active
so scale-in can finish. Do not force-delete, detach, disassociate EIP, remove
routes or resume processes. Handle preexisting refresh/scaling/lifecycle activity
as UNKNOWN until attributable terminal evidence; suspension is not retroactive
cancellation. Unexpected hooks, warm pools, policies or standby members block.

The SDK-shaped observer exhausts scaling activity pagination, rejects nonterminal
or missing-EndTime activity, independently reads current plus pre-inhibition
instances and requires actual terminated state. Desired zero with live members
blocks. Missing/foreign membership and controller reactivation block. Successful
activity status and a terminal snapshot still report service_finality=UNPROVED.
Keep EIP allocation and route-table ownership for protected global destroy; their
references may become blackholes during termination. Existing E15-F conservative
route/EIP diagnostic remains blocked; no premature unassociation is introduced.
Terraform destroy follows final inhibition/settlement only; no intervening apply
can restore capacity 1. Its provider behavior and deletion with suspended Launch
require a genuine first-install test. No provider-backed claim is made offline.

## E15-G guard

E15-F `Quiescence` optionally accepts the exact coordinator tied to the same E2
Store and NAT configuration digest. Its existing request/diagnostic UNKNOWN is
persisted first. The closure is bound to original owner/generation, account/region,
exact global child request and E15-G whole-operation manifest digest; no child E2
acquisition occurs. Fresh close/readback is retained in the existing protected WP5
operation namespace. Original E2 checks bracket it. All subsequent network checks
reuse CLOSED; there is no closure release before or after any stage.

The guard retains its unconditional installed-settlement denial even with all
cooperative permits SEALED. Synthetic coordinator/coverage/effect flags cannot
pass it. InstalledNAT, whole DOWN, five-plan preparation, residual observers and
`down-execute` remain blocked. E15-C/D exact plans and both destruction/SQL-loss
confirmations are unchanged. No new Terraform execution authority exists.

## Least-privilege proposal, NOT installed

Let A/R be the exact installed DEV account/region, B=`e1-wp4-dev-A-R`,
L=`e1-lifecycle-dev-A-R`, Q=`environment-lifecycle/infra-high-risk-dev`.
Real resource IDs, ASG UUID ARNs and role unique IDs must come from protected
security-root installation, not these symbolic source names. Region-limited
Describe APIs that do not support resource ARNs require Resource=* only for the
listed read action, never a service wildcard. Every row needs security-root
approval and live positive/negative DEV/PROD verification.

| Trusted principal | Exact proposed API action | Scope and conditions | Storage / capability | Live verification |
| --- | --- | --- | --- | --- |
| New DEV NAT coordinator execution identity (proposed `e1-nat-admission-dev-exec`) | s3:GetObject, s3:GetObjectVersion, s3:PutObject | `arn:aws:s3:::B/nat-admission/dev/head.json`; sole writer, TLS, SigV4, AES256, Put requires s3:if-match; no delete/version delete/lifecycle/multipart | one versioned head; CAS read/write, no runtime seed | bucket versioning/private ownership, conditional contention/lost ACK/exact version |
| Same coordinator | s3:GetObject, s3:GetObjectVersion | `arn:aws:s3:::B/arbitration/dev/application.json` | E2 read only; no owner seizure/release | reject active/foreign generations; deny E2 writes |
| Same coordinator | s3:GetObject, s3:GetObjectVersion | `arn:aws:s3:::B/recovery/dev/recovery/{assign_eip,change_rt,disable_sdc}/*` as three separate exact prefixes | independent existing E13 evidence read | attempt/ACK version/body mismatch denies |
| Same coordinator's future close server adapter | s3:GetObject, s3:GetObjectVersion | `arn:aws:s3:::L/operations/Q/*/whole-down` only; original owner/manifest/global child readback; TLS/SigV4 | protected E15-G intent read only, no WP5 evidence write | reject caller-supplied manifest digests and serialized E2 grants |
| Three exact DEV NAT execution roles | existing immutable s3:PutObject/GetObject/GetObjectVersion in their own E13 prefix; future coordinator transport only after authentication design approval | fixed duty, existing retry-free EC2 duties/DEV membership; no direct NAT-head or E2 write | `.../<duty>/*/api-response` lies inside existing own journal prefix; no new blanket write grant | service request identity, foreign duty/version/incarnation rejected |
| Existing protected WP5 high-risk DEV runner | s3:GetObject, s3:GetObjectVersion on exact NAT head; authenticated close-only coordinator request after transport approval | original E2 owner + exact manifest/global child; no raw head write or reopen | existing `arn:aws:s3:::L/operations/Q/*` immutable diagnostic; no alternate prefix | stale closure / child / lost owner denied |
| Separate existing installation administrator, NOT NAT roles | events:DisableRule, events:DescribeRule, events:ListTargetsByRule | `arn:aws:events:R:A:rule/e1-wp4-dev-nat-launch` | inhibit/read only this DEV rule | target IDs, old targets, unchanged PROD rule |
| Same administrator | lambda:PutFunctionConcurrency, lambda:GetFunctionConcurrency, lambda:GetFunctionConfiguration, lambda:GetFunction, lambda:ListVersionsByFunction, lambda:ListAliases, lambda:GetAlias, lambda:GetPolicy, lambda:ListFunctionEventInvokeConfigs, lambda:GetFunctionEventInvokeConfig | exact three `arn:aws:lambda:R:A:function:e1-nat-recovery-nat-dev-<duty>` plus explicitly enumerated numeric version/alias ARNs where supported; aws:RequestedRegion=R | configuration/version/permission/retry evidence; concurrency zero is inhibition only | all published versions, aliases, role/code SHA, policies, targets, pending retries; no cancellation inference |
| Same installation administrator, only if historical versions exist | lambda:DeleteFunction | exact enumerated **obsolete numeric version** ARNs of the three DEV functions; never unqualified ARN, current approved version, PROD or shared | optional retire old callable capability; no cancellation claim | first verify alias/target references; already running old executors still require independent finality |
| Security-root read-only installation reviewer | iam:GetRole, iam:GetRolePolicy, iam:ListRolePolicies, iam:ListAttachedRolePolicies, iam:GetPolicy, iam:GetPolicyVersion | exact three DEV handler roles, coordinator role, WP5 close caller and explicitly attached policy ARNs; no IAM write grant | authenticate unique IDs, effective authority and permissions-boundary/PassRole source review | reject broader callers or old capable code; incomplete effective invocation coverage blocks |
| Same administrator | autoscaling:SuspendProcesses, autoscaling:UpdateAutoScalingGroup | two exact installed `arn:aws:autoscaling:R:A:autoScalingGroup:<uuid>:autoScalingGroupName/demo-dev-asg-nat-{a,b}` | only fixed process/capacity plan; no ResumeProcesses/ForceDelete | suspension plus zero capacities; ongoing activity still blocks |
| Same administrator | autoscaling:DescribeAutoScalingGroups, autoscaling:DescribeScalingActivities, autoscaling:DescribeInstanceRefreshes, autoscaling:DescribeLifecycleHooks, autoscaling:DescribeWarmPool, autoscaling:DescribePolicies, autoscaling:DescribeScheduledActions | Resource=* for these exact read APIs; aws:RequestedRegion=R; application supplies exact two groups and exhausts pagination | complete native-controller/membership inventory | unexpected native controller blocks; prior instances terminal |
| Same administrator / future read-only finality observer | ec2:DescribeInstances, ec2:DescribeNetworkInterfaces, ec2:DescribeAddresses, ec2:DescribeRouteTables, ec2:DescribeLaunchTemplateVersions; ec2:DescribeInstanceAttribute | first five exact read actions Resource=* with R; InstanceAttribute exact enumerated DEV instance ARNs + existing Environment/Role constraints | membership/EIP/route/SDC read; no EC2 mutation expansion | attributable fresh reads after seals; conflicting or ambiguous effect remains UNKNOWN |
| Security root human installation owner only | separately reviewed existing provisioning path; no new IAM privilege granted in E15-H | exact coordinator trust/role/transport/code/head seed and private bucket deny exception | administrator-owned publication; no E2 write delegation | evaluate actual IAM/trust/PassRole and versioned source identity |

The existing evidence-bucket lifecycle-writer deny and current role policies do
not authorize this new head. Change only the exact head exception for the approved
coordinator; preserve all other denies. S3 IAM can enforce conditional headers but
cannot enforce JSON transition semantics; that is why sole approved coordinator
code, rather than handler raw PutObject access, is necessary. No `ec2:*`,
`lambda:*`, `autoscaling:*`, `s3:*`, admin IAM, PROD or shared policy expansion.
There is deliberately **no fabricated lambda:InvokeFunction grant**: transport and
trusted caller context must first be selected/verified. A Lambda RPC payload alone
cannot satisfy the Authentication port. Approving raw claims would weaken E1.

## Installation/readback checklist

1. Security-root owner approves narrow duty, authenticated transport, role unique
   IDs, immutable bootstrap/package/code SHA and exact DEV identities; verify
   versioned private conditional/no-delete storage, region/account and bucket denies.
2. Enumerate every numeric version, `$LATEST`, alias/routing weight, function policy,
   identity policy capable of invocation, cross-account delegation, EventBridge
   target/qualifier, async config, retry destination and historical installation.
   Disable/remove uninstrumented capability with separately approved admin actions
   or block. Updating latest does not change a published version. Target inventory
   alone does not enumerate invokers. Existing DEV/PROD privileges stay separate.
3. Verify each capable DEV version's three mutation duties, exceptional paths,
   authenticated incarnation and sole coordinator-mediated admission/dispatch/seal.
   All old E13 attempts without permits require independent inventory/reconciliation;
   an empty newly seeded head cannot certify earlier effects or earlier invocations.
4. Inhibit rule/new invocations and perform protected closure under original E2.
   Delivered events, async retries, DLQs and delayed calls remain relevant. Empty
   approximate counts are never total-drain evidence. Preserve E13 alerts/diagnostics.
5. Capture and inhibit both ASGs using the fixed sequence, exhaust activities,
   refresh/hook/warm-pool/policy checks, observe every prior/current instance.
6. For each permit and every historical attempt, authenticate cooperative seal or
   independent executor-end proof, then attribute and settle each issued effect.
   Unknown at either boundary blocks, with original E2/closure retained. No resend.
7. Fresh readbacks and current coverage/native inhibition must agree at every
   guarded stage through protected global teardown. Reactivation invalidates proof.
   Archive retained journals/closure; never reopen or discard unresolved history.

## Offline acceptance and limits

Run `python -I -B scripts/tests/nat_closure/run.py` and the full existing acceptance
gate. Tests use conditional storage fakes and deterministic barriers/faults, the
real E13 controller, WP4D NAT transport, exact E15-G operation and WP5 guard.
Supported positive outcomes are cooperative permit seals and terminal observed
ASG snapshots. They are not installed AWS executor/effect-finality certificates.
The production default still denies; there is no positive full DOWN test.

E15-H intentionally implements no general scheduler, five-plan preparation,
residual observer, forced E2 recovery, deployment, new roles/policies/resources,
PROD mutation, IAM activation, EC2 resend or unrelated infrastructure repair.
Results and bounded self-review are recorded below after execution.


## Bounded self-review

One source review found a reproducible material defect: after an E13 success, the
SDK wrapper still retained its armed token, allowing an accidental second call
through that object. The repair consumes the exact request/token before dispatch,
checks the duty/verb/request and protects local single use. Its process-local
mutex only prevents duplicate SDK entry; the distributed authority remains the
S3 CAS head. Tests 53/54 prove reuse and unadmitted SDK calls deny. The complete
54-test focused suite passes after this repair. Initial test bring-up also corrected
the actual E13 token/plan path and fixture import paths. No reviewer agents used.

The full regression's transitive-package check also exposed a WP4D dependency on
WP5's whole-operation module via the former quiescence scope import. The repair
extracts only unchanged closed scope/verb/read constants into `nat/scope.py`;
WP4D receives that narrow dependency, and WP5 retains its operation dependency.
No lifecycle executor is added to a NAT package and no transitive import is waived.
This is a regression-driven integration correction within the same bounded review.

The completed gate also found two historical E15/E15-C authority fixtures that
normalized only the eight WP5 package hashes. E15-H adds dormant reviewed source
to WP4D too. Both fixtures now normalize exactly WP4D/WP5 derived package hashes
and compare all remaining authority fields against the immutable baseline digest.
Package digest validation itself remains independently enforced by source/package
checks. No policy/installation/binding change is exempted. The original completed
run passed every other suite/check; it is not reported as a successful gate.


## Final completed validation

Final repaired gate: **E1_REPOSITORY_ACCEPTANCE_PASS**, **983 E1/WP**
(959 regression + 24 WP7), **AC1-AC16 PASS**. All **18 suites and 23 sequential
checks (41 result entries)** pass with no skipped tests/errors. Initial runs with
the documented transitive-dependency/authority-fixture defects are not acceptance
evidence; the final full gate reran after all repairs on unchanged executable bytes.

| Executed suite | Tests | Result |
| --- | ---: | --- |
| E15-H | 54 | PASS |
| E2 | 41 | PASS |
| E2-R | 23 | PASS |
| E4 | 28 | PASS |
| E7 | 8 | PASS, independent runner |
| E8 | 18 | PASS |
| E11 | 33 | PASS, independent runner |
| E13 | 40 | PASS |
| E14-B | 19 | PASS, independent runner |
| E15 | 30 | PASS |
| E15-B | 42 | PASS |
| E15-C | 46 | PASS |
| E15-D | 50 | PASS |
| E15-E | 49 | PASS |
| E15-F | 51 | PASS |
| E15-E/F combined | 39 | PASS |
| E15-G | 54 | PASS |

Parsing: **184 Python, 50 JSON, 22 generated JSON-subset YAML**. Source inventory,
protected package SHA-256, security-root/workflow generation, IAM/trust/PassRole,
DEV/PROD isolation, KDD links, immutable accepted E1 hashes and Terraform fmt pass.
All **16 WP4D + 8 WP5** final packages imported the new modules from extracted
package bytes under hermetic guards. Authority changed only these 24 derived
package digests; all other authority fields and activation maps match main.
177 baseline Terraform/HCL/JSON files compared: only authority.json differs,
solely those derived package digests. No generated IAM/trust/PassRole/source
policy or Terraform/Terragrunt wiring changed; activation remains 0/11, 0/16, 0/8.

Fresh static identity/multiplicity comparison against accepted E15-G evidence:
**24 TFLint warnings / 46 tfsec findings**, exact identities and multiplicities,
no additions/removals/suppressions. Terraform and Terragrunt check-only formatting
pass. **34 Bash syntax checks** pass using preinstalled Git Bash. ShellCheck,
actionlint and native YAML parser are unavailable; no result is claimed for them.
No tool or dependency installed, no provider schema/live plan/init performed.
`git diff --check` passes. One bounded self-review plus reproducible integration
repairs are recorded above; no additional reviewer agents used.

Local evidence files:
`C:/Users/PC/AppData/Local/Temp/e15h-final-repaired-acceptance-20261012/acceptance.json`,
`e15h-static-package-comparison.json` (static comparison),
`e15h-final-package-import.json` (final extracted package identities),
`e15h-final-source-identity.json`, `e15h-preserved-iac.json`, and independent
`e15h-e7.log`, `e15h-e11.log`, `e15h-e14b.log` in that same Temp directory.
Reports stay outside the repository. Executable source hashes were verified unchanged immediately after the completed
gate. Staging then exposed a trailing blank line at EOF in the new scope module
(untracked files were outside the gate's unstaged diff check). Only that redundant
newline was removed; all executable statements are unchanged. Its 24 derived
package hashes/inventory were reconciled, then affected focused/recovery/approval
suites and package/static admission were rerun. That final formatting repair is
not represented as a new full-gate execution. Documentation receives a separate
link check and the final staged diff receives whitespace validation before commit.

Delivery is one local commit on `codex/e15h-nat-trusted-closure`, starting at
`57e18b9f29439c27d6edd6ad1b41598205e76536`. Final revision is reported after
commit and clean index/worktree verification. Main remains unchanged. No new
clone/worktree, fetch, push, PR, merge, AWS read/write, external identity activation,
IAM installation, provider initialization, deployment or teardown occurred.

**Explicit answer:** normal DEV NAT shutdown now has a credible bounded
cooperative source core for ordered admission, executor-permit closure and
E13-attributed effect observation. **An additional approved narrow runtime/control
authority is still unavoidable:** the sole-writer DEV NAT admission coordinator
with authentic version/incarnation and close-caller/manifest readbacks. That
approved installation plus complete callable-version coverage and accepted
remote-effect/native-controller finality evidence remains necessary. The code
cannot yet produce an authenticated installed closure/settlement grant. Five-plan
preparation and residual observation also remain missing. Full DEV DOWN readiness
is not claimed. Safe source integration is partial; genuine AWS validation must
be separately authorized after owner/security-root approval.
