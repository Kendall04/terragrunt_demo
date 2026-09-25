# E1 WP2D — protected ownership and administrator publication closure

Baseline: `447db478a76e72cfa5eeb5d8ccc29472ca7c1f00`.
Repository TARGET implementation, pending independent review. No live deployment,
state migration, installation, provider validation or completed E1 claim.

## Scope and human recovery decision

Original [WP2](../../specs/iam-hardening/plan.md#10-implementation-work-packages-and-migration-order)
requires ownership extraction, protected output records and admin-only bundle
installation. The human clarification assigns cleanup/NAT security ownership to
WP2 and operational materialization to WP4. Recovery code/configuration, events,
invocation and NAT launch/user-data specifications are disabled reservations.
Recovery role identities and profiles are concrete neutral declarations. There
are no recovery functions, launch templates, event targets or invocation grants
in the TARGET tree. All 18 WP2C nodes remain unchanged and inactive.

## Extraction inventory and CURRENT separation

The canonical `ownership_closure` in [authority.json](../infra/security/authority.json)
contains resources, source identities, exact consumer bindings, dependencies,
recovery reservations and the empty administrator publication registry.
[ownership.py](../../scripts/tests/security_root/ownership.py) admits its closed
grammar and renders the neutral module. The root instantiates that module once.

| CURRENT location | Neutral TARGET extraction | Ordinary resources retained outside security ownership |
| --- | --- | --- |
| shared KMS | Two environment keys and aliases | None of these security objects |
| shared ECR | Three repositories and lifecycle policies | Build/publication behavior remains WP3 |
| shared artifacts | Account bucket, versioning, encryption, public-access/ownership and retention controls | Record-writing responsibilities remain later packages |
| shared GitHub IAM | Singleton OIDC provider, with no new OIDC role trust | Existing broad automation roles stay CURRENT exclusions for WP6/WP7; never copied as target grants |
| data IAM | SQL roles, secret/KMS policies, existing SSM attachments and instance profiles | SQL EC2/storage/alarms remain high-risk lifecycle |
| apps IAM | Both colors' task/execution roles, fixed managed attachment, secret/KMS policies | Services/logs/alarms remain high-risk lifecycle |
| global VPC IAM | Flow-log role and policy | VPC/subnets/SGs/flow-log resources/log group/ALB remain ordinary lifecycle |
| global NAT IAM | NAT instance role/profile; deny-only recovery Lambda role/policy | NAT ASGs/EIPs remain ordinary ownership; target materialization waits for WP4 protected launch interface |
| cleanup IAM | Deny-only cleanup Lambda role/policy | Cleanup behavior remains WP4 |
| secrets | Six metadata resources linked to exact environment keys | Secret values remain outside Terraform |

There are 35 concrete resource interfaces: 18 extracted roles, four profiles,
two keys, six secrets, three repositories, one artifact bucket and one OIDC
provider. Companion aliases/policies/attachments/storage controls have the same
neutral owner but are not independently published as mutable policy contents.
These 18 extracted roles are **additional to**, and distinct from, WP2C's 18
inert gateway/controller execution roles and WP2A's eleven inert request roles.

The original 137 IaC files retain their accepted, hash-pinned
`TRANSITIONAL_LEGACY_NOT_TARGET_ACCEPTED` classification. CURRENT recovery
executables remain solely under this exclusion, never second TARGET owners.
The new [TARGET tree](../modules/target) has concrete ordinary resource configurations
derived by [ordinary.py](../../scripts/tests/security_root/ordinary.py) from
those pinned inputs, with protected declarations removed and explicit record
bindings substituted. It does not call security modules or access security state.
No existing workflow is switched to these roots. WP5 still owns protected
lifecycle execution and its full behavioral contract.

The global TARGET omits the old NAT module because it would start instances
against an unavailable protected launch specification. It does not substitute
another launch template or recovery path. This is deliberate unavailability,
not a claim of operational networking. The ordinary NAT resources remain CURRENT
until their protected interfaces are materialized. The app bootstrap keeps zero
desired count and Terraform's revision/count ignore_changes, removes DB secrets
and workload roles from the bootstrap definition, and publishes the real role
identities for later protected delivery. No deployment registration API/tool was run.

Stable role/profile names, environment secret names, KMS aliases, repository
names and the account artifact-bucket naming contract are preserved. Inline
policy names are new WP2D configuration identities; no live policy move is implied.
Recovery policies/trusts are intentionally deny-only instead of copying broad
CURRENT recovery grants. Workload SQL/ECS/flow-log/NAT-instance service semantics
are retained; these are not controller or recovery trust activation. SQL keeps
its existing SSM attachment. Shared retention remains CURRENT-equivalent;
WP3 must implement its separate qualification/evidence policy before publication
of qualification evidence. No retention or qualification redesign occurs here.

## Protected output production and consumption

The neutral Terraform module outputs `protected_output_candidates` directly from
resource attributes. No generated AWS UUID or secret suffix is invented. Records
have schema, owner, scope, class, logical identity, declaration identity, authority
digest, availability, value and publication classification. Only bounded ARN
classes are supported. Names needed by ordinary consumers are derived from the
validated exact ARN, not a second caller-selected identifier.

The [publication module](../../scripts/tests/security_root/publication.py) exposes:

1. `publish_outputs`: read the dedicated output through an external admin channel,
   validate every record, and atomically publish the complete record set.
2. `promote_outputs`: return a reviewed-source change candidate containing that
   protected publication. It never writes files, runs Git or activates compute.
3. `consume` / `validate_consumer_input`: resolve a fixed consumer against the
   protected publication; reject any manually substituted input.

`AdminChannel` is an integration boundary, **not authentication implemented by
Python inheritance or an owner string**. A deployment adapter must authenticate
the separately held administrator, read only the dedicated Terraform output
(never raw state), and enforce create-only protected publication. Consumers get
read-only publication access. Production adapters and external authentication
remain UNVERIFIED/unimplemented; tests inject a narrow in-memory adapter.

Terraform consumers use a fixed path to the admin-owned canonical authority
publication registry. They require explicit `protected_inputs` equal to the
complete pinned publication subset. Missing/unavailable records fail rather than
falling back to names, defaults or local IAM creation. Random AWS IDs are trusted
because of protected publication provenance, not because they match ARN syntax.
Account, region, environment, class and logical identity are checked. Registry
promotion is a separately reviewed admin source change, never an ordinary input.

The registry is empty at this checkpoint: no deployed outputs have been obtained.
The old WP2A interface summary therefore truthfully remains `UNAVAILABLE`.
Eight recovery records always have `available=false`, `value=null`; no function
ARN is inferred from a reserved function name. Synthetic test records exist only
in test code and disposable evaluation files, never the canonical registry.

## Administrator installation and exact version

`install_bundle` accepts an admitted class/consumer and approved canonical bytes,
plus trusted admin storage/publication adapters. It does not accept a VersionId,
bucket/key selector, approval boolean, requester identity or runtime transport.
It derives the protected bucket/key, verifies the bytes and checksum, performs a
conditional create, validates the returned bucket/key/non-null version, reads
exactly that version, checks response identity and verifies bytes/digest again.
Only then does it create the protected installed-reference publication.

Write conflict, missing version, wrong response key/version/bytes or any read
failure publishes nothing. A failed read can leave an unpublished uploaded object;
there is no speculative rollback, overwrite, retry-as-latest or automatic adoption.
External bootstrap must resolve such conflicts deliberately. The test adapter
models only conditional create, exact versions, read failure and atomic publication.
It is not a fake S3 service and no AWS adapter is installed.

Installed references bind class, consumer, approved digest, bucket, exact key,
returned VersionId, verified readback and authority/publication provenance.
They explicitly remain `operational=false`, `executable=false`: WP2B payloads
are notices. Installation does not mutate WP2B reservations, compute prerequisites,
images, role policies, trusts, events or publication availability of recovery
endpoints. Content-addressed keys are not WORM; security administration remains
the trust root. A stored reference never replaces invocation authorization.

## Dependency closure and admission

All resource and recovery dependencies identify the security-root writer. Role
trust/policy, key/secret/profile relationships, publication and consumer bindings
are fixed. Recovery edges distinguish `WP2_PROTECTED_FOUNDATION` from
`WP4_OPERATIONAL_ACTIVATION`. Original recovery code and launch/user-data source
hashes identify CURRENT content only, not approved executable payloads. The SQL
bootstrap source used by the extracted ordinary configuration is also hash-pinned.

Repository admission compares every generated TARGET file, rejects additional
IaC roots and protected/target payload files, and preserves the immutable CURRENT
exclusion. It rejects alternate IAM/KMS/storage/compute, security remote-state
reads, alternate record files, ordinary recovery configuration and forged owner
classifications. This is repository TARGET writer evidence, not deployed IAM
enforcement against the broad CURRENT identities or external administrators.

## Validation and limits

Run the dedicated `python -I -B scripts/tests/ownership_publication/run.py` with
WP1/WP2A/WP2B/WP2C. WP2A/B/C fixture changes only copy newly pinned support sources
and compare generated HCL as text alongside JSON plumbing. The WP2B no-compute
assertion retains its own-surface meaning; WP2D checks ordinary target extraction
and disabled recovery independently. Accepted test method counts remain unchanged.

Provider-free evaluation must check decoded authority, the two empty WP2C maps,
positive synthetic protected inputs and rejection of missing/substituted records.
AWS provider validation remains UNVERIFIED. Git Bash cleanup remains
FAILED/UNRESOLVED; supported Linux remains UNVALIDATED. Live backend/bootstrap,
ownership/state migration, installation/readback and compute remain UNVERIFIED
and NOT PERFORMED/NOT DEPLOYED. No state addresses or live existence are inferred.
Any later migration requires actual inventory before separately authorized moves.

The extracted ordinary TARGET configurations live under `terraform/modules/target/`
and are uninvoked by CURRENT wrappers. This retains WP1 applicability semantics
without relaxing its unknown-root handling or CURRENT positive witnesses.

## Checkpoint validation

The WP2D checkpoint passed WP1 236, WP2A 18, WP2B 22, WP2C 24 and WP2D 35
tests, with zero failures, errors or skips. Canonical/source inventory, Python/JSON
syntax, local links, Terraform/Terragrunt check-only formatting and staged
`git diff --check` passed. No WP1 evaluator or test assertion was changed.

Provider-free Terraform evaluated the actual compute locals: 18 nodes, empty
gateway/project maps and a true creation guard. All ten extracted consumer
configurations accepted matching synthetic administrator publications and rejected
missing/substituted protected inputs with resource-precondition failures. These
checks ran in disposable directories using the built-in Terraform provider only;
no provider initialization, AWS access or state migration occurred.

The accepted compute, bundle, request-identity and wrapper templates remain
byte-identical. The authoritative spec/plan and accepted ancestry are preserved.
This evidence requests independent review; it does not accept WP2 or prove live
security administration, deployment or external adapter enforcement.
