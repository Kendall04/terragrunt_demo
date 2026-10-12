# E4 — bounded post-switch continuation

CURRENT repository contract; AWS has never been deployed. This covers one
representative failure, not general rollback or compensation. It builds on
[E1 delivery](e1-wp4b-normal-delivery.md), [existing-content recovery](e1-wp4c-bounded-recovery.md)
and [E2 arbitration](e2-environment-mutation.md). Qualification, current eligibility,
independent production approval and the accepted E3 gate are unchanged.

## Selected failure and ordering

Starting state: listener serves the protected former active color; candidate rule
points to the other color. Intended terminal state: listener serves the qualified
candidate's exact revision/cohort, candidate rule points to the former active
target, the fixed enabled cleanup schedule carries this E2 generation, all seven
effects support an immutable success receipt, then protected history/dev activation
and public completion are published before E2 terminal/release.

Actual controller order is register, drain, attach, start, E3, listener switch,
candidate rule, cleanup schedule, success receipt. The installed adapter publishes
the color history index (there is no separate normal-delivery current-release
pointer), dev activation and public completion afterward. Cleanup itself comprises
PutRule then PutTargets; these are not a transaction.

Selected intermediate state: the exact listener switch succeeded and its
operation-linked runtime readback is available, but persisting `/switch/observed`
failed. Candidate rule and cleanup have not been attempted, no success was
published, and the original invocation retains ACTIVE application ownership.
The fixture drops that evidence write once, deterministically.

Before E4, E1's `run` could reconcile this journal on a domain retry, but the
installed adapter returned UNCERTAIN; a new invocation could not inherit E2
ownership. E4's installed `run_owned` makes **one** `recover_post_switch` pass
inside the same owning invocation. There is no new public recovery endpoint,
operator resume CLI, lock-breaking API, lease or automatic takeover.

## Evidence and resolution contract

The recovery method verifies exact E2 type, environment/application domain,
normal binding, operation UUID, original request digest and already-held grant.
`Authority.acquire()` only rechecks this existing invocation's exact owner,
generation and head body. It cannot acquire a replacement grant here. Existing
guarded SDK clients recheck E2 immediately before every mutation and enforce the
original deadline after that read. History publication remains `Authority.call`.

Recovery validates retained intent, request/history, stage plans and attempt
hashes; resolves the exact switch-selected content-addressed activation proof;
and uses existing immutable reconciliation for all attempted stages. It then
independently reads **current** switch, candidate and cleanup effects if attempted,
requires exact APPLIED identity and agreement with the journal, and observes the
listener/rule, selected revision, counts, cohort, deployment and closed settings.
It does not read back superseded drain/attach states as though they were current.

| Evidence | Decision |
| --- | --- |
| No plan/attempt for candidate or cleanup, authoritative absent pre-call effect | Existing controller may issue that new stage after all fresh guards |
| Attempt with exact verified APPLIED effect | Reuse it; never resend; current post-switch effect/readback must also agree |
| Attempt with authoritative ABSENT | Retain definite non-application; no resend/compensation; partial deployment remains UNCERTAIN |
| Missing attribution, timeout, UNKNOWN, malformed/contradictory evidence | UNCERTAIN; no later environment mutation |
| Changed generation/owner, active peer, missing/corrupt/unavailable head | Block; no mutation or ownership borrowing |
| Expired original deadline, changed qualification/eligibility/binding, failed prod approval, replaced cohort | Block; no deadline extension or authorization downgrade |

An AWS timeout proves neither failure nor success. The installed runtime requires
its protected call-linked `/ack` plus authoritative AWS verification; absent ACK
after an attempt remains UNKNOWN even if routing happens to match. E4 does not
invent attribution for a lost AWS response. Controlled runtime doubles can prove
an applied effect independently; that is not live AWS attribution evidence.

Before each *new* candidate-rule or cleanup mutation, fresh authorization, exact
task registration readback, listener/rule, service revision/count/cohort/deployment
and runtime settings are checked **after** plan/attempt persistence. E2 guards
follow at the SDK call. Schedule readback now also requires ENABLED, the fixed
expression/target and exact generation InputTransformer. There is still no
cross-service AWS transaction or continuous readiness guarantee. The retained
E3 proof authorizes only the unchanged activated cohort; no second switch occurs.

