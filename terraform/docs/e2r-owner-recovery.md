# E2-R — interrupted-owner diagnosis and recovery boundary

CURRENT repository increment: safe diagnostics and deterministic failure evidence.
Administrative release remains **BLOCKED**. AWS has never been deployed. This
extends [E2](e2-environment-mutation.md) and preserves [E4](e4-post-switch-recovery.md),
E1 authorization, immutable effects and existing-content restoration limits.

## Reproduced failure

The [focused suite](../../scripts/tests/owner_recovery/test_owner_recovery.py)
acquires a genuine E2 grant, issues a guarded mutation, then interrupts the body
before terminal/release. ACTIVE survives. A second invocation of the same logical
operation and a different legitimate operation both receive UNCERTAIN without
entering their controllers. Interrupted pre-call ownership also remains ACTIVE.
An E1 delivery with ambiguous start and an E4 partial listener switch likewise
cannot pass their journals/grants to a replacement invocation.

Two deliberately unsafe, **in-memory-only** experiments demonstrate why an
administrative head CAS is insufficient:

- Pause the old worker after its last `_check`, before sending. Change the head
  to RELEASED and acquire a new generation. The new worker sends; the old worker
  resumes and sends afterward, despite the new generation. Even `touched=False`
  and no issued call at the inspection instant do not prove safe termination.
- Pause an already issued remote operation before completion. Change ownership
  and complete a new owner's operation. The old effect completes afterward.

The experiments are counterexamples, not supported recovery paths. Event barriers
control ordering; wait bounds only prevent hung tests. No elapsed time authorizes
release. If the old worker pauses **before** its ownership check, that check
rejects the changed generation on resume. This narrower guarantee cannot protect
the two windows above. Future old calls, schedule writes, releases and saved-plan
apply reject stale ownership; queued cleanup rejects superseded schedule evidence.

## Exact blocking guarantee

Safe administrative recovery requires both:

1. Authentic, exact execution identity and verified termination/neutralization of
   every executor that can still issue the old operation's mutations, including
   SDK retries and Terraform/provider descendants.
2. Authoritative settlement of every issued or possibly issued effect, with no
   old remote mutation still able to complete after a new generation is admitted.

The head records a Python invocation UUID, operation, request digest, binding,
environment/domain and generation. It does not bind that UUID to an authenticated
Lambda/CodeBuild execution identity, process tree, credential session or a termination
receipt. The installed handlers do not persist such evidence. WP5's synchronous
subprocess timeout is not proof of provider/remote quiescence. No current adapter
verifies either guarantee for an interrupted peer. S3 If-Match fences the head;
ECS/ALB/EventBridge and provider mutation requests do not consume E2 generations.
Repeated readbacks that happen to match cannot rule out delayed old effects.

An expired deadline, missing heartbeat/PID, GitHub cancellation, successful head
CAS, observed SDK return, operator assertion or SUCCESS terminal alone cannot
substitute for these guarantees. A terminal retained before a failed release is
historical status; a retry may return it while the head remains ACTIVE and blocks
new operations. The suite tests this distinction. No terminal replay repair is
introduced.

These prerequisites would need an approved, bounded execution-lifecycle and
remote-effect verification mechanism. Its design, real executor mapping and live
validation remain unresolved. E2-R does not choose a new privileged service,
credential-revocation scheme or downstream mutation broker to fill that gap.

## Implemented diagnostic

[`inspect_domain`](../../scripts/owner_recovery.py) accepts an existing diagnostic
S3 client plus the exact installed bucket/environment/domain. It performs one
GetObject through E2's canonical head/header validator. It creates no client,
credentials, process or SDK mutation. The returned `E2R_DIAGNOSTIC_V1` report has:

- Exact bucket/key/environment/domain and validated head, including owner,
  operation, binding, request digest, generation and schedule.
- ETag, VersionId and SHA-256 of those canonical head bytes from the same read.
- `E2R_BLOCKED_QUIESCENCE_UNPROVED` for ACTIVE, or `E2R_RELEASED_OBSERVED` for a
  released snapshot. A missing/corrupt/contradictory/unavailable observation emits
  `E2R_BLOCKED_HEAD_UNPROVED` with no head bytes or raw SDK error.
- Always `recovery=UNAVAILABLE`, `termination=UNPROVED`, `effects=UNRECONCILED`.

This is a library diagnostic, **not an installed command/controller**. It neither
authenticates an administrator nor establishes installation authenticity. Its
caller must use an independently authenticated protected diagnostic session and
derive configuration from genuine installation. Save the report to a private
administrator audit location if needed; the helper itself writes nothing. A saved
report is a dated observation, not durable recovery authorization or current
ownership. It never reads secrets, state, arbitrary operation journals or runtime
resources. Those remain separate authorized diagnostics.

