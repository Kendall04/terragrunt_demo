# WP4 recovery V2 — local review packet

Status: **IMPLEMENTED / OFFLINE TESTED / NOT APPROVED FOR INSTALLATION / NOT DEPLOYED**.
No AWS, IAM, secret value, installed binding, workflow, controller factory or live
resource was changed. This is a source review package, not an installable or
qualified controller image. V1 remains the installed source factory's default.

## Concrete change

`scripts/normal_delivery/recovery.py` adds explicit `RecoveryAuthorizer` and
`RecoveryDelivery` types. They reuse the V1 qualifier, release eligibility,
resource membership, recursive task model, readback normalization, WP4B state
machine, durable journal, E2 owner and E3 gates. No second deployment controller,
SDK adapter, public endpoint or permissions were added.

V1 constructors and schemas remain strict: a V2 binding is rejected by the V1
authorizer, and a V2 authorizer is rejected by the V1 delivery constructor.
The normal authorizer's small shared hooks return the original V1 behavior.
The journal contract hook returns V1 by default. Neither a request field nor
merely publishing a V2 document selects the new factory.

| Contract | Normal V1 | Explicit recovery V2 |
| --- | --- | --- |
| Binding | `E1_DELIVERY_BINDING_V1` | `E1_DELIVERY_BINDING_V2` |
| Runtime intent | `E1_AUTHORIZED_RUNTIME_INTENT_V1` | `E1_AUTHORIZED_RUNTIME_INTENT_V2` |
| Operation journal | `E1_DELIVERY_OPERATION_V1` | `E1_DELIVERY_OPERATION_V2` |
| Environment | Existing dev/prod rules | Dev only, at most two replicas |
| Connection projection | Existing base secret ARN | Same closed base ARN plus exact VersionId |
| Startup migrations | Existing default | Exactly `Database__RunMigrationsOnStartup=false` on app |
| Probe, roles, commands, network model | Existing closed model | Same closed model; no probe credentials/override |
| Selection | Existing protected factory | Separately reviewed protected factory and binding |

`ci/authority/recovery-profile-v2.json` pins the unchanged V1 model hash and the
single allowed delta. Its canonical SHA256 is
`dff756555488f995b7c8daed1b20735ee904bfb24e91d6849fb32854ee8cd6f2`.
The underlying image qualification remains `E1_RUNTIME_V1`; V2 names the recovery
configuration contract. This does not claim a new image qualification was run.
The selected task is inverse-projected through the original V1 validator, so
the two allowed changes cannot open arbitrary environment, commands, roles or
capabilities. Linux Fargate platform is explicitly pinned to `1.4.0` in V2.

## Protected approval and evidence

V2 uses the existing admin-owned/current-read `Facts.environment` binding path.
Its additional `recovery` object binds an exact operation UUID, approval UUID,
base-binding hash, profile/model hash, immutable secret VersionId, evidence hash
and one or two explicitly approved release/qualification/image/schema tuples.
The caller body remains release/history and replica count; no recovery, secret,
endpoint, model, role or approval override is accepted.

Evidence is closed metadata: account/region, distinct source/target generations,
positive terminated-source state before restore writes, a target created after
the request, CHECKDB result, one private endpoint, task SG membership, restoration
schema hash and references to fence/network/runtime/connection-version receipts.
The exact secret ARN, VersionId and CMK must match the protected binding. The
existing qualifier independently resolves the release ID to the qualified image
and compares the complete qualification hash with the approved tuple.

Writer labels, status fields and hashes are **not authentication**. The existing
protected namespace adapter must authenticate the admin writer and current
version; the admin approval must vet the referenced native verifier receipts.
The contract does not fetch or reconstruct those receipts, read a secret value,
prove the reported SQL/schema state, or establish a continuously fresh network
lease. Fixtures are not approved native evidence. Before installation, each
allowed image must also be qualified to honor the migration-off profile against
the reviewed restored schema.

The proposal requires the observation to be at most 900 seconds old **at approval**,
and an approval interval of at most 24 hours. Current approval/status/expiry and
the complete binding are rechecked on reauthorization. The observation does not
silently expire halfway through an operation merely because it ages after that
approval. These are proposed admission parameters, not changes to backup cadence,
RPO, retention or AWS budget. The existing WP4 operation deadline remains 1800
seconds. Installation must bind the clock to the protected runtime, never JSON.

No extra storage read or new prefix is required: approval/evidence metadata is
inside the existing protected binding envelope. Membership reads and image
qualification are unchanged. No IAM policy or runtime grant was modified; actual
execution-role access to the selected secret version still needs native preflight.