Success requires the existing receipt validation of all seven effects and final
identity. Runtime ACKs, a retry returning normally and local optimistic flags are
insufficient. Readbacks and normalized snapshots are retained under immutable
`post-switch-readbacks/<sha256>` and `post-switch-snapshots/<sha256>`; damaged
observations are not overwritten. A blocked pass emits `POST_SWITCH_RECOVERY_BLOCKED`
with a checkpoint under `outcomes/<sha256>` when evidence storage is available.
Failure to store diagnostics never invents success or claims durable diagnostics.
Read-only effect reconciliation has the existing 30-second per-stage budgets;
future mutations retain the immutable original 1800-second deadline.

Repeated calls with a valid grant reuse exact effects and do not resend attempted
stages. E2 terminal retries return historical status without reacquisition or
index publication. Historical success is not a statement of current eligibility.
A persistent failure gets one pass per `run_owned` invocation, not an internal
retry loop. An ended/crashed invocation has no supported resume path.

## Operator runbook

Repository acceptance is offline:

```text
python -I -B scripts/tests/post_switch/run.py
python -I -B scripts/tests/final_acceptance/gate.py --report-dir <outside-repository-directory>
```

The following AWS **read-only diagnostics** are for future separately authorized
operation after genuine installation. They were not executed for E4. GetObject
writes local audit files; use an existing authenticated administrator diagnostic
session because public result readers cannot read protected internal evidence.
Do not put credentials or secret values in audit records.

1. Obtain the exact operation UUID from the protected request/result and the
   bucket, environment, account and region from installed configuration. Verify
   account/region/environment together. Freeze new mutating requests operationally;
   preserve ACTIVE E2 ownership to arbitrate other controllers. Never reset a head.
2. Collect current storage versions/bytes, not caller-provided evidence. Example
   Bash recipe with values filled from that configuration (no resource discovery
   by guessed names):

```bash
E4_ENV=dev
E4_OPERATION='<exact-protected-operation-uuid>'
E4_BUCKET='<installed-environment-evidence-bucket>'
E4_REGION='<installed-region>'
E4_AUDIT='<absolute-private-audit-directory>'
mkdir -p "$E4_AUDIT"
aws --region "$E4_REGION" sts get-caller-identity > "$E4_AUDIT/identity.json"
aws --region "$E4_REGION" s3api get-object --bucket "$E4_BUCKET" \
  --key "arbitration/$E4_ENV/application.json" "$E4_AUDIT/head.json" > "$E4_AUDIT/head-version.json"
for E4_KEY in intent switch/plan switch/attempt switch/ack; do
  E4_FILE=${E4_KEY//\//-}
  aws --region "$E4_REGION" s3api get-object --bucket "$E4_BUCKET" \
    --key "delivery/$E4_ENV/$E4_OPERATION/$E4_KEY" "$E4_AUDIT/$E4_FILE.json" \
    > "$E4_AUDIT/$E4_FILE-version.json"
done
E4_PROOF=$(jq -er .activation_sha256 "$E4_AUDIT/switch-plan.json")
aws --region "$E4_REGION" s3api get-object --bucket "$E4_BUCKET" \
  --key "delivery/$E4_ENV/$E4_OPERATION/activations/$E4_PROOF" \
  "$E4_AUDIT/activation.json" > "$E4_AUDIT/activation-version.json"
```

3. Using those exact keys, collect all seven stages' plan/attempt/observed/reconciled
   and ACK records, registration, startup, exact persisted E3 hash, outcomes,
   post-switch readbacks/snapshots and any success/public receipt. Record missing
   keys and error codes; a permission/transport error is not authoritative absence.
   Resolve identity from `intent.intent.release` (release/source/digest/manifest
   version/hash), `intent.intent.qualification_sha256`, registration and proof.
   Preserve canonical bytes, S3 VersionIds, ETags and hashes; do not edit evidence.
4. Read runtime reality using exact ARNs from that intent and installed cleanup
   configuration. These are AWS reads, not recovery actions:

```bash
E4_LISTENER=$(jq -er .intent.routing.listener_arn "$E4_AUDIT/intent.json")
E4_RULE=$(jq -er .intent.routing.candidate_rule_arn "$E4_AUDIT/intent.json")
E4_CLUSTER=$(jq -er .intent.service.cluster "$E4_AUDIT/intent.json")
E4_SERVICE=$(jq -er .intent.service.service "$E4_AUDIT/intent.json")
E4_TASK_REVISION=$(jq -er .registration.task_definition_arn "$E4_AUDIT/activation.json")
aws --region "$E4_REGION" elbv2 describe-listeners --listener-arns "$E4_LISTENER" > "$E4_AUDIT/listener.json"
aws --region "$E4_REGION" elbv2 describe-rules --rule-arns "$E4_RULE" > "$E4_AUDIT/rule.json"
aws --region "$E4_REGION" ecs describe-services --cluster "$E4_CLUSTER" --services "$E4_SERVICE" > "$E4_AUDIT/service.json"
aws --region "$E4_REGION" ecs describe-task-definition --task-definition "$E4_TASK_REVISION" --include TAGS > "$E4_AUDIT/task-definition.json"
aws --region "$E4_REGION" ecs list-tasks --cluster "$E4_CLUSTER" --service-name "$E4_SERVICE" > "$E4_AUDIT/tasks.json"
```

   Also DescribeTasks for every listed task (respect API batch limits), target
   health for the exact candidate target, and DescribeRule/ListTargetsByRule for
   the fixed installed EventBridge rule. Verify exact ENI/target/task/cohort,
   revision/digest, deployment/count/settings and schedule generation transformer;
   do not reduce this to a healthy count. Compare current eligibility/prod approval
   through protected fact reads; journal eligibility alone is historical.
5. **Mutating continuation:** the installed adapter automatically performs its
   one bounded pass before publishing a result, while the original worker still
   owns the grant. This is the only installed E4 action. It may finish unattempted
   rule/schedule stages and receipt/publication; it never writes the listener again.
   Do not start another worker or call Python manually to impersonate that owner.
6. **Stop** on any blocked checkpoint, lost attribution, contradiction, newer
   owner/generation, changed cohort, authorization failure or elapsed deadline.
   Retain the hold and diagnostics. If the exact worker has ended, a separately
   authenticated administrator must establish its termination (including in-flight
   SDK/provider calls), reconcile all immutable attempts/effects and current AWS
   reality, and explicitly authorize administrative repair/release under E2.
   No repository command implements that prerequisite; elapsed time is insufficient.
7. **Restoration boundary:** E4 performs none. After independently satisfying the
   E2 administrative prerequisite, existing protected emergency recovery can be
   considered only if the inactive color has its actual prior SUCCESS history,
   exact revision still selected, current qualification/eligibility, independent
   prod approval and fresh healthy topology. Its closed `{}` request derives
   content from protected history. In the selected partial state, listener and
   candidate rule both still point at the new color: existing emergency recovery
   rejects that inactive mapping. Releasing E2 alone does not make restoration
   available; E4 supplies no topology-repair/compensation command. Otherwise stop;
   arbitrary release selection, direct listener rewrites and blind reversal of
   unknown effects are forbidden.
8. **Verify completion:** all seven exact APPLIED effects; unchanged activated
   revision/cohort/digest; listener candidate target and candidate rule former
   target; enabled fixed generation-bound schedule; immutable success receipt;
   matching protected color history/dev activation/public SUCCESS; exact E2
   terminal followed by RELEASED head. A receipt alone does not prove later
   publication or current runtime. Preserve the head/terminal versions, request,
   full proof/journals/readbacks and administrator decisions for audit. A later
   generation invalidates old cleanup events through unchanged E2 admission.

## Limits and acceptance

Partial PutRule/PutTargets failures, attributed definite non-application after an
attempt, absent AWS ACKs, contradictory topology, later history/dev/public
publication failures, expiry, revoked content, schema reversal and orphan-owner
administration remain unresolved. No forced terminal success or compensation is
added. Independent restoration is the existing E1 contract, not proven rollback.

Focused deterministic tests exercise the actual E1 controller and E2 grants,
including installed adapter composition, transient evidence-write failure,
lost response with/without attribution, definite failure, contradictions,
repetition, crashes, generations/contenders, separate environments, stale cleanup,
missing/corrupt evidence and production rejection. Full existing E1 acceptance and
E2 regression evidence must also pass; counts/results are recorded in
[validation](validation.md#e4-bounded-post-switch-recovery).
Packages are refreshed from source without new IAM, trust, PassRole or activation.
Live S3 CAS/SDK attribution, ECS/ALB/EventBridge behavior, installation and Linux
E3 remain separate deployment evidence. E4 is partially resolved at this boundary.
