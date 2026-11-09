# Initial installation of the trusted promotion evaluator

This PR installs the approval producer on the default branch. It is deliberately
separate from enabling application delivery or requiring its check in a ruleset.

Source: reviewed `develop@37aa983b618f8ec17e688c8ff7cf1db32f6bab91`.
Base: `main@d98dec617ebd6b9079d68cc667da9c67902dbfc8`.
The source tree contains later SQL/TLS and executor changes; they are not part of
this installation.

## Installed files and authority

| Files | Purpose |
| --- | --- |
| [api-promotion.yml](../.github/workflows/api-promotion.yml) | Trusted caller for main PR events and completed DEV delivery events. |
| [api-evaluate.yml](../.github/workflows/api-evaluate.yml) | Evaluates with base code, publishes a signed predicate and rereads the published attestation and check locator before success. |
| [cli.py](../scripts/api_delivery/cli.py), [github.py](../scripts/api_delivery/github.py), [model.py](../scripts/api_delivery/model.py) | Existing command orchestration, scoped GitHub transport and application/source/merge contracts. |
| [receipts.py](../scripts/api_delivery/receipts.py), [receipt-policy.json](../scripts/api_delivery/receipt-policy.json) | Discover and authenticate signed deployment and promotion receipts, including exact producer attempts, stable PR association, certificate base and exact-check head. |
| [workflow_contract.py](../scripts/api_delivery/workflow_contract.py) | E1 uses the two evaluator entries from the unchanged reviewed catalog. The shared reader also retains its optional queued-DEV template checks. These templates do not install delivery workflows. |
| [api_promotion tests](../scripts/tests/api_promotion/) | Promotion-only fixtures and regressions; normal and optimized Python run in Repo Hygiene. |

All seven implementation/policy files and both workflows retain the reviewed
Git blob bytes. The shared CLI includes other commands unchanged; their AWS
imports are deferred inside execution. This installation supplies neither those
AWS modules nor a delivery caller/executor, binding, role or environment.
The installed workflows invoke only promotion, receipt-files and finish-promotion.

The caller grants contents/actions/pull-request read, checks/attestations write
and id-token write for GitHub/Sigstore signing. The evaluator has no AWS role,
environment, credential step or secret input. It fetches PR Git objects but never
checks out or executes PR code. Its checkout is the trusted event revision.
Public predicates contain only the closed fields admitted by the receipt reader.

## Adaptations required by main

- Main has no automatic-delivery test/package tree. The promotion fixtures extract
  the reviewed record/PR/run/REST/wire behavior without importing AWS executor
  fixtures. The nine historical PR-target regressions retain their test bodies;
  only fixture imports change. Additional tests cover signer substitution,
  pending evidence, exact attempts, B remaining approved after C and finalization.
- [E1 closed()](../scripts/tests/final_acceptance/contract.py) previously had no
  replacement-path admission. Its new `promotion_workflows()` requires exact
  equality with the two reviewed evaluator templates. It does not exempt the
  deployment templates. Existing retirement, workflow generation, direct AWS,
  compute activation and UNKNOWN/failure checks remain intact.
- The source inventory records only the actual proposed main tree. Repo Hygiene
  adds the isolated evaluator suite, normally and with `python -O`. CI selection
  tests prove both workflows and Python changes select acceptance and hygiene.
  The selector, required-check identities and other CI jobs are unchanged.
- Main's toolchain action catalog adds only the reviewed actions/attest v4.2.2
  commit already used by develop. Its completeness test remains unchanged; AWS
  credential and diagnostic-upload action entries are not imported.

## Application scope proof

Using `scripts.api_delivery.model.application()`, the base, PR head and
a simulated two-parent merge all identify:

```text
242fe5e4022fe0faa856b233f1e5b3a03cff44b3adf23260b604304c6661a88c
```

The local proof records the exact commits, simulated merge parents, tree and
per-file blob comparison outside the repository. No application build-context
file, SQL/TLS runtime file, Terraform declaration or IAM definition is changed.

## Installation order and remaining qualification

1. Review and merge this bootstrap PR using the existing CI Validation and
   CD Safety Validation protections. Do not require API Promotion Validation
   before its producer is present on main. This PR leaves that rule uninstalled.
2. Verify the installed caller/reusable workflow and main signing revision.
   A separately approved governance change must enforce merge-only promotions
   before a successful evaluator qualification. Current main allows merge,
   squash and rebase; the reviewed evaluator intentionally fails closed under
   that policy. Keep the new promotion check optional during this qualification.
3. Qualify real pull_request_target and workflow_run events on the installed
   default-branch code, including published attestation/check readback. Only
   after those checks pass should the separately approved main-only required
   API Promotion Validation rule be installed. Do not weaken the preflight.
4. Keep main as an ancestor of develop before opening a promotion. A bootstrap
   feature branch cannot impersonate develop; later feature-to-main PRs are
   rejected by the evaluator's branch/repository contract.
5. Delivery activation, real DEV receipt production, S3/ECR verification and
   PROD resources/identity remain separate installation work. API_DELIVERY_ENABLED
   stays inhibited and historical CD stays disabled. A changed application with
   no authenticated successful DEV receipt must remain blocked.

Local fixtures establish logic, not live signature issuance or AWS health.
The historical event-identity trial and PR #44 remain evidence of the original
reader; this bootstrap PR still needs its own installed-default-branch run.
