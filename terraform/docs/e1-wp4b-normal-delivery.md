# E1 WP4B - protected normal delivery

This is a provider-free production state machine, pending independent review.
V1 is preserved at `0f1b8327a3a72dbd80a8057105c2b90e9480dfc5`; V2 corrects the
independent review's F1 preparation window, F2 proof retry conflict and F3
unverifiable mutation-effect classification. V2 is preserved at
`31d7467fe1accc6e96d4c236f5dfa370c589f645`. V3 corrects the remaining F3 review
findings: R1 early retry rejection, R2 structurally corrupt stored observations,
and R3 pre-mutation corruption classification. V3 is preserved at
`9854f3a9e4ed46861b64b65b77b19df1cc4730a8`. V4 corrects the remaining structural
retained-operation corruption classification gap. These checkpoints are not integrated.
It consumes the accepted [WP4A contract](e1-wp4a-normal-delivery.md) and the unchanged
[E3 gate](../../scripts/ecs-readiness-gate.sh). It adds no IAM, SDK client, compute,
public endpoint or deployed authority. [E1 plan](../../specs/iam-hardening/plan.md)
sections 5.2, 5.3 and 7 remain the authority for sequencing and ownership.

## Operation and authorization

`Delivery.run(operation_id, request_bytes)` accepts a protected dispatcher-issued
UUID and only `action`, `replicas`, optional `reason`, and either `release_id` for
`deliver` or a historical operation UUID in `history` for `rollback-release`.
There is no environment/color, readiness, AWS argument or task-definition input.
The installed WP4A Authorizer determines dev versus prod. Operation identity is
not an authorization token: the future dispatcher must own its creation and
environment namespace. This slice does not activate request acquisition.

WP4A is called directly at acceptance and again before every new mutation. Its
entire intent must equal the retained intent, including qualification, exact
manifest, current eligibility, artifact, membership/configuration observations,
runtime, replicas and prod prerequisites. Any drift aborts; it is never silently
adopted. The accepted WP4A implementation and model are unchanged.

The fresh listener target identifies exactly one color in the independently
protected membership universe. The WP4A configured candidate must be the other
color; its candidate rule must already point there. A mismatch rejects rather
than rewriting WP4A's color binding. The future protected Facts adapter must
install/resolve that color from controller state, never caller input. The old
service is taken from that same membership observation. Both colors must share
the installed cluster/listener/rule, have distinct services and distinct target
groups, and all selected service settings are closed against WP4A.

## State machine

1. Conditionally create and read back the immutable operation, full WP4A intent,
   request, history reference/hash, initial observation and 1800-second deadline.
2. Register only `intent.task`. Record a stage plan before the mutation. Observe
   the exact operation-linked revision independently of its acknowledgement.
3. Independently describe that revision and run WP4A registration readback.
   Wrong family/revision/image/roles or other execution fields prevent startup.
4. Reobserve routing and candidate settings; drain the inactive service to zero
   and verify no running/pending tasks. Attach the verified revision at zero.
5. Start exactly the authorized replicas. Observe exact service/revision/count,
   full cohort and deployment identity; retain the startup observation.
   Each drain/attach/start plan retains its expected state. After persisting the
   plan, reauthorize through WP4A and freshly observe the inactive candidate.
   Require the same service, routes, revision, counts, cohort, deployment and
   closed settings, excluding only observation time. Drain may stop the old
   inactive revision; attach requires zero tasks/counts; start requires the
   verified new revision at zero. Check the deadline immediately before calling
   the bounded mutation, with no intervening storage write.
6. Run the accepted E3 gate under its existing bounded process supervisor. E3
   owns all per-replica probe, digest, target-health and stability decisions.
7. Reauthorize through WP4A and reobserve service/revision/cohort/deployment and
   listener/candidate targets. Write immutable content-addressed activation
   evidence and a switch plan naming that exact proof;
   reauthorize and reobserve once more immediately before the listener call.
8. Switch only the retained listener to the retained candidate target. Observe
   exact operation attribution and resulting listener/service/cohort identity.
