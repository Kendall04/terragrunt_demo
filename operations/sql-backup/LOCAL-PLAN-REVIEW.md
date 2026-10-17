# Local review candidate: E16 init/plan only

Status: LOCAL SOURCE EDITS ONLY. No rejected operation has been retried. No
Terraform/AWS/runtime command, remote-state read, denied diagnostic read, Norton
change, credential handoff or apply occurred in this local review task.

The outer wrapper already used DEVNULL. The remaining raw stderr capture was in
the canonical `scripts/practical_dev.py` Process.run. The candidate adds an
explicit `--discard-diagnostics` mode there, using stdout=PIPE for internal
structured results and stderr=DEVNULL, and retaining empty stderr on failure.
It emits only stage/plan ID/layer/phase plus address/type/action metadata. Plan
values, state, preview text and apply/SQL-loss confirmation strings are omitted.

The mode accepts native init/bootstrap-network-plan/up-plan only and rejects
apply, teardown and alternative transports. The reviewed wrapper is narrower:
its fixed sequence is `scripts/original_dev.py dev init`, then
`scripts/original_dev.py dev bootstrap-network-plan`, both with that flag. It is
import-safe and defaults to a local review description with no subprocess.
Execution requires an explicit human-review flag and a digest matching the
wrapper, canonical entry and E16 implementation. Those checks bind bytes; they
do not override the previous tool rejection or confer execution authority.

Existing E16 binary/preview/review plan artifacts remain private for actual plan
review. These are normal Terraform plan artifacts, potentially sensitive; they
are not raw diagnostic logs. This wrapper never opens/copies them or prints
their contents. No stdout/stderr log files are written by the wrapper.

## Human review step, before any execution

1. Inspect `wrapper.diff`, `e16-source.diff` and the two source files, including
   both subprocess boundaries. Verify DEVNULL is used throughout this mode and
   the wrapper's only live actions are init/bootstrap-network-plan.
2. Inspect `local-review-manifest.json` and compare its source hashes with the
   actual files. Review digest:
   `0b84d5e8dde0939400e08b385a4a9e396bbff363df2e1d536e27a086897ebe16`.
3. Explicitly release this exact revised init/plan operation for tool review.
   Suggested scope: "I reviewed these source bytes. Permit only the existing
   E16 init/bootstrap-network-plan flow, with internal state consumption,
   discarded stderr and metadata-only output; no raw diagnostic inspection,
   apply, deletion, Norton/TLS change or credential transfer."
4. Only after that human review has resolved the prior tool rejection may a new
   invocation be proposed. The not-yet-run command shape is:

   `python -I -B revalidate_ec2_plan_only.py --execute-after-human-review
   --review-sha256 <exact-reviewed-digest> --evidence-root <new-external-directory>`

   The canonical E16 source must be clean at a reviewed commit. Do not execute
   that command in this local-review task, reset retry allowances, use another
   route, or treat these flags as permission to bypass a further rejection.

## New historical UNKNOWN disposition

The owner said "Sigue con ecs también" after being told that the old NAT
uncertainty disposition was pending; the new delegation explicitly instructed
recording that disposition. A fresh local owner-decision record was therefore
written for operation `05fc796a-03ae-5e11-8d3b-64a61d144d5d`, account
341936017254/us-east-1, preserving `historical_result=UNKNOWN`.

It is bound to the existing local session/configuration and an evidence digest.
The evidence references the already recorded old-target absence; it makes no
new native AWS observation. At future use the unchanged guard still checks the
attempt/plan/original FAILURE hashes and performs a fresh exact-target read.
No E13 journal, ACK, APPLIED/ABSENT/SUCCESS or historical FAILURE was written or
modified. The old final-DOWN authorization was not copied.

This is solely a disposition of the historical risk for the approved current
ECS backup component; it authorizes no deletion or apply. Any fresh execution
configuration must be technically rebound within that same scope after human
review, rather than copying this configuration hash into another session.
E2/identity/state/plan/controller/queue/ASG/ECS and SQL-loss checks remain in force.

The two program-shaped files are local under the existing session:
`historical-SDC-05fc796a-owner-disposition.json` and
`historical-SDC-05fc796a-native-evidence.json`. The review bundle includes a new
provenance record with `ApplyAuthorizedByThisDisposition=false` and
`DeletionAuthorizedByThisDisposition=false`. No runtime window has started.

## Deliverables

Review bundle:
`C:\CodexDrop\temp\terragrunt-demo-sql-ec2-local-review-20261017`.

It contains wrapper.diff, e16-source.diff, local-review-manifest.json, the new
UNKNOWN disposition/provenance and its non-sensitive prior-evidence reference.
Tests use process mocks/hermetic fixtures only, never real Terraform or AWS.

## Fixed failure-step metadata follow-up — 2026-10-17

The corrected route was admitted by normal tool review and then failed technically;
its generic failure code did not identify the failed step. The owner authorized
a minimal metadata correction and the same bounded init/network-plan retry.
The canonical entry now emits only an allowlisted step label and integer exit
code on failure in discard-diagnostics mode. The wrapper accepts only that
shape and maps all other failures to fixed labels; stderr remains DEVNULL.
No error text, state or preview values are inspected or displayed. Default
E16 behavior, identity/state/plan/teardown guards and the two actions are unchanged.

Local verification uses hermetic E16 fixtures and seven wrapper mocks, including
unexpected diagnostic text and untrusted metadata. The new review digest is
`e649aed37ae4739a8162d93832c9b2b3a7d3e107751fb5da58fb97f320956062`. This source change authorizes no apply or runtime creation.
A fresh normal-review invocation must bind this clean commit; another review
rejection remains a stop condition. No raw diagnostic fallback is permitted.

The admitted retry result is recorded in [validation](../../terraform/docs/validation.md#fixed-step-result-after-admitted-retry---2026-10-17): init 0, global state pull 1, no plan. Evidence is execution-result-metadata.json in the fresh step-plan directory. No further live attempt was made.
