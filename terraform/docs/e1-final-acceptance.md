# E1 WP7 — legacy retirement and final repository acceptance

Starting integrated main: `a7a3c85d4d50678391a792a4e740e5f657b98d12`.
Local branch: `codex/e1-wp7-final-acceptance`. Main is unchanged.
The approved [specification](../../specs/iam-hardening/spec.md) and
[plan](../../specs/iam-hardening/plan.md) remain immutable. WP1–WP6 contracts are
preserved; WP7 retires overlap and accepts the resulting repository model.

## Retirement and replacement

The [retirement catalog](../../ci/authority/retirement.json) accounts for every
frozen legacy IaC source, seven composite actions and two imperative wrappers.
All 137 old Terraform/Terragrunt/provider-lock source paths are removed from their
operational locations. Their exact bytes remain `.txt` data under
[retired source](../../ci/authority/retired), checked against immutable digests.
They cannot be initialized as roots, selected as modules or invoked as actions.
Only explicit reviewed generators select ordinary declarations; generated TARGET
Terraform, runtime package hashes and protected installation contracts are unchanged.

| Retired authority | Accepted replacement / stopping control |
| --- | --- |
| Combined app-CD, old deploy/promote/rollback and TG CI/CD roles, attached policies and default environment subjects | Eleven security-root request reservations; exact aud/repo/environment/pinned reusable-workflow trust; no legacy external trust remains |
| Broad IAM/OIDC/KMS/secret/storage administration and caller control-state/code writes | Separately authenticated human administrator, neutral protected root and dependency policies; lifecycle cannot change them |
| Old cross-env artifact writes, prod high-risk dev-approval and TG_CD/app-CD credential fallbacks | Disjoint environment gateways/state/result namespaces and neutral qualification; missing authority fails closed |
| Generic delivery PassRole and AssumeRole acquisition | Public callers have neither; protected service-specific executors pass only exact fixed environment roles to the intended service |
| Direct ECS registration/service/ALB workflow/action/local deployment | Exact gateway → protected controller; qualification/runtime/role authorization before startup and accepted E3 before normal switch |
| Legacy manifest bypass / no-dev-record promotion | Current historical eligibility and protected dev activation plus independently held prod approval; same normal authorization/readiness |
| Legacy emergency/cleanup/NAT mutation roles/functions/events | Separate bounded WP4 recovery executors, closed content/membership/event inputs; no publication, registrar or generic EC2 authority |
| Local bootstrap/deploy wrapper and standalone blue/green main | Permanently rejected before AWS; future reconstruction uses explicit admin install/secret bootstrap and protected lifecycle |

The accepted E3 library, renderer/response-boundary helpers, SQL user data and
protected runtime dependencies remain. A helper's presence alone grants no AWS
authority. Historical WP1 bypass regressions expand retired bytes only into
disposable test fixtures; their positive witnesses characterize pre-E1 behavior,
not current TARGET permissions. Existing approved spec/plan source links identify
historical logical paths; the retirement catalog resolves them to inert source data.

## Final deterministic gate

Run with preinstalled Python, Git and Terraform, with reports outside the checkout:

```text
python -I -B scripts/tests/final_acceptance/gate.py --report-dir <outside-repo-directory>
```

The gate runs all fourteen accepted WP1–WP6 entry points plus focused WP7 composed
relationships and restoration mutations. Each test process uses the existing
hermetic credential/process/socket guard. Static checks evaluate actual generated
Terraform in disposable provider-free roots, without init/backend/provider/AWS.
It checks all generated wiring, source inventory, deterministic extracted packages,
Python/JSON/generated-YAML parsing, current KDD links and immutable approved
contracts, check-only Terraform format and `git diff --check`. Static CI invokes it.

The evidence manifest records exact revision/tree/dirty status, content hashes,
actual test IDs/counts/log hashes and AC1–AC16 evidence families. Missing, failed
or skipped evidence cannot pass. Existing suite semantics and positive controls
remain; WP7 adds requester → gateway → controller relationships, exact PassRole,
cross-environment denial and mutations restoring old roots/actions/wrappers/grants.
Removing an essential gateway grant cannot satisfy its positive control.