9. Point only the retained candidate rule to the former active target. Verify
   both routes. Request cleanup scheduling for only the former active service
   using an installed fixed schedule/function/delay, then observe the effect.
10. Observe final routing/service/cohort, reauthorize, and conditionally publish
    the success receipt. No acknowledgement alone permits a success receipt.

Candidate startup is not activation. The diagnostic candidate path can carry
non-normal traffic. No claim of literally zero candidate traffic is made.
Readiness does not authorize a future operation or replacement cohort.

## E3 composition

[e3.py](../../scripts/normal_delivery/e3.py) constructs a fixed argument vector
for `bounded-process.py`, Bash and the protected
[evidence wrapper](../../scripts/normal_delivery/e3-evidence.sh). The wrapper
sources the accepted gate, calls its `main`, and only after success emits its
frozen cohort and final observation fingerprint. It does not reproduce readiness
logic. The Python gate requires successful process completion, bounded output,
the exact context hash, exact cohort and a final fingerprint.

The context binds operation, environment, service/cluster, revision, immutable
image, app/probe names, target/listener/rule, former active target, replicas,
deployment identity, cohort and attempt start/deadline. Every pre-switch retry
runs E3 again. Previously stored `ready` evidence is never a substitute.
The same operation cannot replace its retained startup cohort/deployment.

`Process.execute` is an installed protected port, not a request-supplied program
or readiness record. Its production implementation must execute the fixed argv,
enforce the remaining wall-clock budget, bound output and terminate descendants.
WP4D supplies that runtime and packaging. Linux Bash/jq/Python prerequisites and
the accepted process supervision remain necessary; Windows fixture execution
does not establish Linux runtime behavior.

## Retry and ambiguity

Records use environment-prefixed keys, canonical bytes, observed storage versions
and conditional creation (`If-None-Match: *` semantics), following the existing
protected evidence conventions. There is no mutable generic database or current
pointer that grants authority. Namespace/writer protection, deletion protection
and storage-currentness enforcement remain future adapter obligations.

Each stage has `<operation>/<stage>/plan`, `/attempt`, and `/observed`. A mutation
is sent at most once by a single operation runner. The immutable attempt record
contains the exact environment/operation/stage token and SHA-256 of the canonical
stage plan. Both plan and attempt must be durably read back before the runtime
call. Attempt persistence precedes the fresh preparation/switch guards, preserving
F1's no-storage-I/O boundary after the last observation. A crash between attempt
persistence and the call is conservatively possibly attempted. A guard rejection
in the running process is known to precede the call. A plan without an attempt
cannot have invoked the V3 runtime and is terminal without resend. These offline
checkpoints have no deployed journals; V3 does not migrate V1/V2 journals lacking
attempt provenance. Returned API
acknowledgements are ignored. `Runtime.effect` must return APPLIED only from
independent exact operation attribution and resource observation; ABSENT and
UNKNOWN carry no result. Matching names, tags, latest revisions, or matching
resource state without operation attribution are insufficient. In particular,
registration ambiguity must never be resolved by arbitrarily choosing a revision.

Preparation plans include `expected_state`; their fresh post-plan guard rejects
authorization or topology changes during plan-storage I/O. Observation timestamps
may advance without changing that state. This closes the avoidable F1 window,
not the final non-atomic observation-to-mutation race.

Activation proofs live at `<operation>/activations/<sha256>`, where the hash is
of the actual canonical proof bytes. Each proof explicitly binds operation,
environment, immutable intent, verified registration, startup, E3 and pre-switch
observations. The switch plan's `activation_sha256` selects one exact proof;
there is no mutable latest-proof pointer. Loading checks its byte hash and its
agreement with the retained operation, registration, startup cohort/deployment
and persisted exact E3 evidence. A different operation/revision/cohort cannot
substitute. Exact duplicate proofs are idempotent.

If activation evidence persists but switch-plan persistence fails, a retry reruns
E3 and current observations for the same intent/candidate. Fresh timestamped
proofs coexist without overwriting prior evidence. The new switch plan selects
the proof used by that attempt. Once a switch plan exists, reconciliation uses
only its selected proof and never sends a second blind listener mutation.