## Transition and rollback

1. Review this exact source/profile/diff and pin a new controller package containing
   both the profile descriptor and V2 code. The installed WP4D factory is **not
   wired or changed by this packet**. A reviewed future installation must select
   the two V2 types explicitly and bind the exact operation ID and runtime clock.
2. Require V1 operations to be terminal or reconcile their existing owner first.
   Do not reinterpret a retained V1 operation as V2, overwrite a journal, steal an
   E2 owner, reset a deadline or clear an uncertain result.
3. Complete and review native cold restore/private-listener/fencing evidence,
   schema compatibility and immutable secret-version receipt. Publish the matching
   V2 binding only through the existing protected admin path. An unknown,
   incomplete, revoked, expired or mismatched approval fails closed.
4. Deliver through the same WP4B/E2/E3 flow. Repeated completed calls return the
   retained historical receipt without new effects. Changing approved metadata
   changes intent identity and blocks continuation; it is not an in-flight retarget.
5. Roll back only with a **new** approved operation and a qualified compatible
   image in its allowlist. V1 success history may identify that old release; its
   old task/secret configuration is never reused. The new task retains the same
   recovered DB secret VersionId and migrations-off profile. No DB/schema rollback
   or reconnection to the terminated source is implied.
6. Return to V1 only after V2 is terminal and the protected normal connection has
   been independently proven to point safely to the recovered DB. Never restore
   an old unversioned binding blindly. If uncertain, stop activation and reconcile
   rather than using V1 as a bypass.

## Local evidence and exact remaining gate

Tests exercise actual authorization/readback/state-machine code with protected-port
doubles: V1 compatibility, V2 selection, wrong versions/profile/model/roles/commands,
account/region/digest/schema, missing approval, expiry, revocation before switch,
replay without effects and rollback between distinct qualified-image fixtures
from V1 history while retaining the recovered connection. No native effects occur.
The same V2 test class is included in the existing explicit recovery CI through a
thin discovery shim, not duplicated tests or a new workflow.

The service dry plan also corrects the old release-ID=image-digest assumption:
the release ID hashes the qualification record. A plan checks metadata format;
the protected qualifier establishes its real relationship to the image. A plan
or rendered task still grants no activation authority.

Before **any** install/deploy: review the protected factory/package selection,
receipt provenance/per-image profile qualification, current versions and effective
IAM, the full integrated saved plan/budget/retirement and owner LIVE window. No new
cycle or spend is authorized here; previous trial budgets remain closed. SQL
private binding, real Fargate/E3/public decrypt-write-read and total recovery timing
remain native acceptance work. SSM is unresolved and was not retried or bypassed.

## Final review and next local acceptance gate

The focused review closed the new retained V2 proof record: its profile/model,
operation UUID, approval UUID and digest fields must remain well formed even when
a corrupted intent carries a recomputed hash. Malformed retained records keep
the existing failure/uncertainty classification and cannot continue effects.
V1 behavior was not changed by this V2-specific correction.

Final local coverage: 176 tests in the existing 12-suite recovery entrypoint,
including 13 V2 tests; separately, 20 existing V1 authorizer and 98 existing V1
delivery regressions passed. The 118 V1 regressions were not repeated after the
V2-only retained-record fix. These are in-process/fixture checks, not native AWS,
SQL, E3 or inbox delivery.

At the sealed d9e9772 checkpoint, the next local gate was installed-bundle/factory interoperability.
`scripts/wp4d/runtime.py:_normal` still selects `a.Authorizer` and `d.Delivery`,
and `_installed`/`installed.load` pins and verifies the administrator-published
bundle bytes. A future **offline** test must load the proposed code/descriptor
through that same loader, test an explicitly protected V2 factory selection and
validate history/public-receipt publication. It must reject a missing descriptor,
wrong pin/version, V1 factory fallback, caller selection and cross-operation
context. That wiring was not in the d9e9772 review packet. That immutable packet and its
hashes remain unchanged; the follow-up below versions the additional source work.

After that local gate, native receipt publication still needs an approved mapping
from real restore/fence/listener and connection-version receipts; missing timing
or identity fields must remain UNKNOWN. No fixture may be promoted to approved
evidence. New native deployment, access and spend require separate admission.

## Installed-loader/factory local acceptance — follow-up to d9e9772

