# E1 WP6 — protected GitHub/OIDC request integration

WP7 milestone disposition: the stage narrative below records its accepted package.
Legacy overlap is now retired; see [final E1 repository contract](e1-final-acceptance.md).
Installation/governance/live evidence remains unverified and compute stays inactive.

Starting revision: `d5d1ecc2e803ebee0226ae17d5f2f1db34b27113`.
Implementation candidate; not integrated, deployed or operationally installed.
The approved [E1 specification](../../specs/iam-hardening/spec.md) and
[plan](../../specs/iam-hardening/plan.md#41-oidc-acquisition) remain authoritative.

## Closed responsibilities

The security root still owns all eleven IAM reservations. The separately held
human administrator has no GitHub role or workflow. Each reusable entry hardcodes
one identity and environment; callers supply operation data only.

| Identity | GitHub environment / entry filename | Authority and source |
| --- | --- | --- |
| plan-dev / plan-prod | e1-plan-dev / e1-plan-prod | Nonsensitive own lifecycle state and required metadata; approved develop / main respectively |
| infra-dev / infra-prod | e1-infra-dev / e1-infra-prod | Exact ordinary lifecycle gateway; approved develop / main |
| infra-high-risk-dev / infra-high-risk-prod | e1-infra-high-risk-dev / e1-infra-high-risk-prod | Distinct approved data/apps lifecycle gateway; develop / main and deliberate operator approval |
| release | e1-release | Neutral approved-source release gateway; develop |
| deploy-dev | e1-dev-deploy | Dev normal delivery and history rollback; develop |
| promote-prod | e1-prod-promote | Independent prod delivery/history rollback; main and deliberate operator approval |
| emergency-dev / emergency-prod | e1-dev-emergency / e1-prod-emergency | Existing-content recovery only; develop / main and manual operator approval |

Non-plan roles have only `lambda:InvokeFunction` on their installed numeric gateway
version, constrained by `aws:RequestedRegion`, and `s3:GetObject` on their class's
sanitized public completion objects. There is no direct ECS/ALB/ECR mutation,
StartBuild, finalizer/cleanup/NAT invocation, IAM administration, PassRole,
AssumeRole, security state, eligibility administration or control-code write.
Dev/prod endpoints and result namespaces are disjoint. Protected bucket policies
also deny external writes and internal object reads.

The two plan identities have an explicit read inventory, exact own state keys,
ECS services/clusters, approved task/execution/flow-log role metadata, instance
profiles and cleanup function configuration. They cannot apply, write state/locks,
read secret values, download cleanup function code or invoke a controller.
Required region-wide EC2/ELB/ASG/Logs metadata reads and ECS DescribeTaskDefinition
have `Resource="*"` where AWS lacks resource authorization. They remain isolated
to read identities with `aws:RequestedRegion`; their pinned code and protected
resource inputs select the observations. IAM cannot enforce an environment filter
on those unsupported read actions. See the [ECS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ecs.html),
[EC2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html)
and [ELBv2](https://docs.aws.amazon.com/service-authorization/latest/reference/list_elbv2.html)
authorization references. This does not grant cross-environment mutation.

## Trust and source binding

Trust fixes the account's GitHub provider, `aud=sts.amazonaws.com`, repository,
responsibility environment and complete `job_workflow_ref@<40-character-SHA>`
subject. The repository's ordered customization is
`["repo","context","job_workflow_ref"]`; colons inside values are escaped with
`%3A`. There is no default-sub alternative, wildcard repository/ref, role chaining
or OIDC trust on internal service execution roles. Moving refs, PR/fork contexts,
wrong audiences, other responsibilities and missing pins fail closed.

Branch/reviewer enforcement comes from externally verified GitHub environment
and source-ref protections, with a redundant branch/event check in the pinned
entry. A GitHub-issued diagnostic token binds the immutable checkout to the
entry's actual reusable workflow identity before any AWS credentials exist;
STS subsequently verifies the cryptographic trust. No caller checkout or
caller-supplied command executes under AWS credentials. Checkout is pinned to
[actions/checkout v4.2.2](https://github.com/actions/checkout/commit/11bd71901bbe5b1630ceea73d27597364c9af683)
with persisted credentials disabled. Plan tooling fixes Terraform 1.13.4 through
[setup-terraform v3.1.2](https://github.com/hashicorp/setup-terraform/commit/b9cd54a3c349d3f38e8881555d616ced269862dd).
Jobs use ephemeral hosted runners and have no secrets-inherit/admin-token path.

## Requests, outcomes and workflow overlap

[The stdlib client](../../scripts/workflow_requests/client.py) rejects unknown or
duplicate fields, arbitrary resources/roles, oversized requests and malformed
IDs/counts. It generates normal/recovery correlation IDs, invokes once without
mutation retries or alternate credentials, and polls only public completion.
Transport acknowledgement or CodeBuild success never substitutes for protected
controller success. Qualification completion includes the exact qualified release
ID/source; timeout, absence and uncertain/failed completion fail the workflow.
Readbacks/errors, state, JWTs and credentials are withheld from logs and outputs.

The existing finalizer and delivery/lifecycle/recovery runtimes now publish
create-only `public.json` results under their already owned prefixes. Persistence
is read back before reporting completion. Their authorization, qualification,
current eligibility, E3, protected dev activation and prod approval algorithms
remain unchanged. Public records convey no qualification/eligibility authority.

Public release-build, deploy-dev, promote-prod, rollback-manifest, cd-rollback,
cd-terragrunt, cd-demo-api, remote-plan and CD orchestration paths are rendered
as thin responsibility callers. Legacy workflow AWS-role secrets, app-CD/TG_CD
fallbacks and direct mutation commands were removed. PR diagnostics are static
and have no OIDC permission. Remote plans use approved immutable source rather
than PR code. The existing no-AWS scope classifier is retained in cd-scope.
CD preserves layer dependency order, fails closed on critical/unmapped paths,
uses read-only infra-ready before release and keeps prod application promotion
manual with an existing qualified ID; it never rebuilds on main.

High-risk reconciliation selects data/apps only. Full teardown retains WP5's
independently approved all-layer operation. The exact lifecycle operation UUID,
revision and request must be known to the operator before its protected approval
is published; workflow preparation emits them without gaining authority. GitHub
approval alone cannot replace WP5's exact request-hash approval. Delivery consumes
the same protected qualified artifact identity, and independent prod authorization
cannot be supplied by dev success or a caller flag.

## Truthful installation and activation

Canonical `authority.wp6.approvals` is empty. All eleven request roles remain
deny-only, all sixteen WP4D bindings and all eight WP5 bindings remain inactive,
and no genuine installation, environment readback or GitHub conformance is claimed.
There are no fabricated S3 VersionIds, approval records, deployment observations
or installed packages. Missing prerequisites fail before token acquisition in
canonical public callers; reusable entries also reject missing configuration.

The [fixed renderer](../../scripts/workflow_requests/render.py) emits explicit
inactive failures when no verified immutable pin exists. For an admin-admitted
record it emits only the exact remote reusable `uses: ...@SHA`. It never emits
moving refs or a guessed self-referential future commit. Positive projections in
tests are synthetic, not approvals. The authority source binds exact workflow,
client/dependency and governance-file hashes. Runtime package hashes changed for
the compatible completion bridge; the accepted build/finalizer core package bytes
stay unchanged. WP2/WP4D/WP5 exact bucket/key/hash/version/readback and runtime-image
installation contracts still gate every internal endpoint.

`RequestAdminChannel` reuses the existing separately authenticated administrator
port convention. Its approval helper requires a complete genuine observation of
immutable Git source hashes, endpoint/plan bindings and all nine existing
[G1–G9 expectations](../../ci/authority/governance.json). A configured flag or
workflow JSON is not this evidence. There is no live channel/default observation.
The admin-installed GitHub environment configuration contains only the closed
client configuration; it cannot add roles, policy, source overrides or controller
parameters. Terraform additionally matches the entire admitted record and, for
mutations, an actually materialized qualified endpoint. Altering module/caller
inputs cannot activate or replace the protected record.

After genuine separately authorized installation/conformance, the administrator
must approve the immutable entry source, record exact observations through the
admin port, regenerate the fixed wiring/callers and publish the matching protected
environment configuration. Old trust pins are replaced, not accumulated. No such
operation occurs in this checkpoint. No migration or resource adoption is needed
for this undeployed greenfield repository.

## Bounded validation and remaining work

Run `python -I -B scripts/tests/workflows/run.py` and
`python -I -B scripts/tests/workflows/check_static.py`. The focused suite has 61
tests: eleven positive and negative responsibility pairings, closed operation
schemas, production independence, exact IAM action/resource/condition cases,
admin observation/installation gates and pre-credential source binding.
The static checker evaluates actual generated Terraform gates/trust/policies,
IAM inline size and protected bucket deny policies in a disposable root with no
provider/backend. Eleven synthetic identities are representable; canonical
activation is zero. The final provider-free regression run passed all 959 tests
(898 accepted WP1–WP5 tests plus 61 WP6 tests), with zero failures, errors or skips.
Source inventory (508 entries), Python/JSON parsing, generated workflow/security
wiring, deterministic extracted packages, WP4D/WP5/WP6 static checks, Terraform
formatting, local documentation links and `git diff --check` passed.

The implementation self-check is bounded to WP6 requirements. Concrete corrections
included immutable pre-credential checkout binding, lifecycle approval correlation,
conditional public-result persistence, metadata-only cleanup inspection, unsupported
ECS read scoping, ordinary-before-high-risk lifecycle ordering, fail-closed IAM
inline size limits and test-double support for resource-policy complement operators.
No independent/adversarial review or new approved architecture was introduced.

WP7 owns frozen legacy Terraform/action/helper retirement, residual trust/session
closure and final E1 acceptance. Legacy files are not an installation instruction
for this empty account. Known WP4A-N2 documentation encoding remains non-blocking
maintenance debt. Live GitHub governance, IAM/provider behavior, installation and
readbacks, authoritative AWS membership and fresh Linux E3 execution remain
unverified. Passing offline tests does not establish AWS operational readiness.
