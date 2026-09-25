# E1 WP2C — protected controller compute foundation

Classification: `E1_WP2C_PROTECTED_CONTROLLER_COMPUTE_FOUNDATION`.
Baseline: `0c50721424225843bd4418562a9298d1730fef44`.
Repository TARGET foundation only; not deployed, operational, WP2 complete or E1 secure.

## Plan reconciliation and bounded implementation

The immutable [plan sections 1 and 5.1](../../specs/iam-hardening/plan.md#51-entry-and-execution)
select one Lambda gateway/version per request capability and fixed on-demand
CodeBuild projects for long-running build, lifecycle, normal delivery and emergency
recovery. [Section 4.2](../../specs/iam-hardening/plan.md#42-internal-principals-and-interactions)
separates ordinary/high-risk and dev/prod responsibilities. Section 6 assigns
controller code, configuration and IAM to separately authenticated security
administration. No spec or planning decision changes in WP2C.

| Existing WP2B class | WP2C declaration | Count |
| --- | --- | --- |
| request-gateway | Separate Lambda skeleton for each non-plan request capability | 9 |
| build | Neutral release CodeBuild skeleton | 1 |
| environment-lifecycle | Ordinary/high-risk, dev/prod CodeBuild skeletons | 4 |
| normal-delivery | Dev deployment and prod promotion CodeBuild skeletons | 2 |
| emergency-recovery | Dev/prod emergency CodeBuild skeletons | 2 |
| qualification-finalizer | Reservation only | 1 binding |
| status | Reservation only | 3 bindings |
| cleanup-recovery | Reservation only | 2 bindings |
| nat-recovery | Reservation only | 2 bindings |

These are the existing nine classes and 26 bindings, not a new taxonomy. The
four reserved classes have no new role or compute declaration. Planning identities
are not request gateways. Ordinary and high-risk lifecycle have separate projects
and execution identities even though they share a bundle class.

## What the skeleton actually declares

[authority.json](../infra/security/authority.json) adds `controller_compute`.
[The module](../infra/security/modules/controller_compute/main.tf.json) declares:

- 18 `terraform_data` records containing the protected, resolved node/bundle relation.
- 18 execution-role skeletons with no trust Allow and explicit deny-all permissions.
- Lambda and CodeBuild resource templates whose instance maps are **empty**.

Thus a future authorized apply of this slice would create declaration records and
inert roles, **zero Lambda functions and zero CodeBuild projects**. Nothing was
applied here. `declared=true` means the repository skeleton exists, not that AWS
compute exists. This distinction is also explicit in the output instance lists.

No executable bundle or digest-pinned runtime image exists. The accepted WP2B JSON
notice artifacts are not Lambda packages or controller programs. WP2C does not
invent a ZIP, image digest, handler, VersionId or upload to make compute instantiate.
Lambda templates reserve image packaging; CodeBuild reserves `NO_SOURCE` with a
canonical buildspec whose sole command is `exit 1`. Both image fields are null and
unusable. There is no controller checkout, bundle downloader, supervisor or domain
handler. A later reviewed image/loader must implement exact-version byte checking
before any bundle execution; the current buildspec cannot run a bundle.

CodeBuild has no artifacts, cache, privileged mode or log writes. Gateway reserved
concurrency is zero. The only future environment value is canonical
`E1_PROTECTED_CONFIGURATION`, generated from the exact node and its downstream
node, including their bundle references. No arbitrary environment map, command,
source, buildspec or role input is exposed. Null images are never passed to an AWS
creation call because no compute instances are admitted. Provider-backed validation
of these templates remains UNVERIFIED; it is not substituted by an apply claim.

## One canonical relationship

The [compute admission/renderer](../../scripts/tests/security_root/compute.py)
derives expected topology from the already admitted WP2B engine and consumer map:
each gateway consumer matches exactly one CodeBuild consumer. Ambiguous, missing
or cross-responsibility matches fail. No test-owned duplicate mapping exists.
Canonical nodes reference WP2B binding IDs; Terraform resolves complete references
from that same catalog instead of maintaining digest/key copies.

Each node has a fixed name, kind, engine, bundle binding, role name/class,
request identity or null, and downstream binding or null. Gateway/project names
and the downstream relation are not request parameters. A different admitted
bundle/class or another environment's project is still a substitution and fails
admission. Future CodeBuild service trust must be separately reviewed, service-only,
and constrained to the exact protected project ARN/account; current trust has no
Allow at all. No StartBuild, InvokeFunction, PassRole or role-assumption grant exists.

The WP2B reservation resolver remains **not invocation authorization**. Later
privileged consumers must load their selected class/consumer/digest/key/version
from protected configuration, never request data. Security administration remains
the trust root; there is no claim of WORM storage against that administrator.

## Fail-closed activation and exact version

Both canonical admission and Terraform prevent activation. Node prerequisites
remain false: installed bundle, verified readback, accepted controller contract,
complete role permissions, and accepted request/trust wiring. Image digests remain
absent. Bundle references retain their original null VersionIds, UNVERIFIED
installation and inactive status.

The actual Terraform instance expressions require all those prerequisites,
operational state, a nonempty non-null exact version, verified installation and a
pinned image digest. Separately, `creation_supported=false` is a closed WP2C
invariant. Resource preconditions on declaration records and roles reject changing
that flag or global operational status, even if someone fabricates all the other
prerequisites. Source admission rejects individual node/prerequisite changes too.
There is no enable switch or alternate admitted source.

Later installation/activation must introduce an explicitly reviewed implementation,
not merely change booleans. The required identity remains class + consumer + approved
SHA-256 + exact object key + exact installed VersionId, with verified byte readback
before execution. `GetObject(key)` against latest, ETag comparison, metadata-only
approval and retained historical content are not acceptable substitutes. WP2B's
[administrator installation contract](e1-control-bundles.md#administrator-installation-contract)
remains unchanged; no object was installed or read back here.

## Minimal request and StartBuild boundary

The production contract helper is an offline source-admission module, **not a
deployed handler**. It accepts only the bounded duplicate-key-free envelope
`{"schema":"E1_WP2C_INACTIVE_V1"}`. It rejects every other field, including nested
payload/data maps, selectors, principal/environment/approval claims, AWS account
or region, Terraform paths, routing targets, roles and runtime configuration.
Business schemas remain for later packages.

`describe_start` constructs only `projectName` from the protected gateway's exact
canonical downstream node. Its gateway argument represents administrator-selected
configuration, not requester input. This is a non-executing reservation preview.
`request_start` rejects even a valid envelope with `WP2C_INACTIVE`; neither function
accepts an AWS client/transport or invokes a subprocess. No boto/AWS SDK is used.

The closed future StartBuild shape excludes sourceVersion, source/type/location,
secondary source/version, buildspec, environment, image, compute, role, artifact,
cache, privileged-mode, debug, logging, encryption and all other overrides.
Unknown fields fail rather than becoming an implicit extension. `projectName`
itself is forbidden in requester data despite being the one internally constructed
API field. Server operation-record creation and operation IDs are not implemented.

AWS confirms that StartBuild accepts execution-changing overrides; a safe project
configuration alone does not prevent a directly authorized caller overriding it.
[StartBuild API](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html).
Therefore no requester or gateway receives StartBuild permission in WP2C.
Future exact service trust follows the [CodeBuild service-role contract](https://docs.aws.amazon.com/codebuild/latest/userguide/setting-up-service-role.html).
Resource shape references: [Lambda provider definition](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/website/docs/r/lambda_function.html.markdown)
and [CodeBuild provider definition](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/website/docs/r/codebuild_project.html.markdown).
These documentation checks do not initialize or validate a provider.

## Authority, admission and preservation

Execution roles reuse the canonical WP2A deny-all policy. They have no S3/log read
or write, domain permissions, self-mutation, project mutation, invocation or role
passing. Service-specific deny-only trusts are inert. All eleven request roles
retain their original trust and permissions unchanged. Future operational service
trusts, boundaries and action inventories require separate accepted slices.

The closed target source admits one compute module, called only by the neutral
security root. Added Lambda, CodeBuild, IAM, source, buildspec or configuration
surfaces and ordinary-root copies are rejected, not semantically interpreted.
Actual Terraform must match the canonical renderer. Existing broad CURRENT legacy
authority is unchanged and excluded from target acceptance; this slice does not
claim to revoke its live privileges or protect an already deployed account.

The two ownership implementation labels for controller IAM and controller code now
say `WP2C_INERT_COMPUTE_FOUNDATION`. They do not claim completed IAM migration or
installed enforcement. WP1's bounded CURRENT evidence and WP2A's eleven inert
request identities remain. WP2B's artifact bytes, hashes, all 26 reservations,
storage policy and installation grammar remain unchanged. Its no-compute test now
checks the WP2B surfaces and explicitly checks WP2C inactivity; WP2C independently
checks the new disabled resource templates and roles.

## Validation and deferred work

Run `python -I -B scripts/tests/controller_compute/run.py --report <temporary-path>`
with all three accepted suites. The 24 WP2C tests exercise actual canonical source,
Terraform drift, fixed relations, role authority, malformed requests, forbidden
overrides, fake activation, alternative bundles and out-of-model compute surfaces.
Positive reservation previews prevent reject-everything behavior from passing.
Fixtures are disposable and the runner uses the inherited credential/process/network
guards. No controller executes in AWS.

Provider-free expression evaluation checks real root decoding, joined bindings,
empty instance maps and creation preconditions in a disposable no-provider/no-backend
configuration. JSON/Python parsing, link review and formatting are offline checks.
Git Bash remains FAILED/UNRESOLVED cleanup; supported Linux remains UNVALIDATED.
Provider-backed validation and live security bootstrap/storage/install/readback
remain UNVERIFIED.

Deferred: executable image/bundle installation and verification loader, service
trust activation, StartBuild/InvokeFunction, business envelopes, operation records,
qualification/status, release publication, ECS/ELB/PassRole, E3 migration,
lifecycle execution, cleanup/NAT, OIDC/workflow cutover and legacy revocation.
WP2 and E1 remain incomplete.
