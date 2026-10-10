# E1 WP2A — protected security root foundation

WP3C adds [internal release wiring](../../docs/e1-internal-release.md) within this
root. Canonical installation/runtime records remain empty; no live resources or
external request authority are claimed.

WP4D adds [exact IAM and selective materialization](../../docs/e1-wp4d-iam-materialization.md)
for the accepted delivery/recovery contracts. Its installation and environment
maps also remain empty, so no WP4D compute or external request grant is active.

WP5 adds [protected environment lifecycle](../../docs/e1-protected-environment-lifecycle.md)
using the eight existing ordinary/high-risk reservations. Installation, approval
and environment-binding registries remain empty; lifecycle compute stays inactive.

Classification: `E1_WP2A_PROTECTED_SECURITY_ROOT_FOUNDATION`.
Repository foundation only; **not deployed, not WP2 complete, not E1 secure**.
The accepted baseline is `c8e880b552b5782e9bca94891b75a71b45ddc113`.
The immutable [spec](../../../specs/iam-hardening/spec.md) and
[plan section 6](../../../specs/iam-hardening/plan.md#61-security-root) govern it.

WP2B extends this accepted foundation with the
[protected control-bundle contract](../../docs/e1-control-bundles.md): canonical
inactive bundle reservations and admin-only storage. The WP2A identity, backend
and external-administration boundaries below remain unchanged.

## Neutral root and external administration

`terraform/live/security/terragrunt.hcl` selects this root. It inherits neither
dev nor prod configuration and has no dependency on either environment. The root
calls `modules/request_identities` and the WP2B `modules/control_bundle_storage`.
WP2C adds `modules/controller_compute`; WP2D adds
`modules/protected_resources` and the [ownership/publication substrate](../../docs/e1-ownership-publication.md).
No workflow or existing bootstrap script invokes it. The existing operational
dev/prod paths are unchanged.

The operator supplies an **existing, separately authenticated human administrative
principal**. This root does not create an admin role, assume one from a requester,
or grant administration. The input ARN records that external identity; it is not
credentials, an authentication check or proof of admin permissions. The AWS
provider restricts the selected account. Actual caller authentication and backend
access controls remain external, UNVERIFIED prerequisites. Do not run apply with
ordinary lifecycle credentials or interpret the source contract as AWS enforcement
against the still-broad legacy roles.

## State and empty-account bootstrap contract

The S3 backend is separate from environment lifecycle state. Before a separately
authorized init, the human admin must establish a dedicated admin-only bucket,
versioning, public-access blocking, TLS-only access and admin-only state/lock
permissions. That bootstrap implementation and any live policy verification are
deferred. There is no backend auto-creation or state migration in this slice.
Terraform >=1.10 S3 native locking is required; the repository CI selects 1.13.4.

The external administration interface requires these non-secret values with
**no dev/prod fallback**:

| Input | Meaning |
| --- | --- |
| `E1_SECURITY_STATE_BUCKET` | Externally bootstrapped dedicated admin bucket name |
| `E1_SECURITY_STATE_REGION` | Its actual region |
| `E1_SECURITY_ACCOUNT_ID` | Admin-selected account, checked by the provider |
| `E1_SECURITY_AWS_REGION` | Security resource region |
| `E1_SECURITY_ADMIN_PRINCIPAL_ARN` | Existing same-account human-admin IAM role/user ARN |

Backend key is `e1/security/terraform.tfstate`; its lock is the corresponding
`.tflock` object. Encryption and `use_lockfile` are fixed true. Bucket and lock
administration remain security-admin owned. The generated root fixes key,
encryption and locking directly from the canonical source. Bucket and region are
deliberately unspecified partial-backend inputs: a later authorized admin init
must supply them as backend configuration from the first two interface values.
The wrapper reads only the account, resource region and admin ARN inputs. It does
not initialize or provision a backend, and cannot grant external permissions.
Do not put credentials, token files or secret values in backend arguments, tfvars,
the authority source, outputs or state. Ordinary lifecycle has neither read nor
write access to this state in the target contract, including the lock object.

There is deliberately no bootstrap/apply command in this implementation task.
The current empty-account assumption does not assert that the backend exists.

## One closed authority source

[`authority.json`](authority.json) is the canonical WP2A target authority and
ownership contract. It contains the role inventory, exact deny-only IAM documents,
ownership categories, backend requirements, future interface reservations and
UNVERIFIED governance expectations. Terraform loads it using `templatefile` and
`jsondecode`; the sole substitution is the validated admin principal ARN.
Both role trust and inline permission policy are encoded from that same object.
No second policy body is maintained in Terraform or expected-answer fixtures.

[`model.py`](../../../scripts/tests/security_root/model.py) validates a closed
WP2A grammar and generates the fixed `.tf.json` plumbing and Terragrunt wrapper.
[`render.py`](../../../scripts/tests/security_root/render.py) checks by default;
`--write` regenerates only that plumbing. Tests compare the checked-in wiring to
the generator, then evaluate documents from the authority source with WP1's
admitted policy semantics. This is not a general HCL or policy DSL interpreter.

Admission covers all repository `.tf`, `.tf.json`, `.hcl`, `.tfvars` and
`.tfvars.json` sources. Additional/changed target declarations, modules, backends,
provider mappings, hooks and input files fail. Protected-root payload files are
also closed. New mechanisms require an explicit reviewed grammar/generator/test
extension, not an inventory refresh. Source symlinks/junctions are not admitted.

The [legacy source snapshot](../../../ci/authority/target/legacy-sources.json)
pins the baseline's 137 IaC files as `TRANSITIONAL_LEGACY_NOT_TARGET_ACCEPTED`.
It is a migration exclusion, not a target Allow mechanism or proof of safety.
Its digest is independently pinned by admission. A new role hidden in ordinary
Terraform, a second security-root invocation or a changed legacy declaration
fails even if someone refreshes WP1's freshness inventory. Later migrations must
explicitly revise this exclusion with new target ownership evidence. Arbitrary
executable behavior outside the target root is not simulated; no target controller
execution is installed by WP2A.

## Ownership and output interfaces

The manifest distinguishes `SECURITY_ROOT_OWNED`, `ORDINARY_LIFECYCLE_OWNED`,
`HIGH_RISK_LIFECYCLE_OWNED`, `DELIVERY_CONTROLLER_OWNED`,
`RECOVERY_CONTROLLER_OWNED`, `EXTERNAL_GOVERNANCE` and `UNVERIFIED`.
All OIDC/IAM/trust/profile/boundary administration, KMS policy/grant authority,
secret metadata/resource policies, shared ECR/storage/evidence protection,
controller identities/code/configuration and security state/lock ownership point
outward to security administration. WP2A declares inert request identities; WP2B
declares bundle storage; WP2C declares inert controller identities; WP2D extracts
workload/recovery IAM, KMS, secret metadata, ECR, artifact storage and OIDC into
neutral TARGET ownership. Recovery execution remains disabled/reserved.

Ordinary owns intended network/platform skeleton reconciliation; high-risk owns
intended data/apps skeleton reconciliation. Normal revision/count/forwarding and
existing-color restoration are separate controller responsibilities. None owns
security controls, and no mutable ceiling is supplied to an ordinary module.
These are target ownership allocations, not changes to current runtime owners.

`foundation` outputs the stage, canonical-source hash, created request-role ARNs
and `target_accepted=false`. `protected_interface_contract` reserves ARN/ID-only
records for workload/recovery roles, KMS, secret metadata, artifact/evidence/ECR
identities and qualified controller endpoints. They remain `UNAVAILABLE`, without
invented resource identifiers. Later admin publication must expose only these
sanitized records; ordinary consumers must not use `terraform_remote_state` on
this root. WP2D now implements candidate output production, closed record
validation and offline administrator publication. The live publication registry
remains empty; no deployed identifiers or installation are claimed.

## Inert identities and deferred activation

Eleven neutral-root request identities are declared: plan-dev/prod, infra-dev/prod,
infra-high-risk-dev/prod, release, deploy-dev, promote-prod and emergency-dev/prod.
Their names use the new `e1-request-` namespace. Each has a trust document with
no Allow and an inline `Deny Action=* Resource=*`. Even the recorded admin is
denied assumption; admin manages these resources through separately held authority.
There is no OIDC principal in the declared trust, no endpoint, no operational grant and
no enable switch. Later activation must replace this inert policy through a
reviewed security-admin change; adding an Allow alongside the deny is insufficient.
No permissions boundary is introduced: final responsibility ceilings are deferred,
and boundaries will be defense in depth, never the sole proof.

Future OIDC expectations preserve repo/context/job_workflow_ref and distinct
responsibility/environment identities. Workflow paths are reserved contracts, not
installed workflows; commit pins are null/unbound and GitHub verification is
UNVERIFIED. No OIDC cutover or external setting is performed.

## Evidence limits and offline checks

Run from the repository root with installed Python, without AWS credentials:

```text
python -I -B scripts/tests/security_root/render.py
python -I -B scripts/tests/security_root/run.py --report <temporary-report-path>
python -I -B scripts/tests/authority/run.py --report <temporary-report-path>
```

Both test runners use WP1's credential/proxy scrub and socket/process guards.
Tests mutate disposable source copies. WP2A tests check ownership, inert trust
and permissions, competing declarations, wiring/source drift, backend separation,
external governance and retained CURRENT positive/PARTIAL witnesses.

WP1 is unchanged: CURRENT results remain trustworthy positive witnesses with
PARTIAL/UNKNOWN, not exhaustive negative authority proof. EFFECTIVE_DENY is
demonstrated only inside closed synthetic fixture universes. WP2A's synthetic
projection uses source policies but certifies only its explicitly enumerated
policy-permission routes, not the target repository/account. Final target negative
acceptance requires a genuinely closed admitted source universe after migration.
The legacy exclusion and deferred classes prevent any present E1-secure claim.

Static Terraform/Terragrunt formatting does not need initialization. Provider-
dependent validate may be unavailable without downloaded plugins; do not initialize
or download for this task. Git Bash selector remains FAILED/UNRESOLVED cleanup;
supported Linux execution remains UNVALIDATED. Windows tests do not clear either.

External deployment still owns live backend bootstrap/protection and state
inventory/migration. Repository TARGET ownership and offline publication exist;
live AWS bootstrap, migration, installation/readback remain UNVERIFIED / NOT
PERFORMED. Later packages own operational ceilings/boundaries, executable
controllers, images and activation. Controller/recovery execution remains inactive.
WP3–WP7 delivery/qualification,
runtime enforcement, protected lifecycle execution, workflow cutover and legacy
revocation remain out of scope. No state import, live IAM change or deployment
has occurred.

## WP2C — inactive protected compute foundation

The root also calls `modules/controller_compute`, described in the
[WP2C contract](../../docs/e1-controller-compute.md). It declares 18 protected
node records and deny-only execution roles, with zero Lambda/CodeBuild instances.
The earlier WP2A/WP2B sections describe their bounded contributions; the added
compute declaration is still not a deployed/operational controller plane. All
eleven request identities, bundle reservations and external administration
requirements remain unchanged. Run the dedicated
`python -I -B scripts/tests/controller_compute/run.py` suite with WP1/WP2A/WP2B.