After loading the immutable operation, retry reconciles attempted stages in
stage order before current authorization/deadline rejection or later mutations.
Stored effects require the same validator as fresh runtime effects: closed schema,
exact environment/operation/stage token, immutable request hash, supported state,
and exact stage result. Registration requires the intended family/account/region
revision ARN; preparation requests derive their revision from validated registration.
Plans must match the operation's intent and stage request, and attempt hashes must
match the plans. Canonical JSON syntax or a non-null object is never sufficient.

Missing, malformed, or UNKNOWN observations require fresh authoritative effect
readback. Read-only reconciliation uses a separate 30-second budget per stage,
including after the operation deadline expires; it never extends the original
1800-second budget for E3 or future mutations. Unavailable provenance, failed
validation, or UNKNOWN remains UNCERTAIN with no later mutation. APPLIED is
retained before authorization/deadline checks for progression. Thus a revoked or
expired operation can return FAILURE while truthfully retaining an APPLIED start.
Validated ABSENT is retained and yields terminal FAILURE, with no automatic resend.
This refines V2's conservative ABSENT outcome while preserving its no-resend policy.

A recovered terminal effect is conditionally written to the fixed immutable
`/reconciled` slot; damaged `/observed` bytes are never overwritten. The reconciled
slot is validated before reuse and takes precedence. If it is itself corrupt or
cannot be persisted exactly, the operation remains UNCERTAIN. Valid existing
APPLIED observations are reusable without another mutation. Receipts, including
completed-success retries, validate all seven effects against their exact stage
plans; arbitrary journal objects cannot enter a successful receipt.

An ambiguous listener call is never repeated. Reconciliation can finish the
remaining candidate-rule/cleanup/receipt steps only when the exact prior switch
effect and retained activation proof are established, authorization remains
current, and the same revision/cohort is observed. Retry never extends the
original mutation/E3 deadline. A completed success retry returns historical evidence without
mutating anything; that historical return does not assert current eligibility.

There is one protected runner per operation. No cross-operation lock, fencing
generation, transaction or general E2 scheduler is claimed. Observed interference
rejects, but the accepted final-observation-to-listener race remains. Delayed
cleanup safety redesign and arbitrary post-switch recovery remain WP4C/E4 work.

## Outcomes and receipt

`E1_DELIVERY_OPERATION_V1` holds the immutable intent and initial state.
`E1_E3_OBSERVATION_V1` carries the context hash, exact cohort and final fingerprint;
the journal also retains the context and transcript hash.
`E1_DELIVERY_RECEIPT_V1` contains SUCCESS, environment, operation/action/history,
the complete WP4A intent, verified registration identity, startup/E3/pre-switch
proof and its `activation_sha256`, final observed state, and all seven
operation-linked mutation observations.
The full intent carries release/source/digest, exact manifest identity,
eligibility/configuration/membership versions and hashes. No secret values enter
these records. Effects and immutable plans expose reconciliation history.

`E1_DELIVERY_OUTCOME_V1` distinguishes FAILURE from UNCERTAIN. Unproven effects
after a mutation attempt remain UNCERTAIN. Effect transport errors, malformed
schemas, wrong correlation or contradictory results cannot establish an effect.
Decoding errors carry the affected journal key; classification consults stage
attempt provenance rather than treating every parse error as uncertainty.
Corruption of initial intent or preparation evidence before the runtime boundary
is FAILURE. Once a stage may have run, its unreadable evidence requires
reconciliation and cannot authorize a repeated call. Failures after a possibly
applied switch remain conservatively UNCERTAIN, except validated ABSENT.

V4 validates the persisted operation's closed structure, retained request/history,
identity, timing fields and embedded intent integrity before comparing it with
the caller's retry request. Invalid protected structure raises the same keyed
journal error as invalid JSON. The existing classifier consults attempt records
under the installed environment and validated operation ID, without accepting
fields from the corrupt object. No attempt means FAILURE; possible prior attempt
means UNCERTAIN. Unavailable attempt evidence remains conservatively UNCERTAIN.
No missing operation fields are reconstructed from caller data, and no effect
lookup or later mutation runs when the operation cannot be safely loaded.
Matching a structurally valid operation against a different retry request remains
a separate request rejection, not a journal-structure error.