| Acceptance family | Required evidence |
| --- | --- |
| AC1, AC7 / WP1–WP2–WP5 | Closed generated ownership/policy/trust/configuration; ordinary control mutations denied; legitimate admin/lifecycle represented |
| AC2, AC3 / WP6 | Exact token-to-role matrix, own exact versioned gateway, no legacy/default-sub or dev→prod authority |
| AC4–AC6, AC14 / WP3–WP4 | Genuine synthetic qualifying positives; missing/rewritten evidence, runtime injection/role swap and direct activation rejected before startup |
| AC8–AC9 / WP4 | Normal E3, current historical rollback eligibility, existing-content emergency and bounded cleanup/NAT positives and denials |
| AC10 / WP7 | Complete retired inventory; legacy/fallback/alternate invocation restoration detected |
| AC11–AC13 / all | Positive legitimate responsibility traces, fail-closed negative cases, actual-source mutations and no deny-all acceptance |
| AC15–AC16 / all | Preserved app/secret/runtime ownership contracts; hermetic exact-content provider-free evidence |

Validation results and the bounded implementation self-check are recorded below
after actual execution. Repository-level acceptance never establishes live security.

## Installation and live limits

Canonical approvals/installations/runtime/environment-binding maps remain empty:
**0/11 external identities, 0/16 WP4D and 0/8 WP5 compute bindings are active.**
No S3 VersionId, image qualification, installation, resource membership, environment
readback, approval or deployment success is fabricated. Synthetic test projections
are explicitly separate from live evidence. Old sessions/state migration are not
applicable to this undeployed greenfield project.

Future separately authorized deployment still needs genuine administrator access,
protected package/image/version installation/readbacks, membership/bindings, AWS
provider schemas and live IAM behavior, OIDC customization and GitHub G1–G9 controls,
plus live Fargate/ALB/DB/KMS and delivery/rollback verification. These are operational
prerequisites, not hypothetical blockers to repository-model acceptance.

## Validation record

The stabilized-source final gate returned `E1_REPOSITORY_ACCEPTANCE_PASS`:
**959 accepted WP1–WP6 tests + 24 WP7 tests = 983**, with zero failures, errors or
skips. All **AC1–AC16 passed**. All nine static checks passed: security/workflow
wiring, KDD/approved contracts, extracted packages, WP4D/WP5/WP6 provider-free
Terraform, Terraform formatting and Git whitespace. The inventory is fresh at
371 sources; the final generated authority inventory contains 87 protected
declarations. Parsing passed for 132 Python files, 46 JSON files and 21 generated
YAML files. The external `acceptance.json` records test IDs, log/source hashes,
the evaluated Git state and the complete final authority inventory.

Additional checks passed: all 27 workflow YAML files through native PyYAML 6.0.3,
32 Bash syntax checks, Terragrunt HCL format check and 40 .NET tests. The .NET run
used an environment-only EventLog override after the sandbox denied two tests'
Windows EventLog writes; no app code was changed.

Native Ubuntu provides Python and PyYAML but no `jq`; the full
fresh E3 shell suite is unavailable without an unauthorized dependency installation.
Native process-group supervision passed all five cases from disposable exact source
copies on the Linux filesystem. The first mounted-filesystem run failed the nested
fixture's grandchild-marker assertion; the native filesystem repeat passed. No E3
architecture change was made and full Linux E3 success is not claimed.

Non-blocking debt remains: WP4A-N2 historical documentation encoding, incomplete
tool/provider reproducibility, existing Git Bash selector cleanup limitation,
optional E2/E4 and SQL/retention/observability backlog. None grants legacy authority.

Auxiliary scans are not reported as green: preinstalled TFLint emitted 24 warnings,
and provider-free, no-module-download tfsec exited 1 with 46 findings (32 high,
14 medium). Their encryption/versioning/logging/image-scanning rules concern
unchanged WP1–WP6 source; all affected files were compared to integrated main and
are identical. Some diagnostics fail to associate separate JSON encryption and
versioning resources. Others request CMKs, logging or image scanning beyond the
accepted current contract. No suppressions or unrelated infrastructure changes
were introduced. These are existing scanner/maintenance debt, not new authority
grants or evidence of a WP7 retirement bypass.

One bounded implementation self-check compared the retirement catalog, live IaC
universe, workflow credential/invocation paths and composed positive/negative
authority tests with approved WP7 and AC1–AC16. It found no concrete remaining
TARGET bypass. The earlier execution exposed source-inventory timing drift while
new gate files were being added and a unittest log parser that missed multiline
docstrings. Hermetic Git also needed explicit platform line-ending normalization
and exact-repository trust after disabling inherited system/global settings;
the corrected check passed. A transient Terraform console decoding failure did
not reproduce in two focused repeats, including the sanitized gate environment.
These harness issues were addressed before the final stabilized-source run. No
independent or recursive reviewer was invoked. The complete corrected gate passed;
no material repository-level security or architectural blocker remains.

**E1_READY_FOR_FINAL_INTEGRATION** — repository acceptance only, without AWS
deployment, operational activation or integration into main.