The new **source** bootstrap accepts the optional administrator-owned configuration
field `delivery_contract`. Absence or `V1` selects the original exact V1 classes.
Only `SQL_RESTORE_NO_MIGRATIONS_V2` on `normal-delivery/deploy-dev` opts into the
new exact classes. The selector is not a gateway/event/request field. Unknown
selectors, PROD, emergency and cleanup selection of V2 are rejected. The trusted
clock comes from bootstrap process time; the operation comes from the existing
protected gateway/ownership envelope, never an added caller override.

The existing bundle builder includes the V2 code and pinned profile. The exact
version/digest loader and bootstrap self-consistency checks remain intact. All
16 local source materialization digests are regenerated through the existing
builder because the common bootstrap/dependency closure changed; this does not
install any bundle, update a controller image or authorize PROD/NAT V2. The source
installation/runtime-approval/environment-binding maps remain empty. No IAM
statement, resource, backend namespace or SDK permission was added.

A successful V2 operation uses the existing immutable success/public records and
color-history index. Its V2 intent is retained verbatim. It **cannot** emit an
`E1_DEV_ACTIVATION_RECEIPT_V1` for normal-runtime PROD promotion. The public receipt
continues to expose only operation/status and null release/source fields. Index
publication requires readback of the exact stored success receipt; a substituted
receipt fails. A hash or a fixture writer label is not authentication.

The original emergency history reader was missing the V1 `operation_contract`
hook after the earlier journal refactor. The one-line compatibility correction
restores V1 receipt closure and V1 emergency execution. It does not widen the
emergency authorizer: V2 history/authorizers are refused before any emergency
effect. Recovery rollback remains a new separately approved V2 delivery using
the restored connection and compatible qualified image, not replay of an old
task definition or reactivation of a potentially stale database endpoint.

Existing cleanup remains profile-independent: protected membership, active route
and nonzero active tasks must be proved before scaling only the inactive color
to zero and removing its cleanup target/rule. It neither registers a task nor
rewrites SQL secrets. Fixtures with V2 task data prove that active tasks stay up.
They do not prove native ECS draining or a real database's exclusivity.

`scripts/tests/wp4d/test_installed_recovery.py` loads actual builder-produced bytes
through `installed.load` and `_installed`, checks extracted module paths and warm
module cleanup, and executes the actual factory/state machine/history/public
adapters. AWS ports, protected facts, clock and E3 process are in-memory doubles.
Fixture eligibility/readback match the existing materialized DEV contract; no
production validator is mocked or relaxed. Missing/changed descriptors, pin or
version mismatches, wrong bootstrap, caller selection, V1 fallback and foreign
operation are rejected. This is local bundle interoperability, **not** actual
installation, AWS authorization, SQL recovery or public E2E acceptance.

### Transition, rollback and remaining gate

1. Review the new source commit, immutable bundle/bootstrap image and optional
   protected configuration together. The changed bootstrap requires a new image;
   an old image cannot load it because self-hash comparison fails. No image build
   or installation was performed by this follow-up.
2. Keep V1 selected until a separately admitted native recovery has authenticated
   fencing/restore/network/connection-version/per-image evidence and a reviewed
   current V2 approval. Tests and the synthetic review binding are never inputs
   for live approval.
3. Select V2 only in a separately reviewed installation for the exact DEV binding;
   preserve original package/image/config versions and the terminal journals.
   Installing this source or changing IAM/cloud configuration is not authorized
   by local tests. New deployment/access/spend still require admission.
4. Do not return to V1 by restoring a stale connection. Reconcile active tasks,
   current routing and the independently proven recovered DB connection first.
   If uncertain, stop activation; cleanup is not a database rollback mechanism.

The next implementable local gap is a strict projection of preserved native
restore/fence/listener/connection receipts into the V2 evidence contract. Missing
timestamps, identities, provenance or per-image migration-off qualification must
remain UNKNOWN and block an approved binding. No such native approval publisher
has been qualified. Live private SQL/Fargate/E3/public decrypt/write/read, complete
recovery timing and the owner's review window remain untested. SSM remains
unresolved; no retry, alternative principal or transport was used here.

Final follow-up regression: 40 WP4D tests (including seven installed-bundle cases),
176 recovery CI tests in 12 suites, 20 V1 authorization tests, 98 V1 delivery tests
and 53 emergency/cleanup/recovery tests passed, with zero skips. The seven new
cases were rerun after tightening two negative assertions; they are counted once.
No production validator was relaxed and no native cloud/SQL test ran.

## Consolidated next execution gate

The historical projection follow-up and the single remaining LIVE checklist are
in [ECS-LIVE-READINESS.md](ECS-LIVE-READINESS.md). It supersedes the pending local
projection item above without changing historical evidence or native approval.