There is **no implemented administrative recovery command**. No input can supply
an admin/termination/force flag, authorize a CAS, delete a head or manufacture a
terminal. Repeated and simultaneous diagnostic calls leave ownership unchanged.
No new IAM, trust, PassRole, installed package, binding digest, Terraform generator
or activation change is needed. Existing externally authenticated security
administration remains the [authority boundary](secrets-strategy.md#current-contract--protected-administration-and-installation).
Ordinary delivery credentials receive no new path. Future admin mutation would
require separate verified authority, explicit authorization, exact current
head/version/request, reconciled effects, an atomic new generation with replay
protection and durable audit; no part of this list is an implemented release API.

## Operator runbook

The following steps are for future separately authorized diagnostics after genuine
installation. No AWS command was executed for this increment.

1. Identify the blocked environment and conflict domain from the installed
   configuration and protected request/result. Application spans delivery,
   recovery, cleanup and conflicting lifecycle layers; shared/secrets are separate.
   Freeze new mutating requests operationally and preserve ACTIVE arbitration.
2. In an existing authenticated protected diagnostic/admin session, use the
   read-only helper above or the E4 runbook's exact-key head collection. Record
   canonical bytes, VersionId, ETag, hash, owner, operation, generation, binding,
   request hash and schedule. Do not infer absence from access/transport failures.
3. Collect the exact operation's immutable intent, request, plans, attempts, ACKs,
   observed/reconciled effects, activation/E3, outcomes, terminals, receipts,
   history/dev/public publications and WP5 saved-plan/result evidence as applicable.
   The [E4 collection recipe](e4-post-switch-recovery.md#operator-runbook) covers
   normal delivery. Retain missing/error distinctions, versions and canonical
   hashes. Never overwrite evidence or blindly resend an attempted mutation.
4. Establish the exact executor's authenticated lifecycle, descendants, retries
   and external requests. **Stop here under CURRENT CONTRACT:** the repository
   cannot map the owner UUID to verifiable termination/neutralization and cannot
   rule out pending old effects. A cancellation/timeout/claimed process exit is
   insufficient. Escalate the missing guarantee to the security administrator;
   do not edit/reset/delete the head or impersonate the owner.
5. Separately inspect authoritative runtime reality using exact installed/intent
   identities: both ECS service revisions/counts/deployments/settings, registered
   task definition/digest, all tasks/cohort/ENIs and target health, listener and
   candidate rule, enabled cleanup rule/target/generation transformer, protected
   history/activation/publication and current eligibility/prod approval. For WP5,
   also reconcile exact saved-plan/state and changed resources under its approved
   scope. These reads aid diagnosis; matching current state does not settle a
   pending or unattributed request. Preserve UNCERTAIN/UNKNOWN where attribution
   or settlement remains unproved.
6. Recovery authority and deployment consistency are distinct. No step in this
   runbook authorizes release or rewrites ECS/ALB/schedules/history. There is no
   resulting recovery generation to verify. Re-read the same exact head to check
   for concurrent changes; a changed generation invalidates the earlier snapshot.
   Only existing same-invocation E4 continuation or a proven ordinary E2 terminal
   and release can currently complete ownership. Genuine future administrative
   recovery must verify its immutable audit and resulting environment/domain/new
   generation by exact readback before admitting later operations.
7. After independently supported authority recovery becomes available, any new
   operation must still meet E1 exact release/manifest/current eligibility,
   readiness, independent prod approval, immutable no-resend and cleanup fencing.
   The partial E4 topology can still block existing-content emergency recovery;
   releasing arbitration would not repair it. General compensation is unresolved.

Stop on any unknown effect, active/paused executor, unverified termination,
contradictory identity/readback, stale version/generation, storage/authentication
failure or cross-environment evidence. Availability remains deliberately blocked.
Live installation, authenticated execution identity/termination, credential and
SDK/provider retry behavior, remote settlement/attribution, S3 CAS/IAM and actual
ECS/ALB/EventBridge observations require separately authorized AWS evidence.

## Acceptance scope

Run `python -I -B scripts/tests/owner_recovery/run.py` and the existing full gate
in [validation](validation.md#e2-r-interrupted-owner-diagnostics). The new suite
is independently required by AC16; existing 983 E1/WP, 41 E2 and 28 E4 tests and
40 E13 checks retain their original meanings/counts.

The suite covers interrupted/live/paused owners, later admission rejection,
before/after-check windows, unknown in-flight effects, expired deadlines, stale
release/apply/schedule and delayed cleanup, actual E1/E4 journals, terminal/release
ambiguity, corrupt/missing/contradictory evidence, repeated/competing diagnostics,
unsupported administrative assertions, environment/domain isolation and safe new
operations after ordinary proven release. Positive **administrative** recovery,
competing recovery CAS and admin-authentication enforcement are unavailable and
are not represented by a synthetic success. The two unsafe experiments intentionally
allow old simulated effects to prove the limitation; all supported negative paths
issue no protected mutation.