Failed outcome persistence does not manufacture runtime uncertainty; a returned
outcome cannot be claimed durably recorded unless its write was verified. Failed
post-call effect persistence remains UNCERTAIN. Storage failures after earlier
runtime side effects retain conservative non-success behavior. Known pre-call
guard rejection remains FAILURE. Failures before switch never generate success.
Switch, rule update, schedule and receipt writes are not transactional. The
listener may already have changed when a later step fails; no automatic rollback
or invented success hides this window.

Dev success can be projected by `dev_prerequisite` into the exact existing WP4A
dev-receipt contract. Only an authenticated protected receipt reader may invoke
that projection as evidence. Prod still independently requires WP4A's matching
prod approval, current eligibility and prod-specific bindings. It uses the same
qualified immutable image; there is no rebuild or retag authority.

History rollback selects only a same-environment protected success receipt and
then follows the complete normal path through current WP4A and E3. Revoked or
unavailable history rejects. It cannot invoke emergency recovery.

## Acceptance and deferred work

Run `python -I -B scripts/tests/delivery/run.py` (98 tests in V4; 90 in V3; 69 in V2) alongside all 665 accepted
WP1-WP4A tests. Fixtures exercise production sequencing with protected runtime,
storage and process doubles; they are not deployed AWS evidence. Ten behavioral
mutants cover authorization, registration readback, candidate identity, E3
failure/context, revalidation, early switching, ambiguous acknowledgement,
prod prerequisites and historical eligibility. Syntax/setup errors are not
counted as detections. Deterministic independent receipts and package compatibility
are checked without modifying the WP2 catalog or accepted WP3 package digests.
Twenty added correction tests include the original routing/revocation startup
counterexamples, stage-specific drift across preparation, advancing-clock proof
retry, proof substitution, and malformed-effect reconciliation for all seven
mutation stages. Four additional behavioral mutants remove preparation checks,
remove fresh preparation authorization, restore a single activation-proof slot,
or misclassify unproven effects as FAILURE. Unchanged controls must pass. The
original E3 identity mutant is detected when invalid evidence is admitted even
though V2's independent activation-proof check also prevents switching.

V3 adds 21 tests (755 total with WP1-WP4A), including three focused behavioral
mutants for early authorization before reconciliation, trusting non-null observed
objects, and universal decode-error uncertainty. They use passing unchanged
controls and reject behavioral assertion failures, not syntax/import/setup errors.
The prior post-call storage test now permits validated independent APPLIED recovery
through `/reconciled`; the prior ABSENT switch test expects terminal FAILURE while
still asserting exactly one switch attempt. No automatic resend is introduced.

V4 adds eight tests (763 total with WP1-WP4A): pre-attempt structural corruption,
unresolved start and switch corruption, missing history, nested intent corruption,
invalid JSON on both sides of the attempt boundary, separate retry mismatch
classification, and one behavioral mutant that restores definite FAILURE for
structurally corrupt attempted operations. The unchanged control passes; the
mutant must fail a behavioral assertion. All 17 earlier mutants remain in place.

WP4A-N1 is closed by [model_consistency.py](../../scripts/normal_delivery/model_consistency.py):
required, forbidden and return-only classifications must be coherent with the
canonical task, with positional ownership and documented default exceptions.
The representative `image`-as-forbidden contradiction fails acceptance and WP4B
startup. WP4A-N2 remains recorded: its untouched document has one invalid UTF-8
byte in the V2 heading. No unrelated rewrite is included.

WP4C emergency/cleanup/NAT recovery, WP4D IAM/packaging/selective materialization,
WP5 lifecycle, WP6 request activation and WP7 retirement remain deferred. Existing
live/platform limitations in [validation](validation.md) are unchanged. WP4 is
not complete. No AWS, credentials, provider initialization, state operation,
deployment, remote publication or integration is part of this checkpoint.
