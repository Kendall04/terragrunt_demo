# E1 WP3A — qualification contract and protected finalizer

TARGET repository logic only. AWS compute, trust, permissions and live qualification
remain inactive/unverified. WP3 is not complete. This implements plan sections
[5.1, 7 and 10.3](../../specs/iam-hardening/plan.md#7-qualification-and-environment-evidence)
and [spec 5.3](../../specs/iam-hardening/spec.md#53-qualified-releases-and-runtime-authorization).

## Reconciliation inventory

The existing [release manifest](../../ci/schemas/release-manifest.schema.json)
contains app/repository/gitSha/sourceBranch, GitHub run/attempt/time, image
registry/repository/tag/digest/URI and quality fields. Existing publication uses
by-digest, by-commit and develop candidate keys, not an immutable public release
ID. Git SHAs may be abbreviated in that compatibility schema. The legacy renderer
defaults dotnetTests/dockerBuild to passed; scanStatus can be unknown. Those
interfaces remain unchanged for CURRENT compatibility and confer no E1 authority.
History/promotion still belong to later delivery/cutover packages.

The new path requires the full 40-character source commit, fixed approved repository,
neutral account/region/repository, exact digest and exact bytes of the by-digest
manifest at its protected VersionId. The manifest may retain discovery tags and
GitHub metadata; they are not used as qualification evidence. Contradictory legacy
quality is rejected, but passed quality never supplies missing required checks.
No historical artifact is enrolled based on legacy metadata alone.

## Closed contracts

[Machine-readable schemas](../../ci/schemas/e1-qualification.schema.json) define
wakeup, gateway operation, independent build observation, protected supervised
result, qualification, and minimal eligibility. All objects reject unknown keys.
The production [finalizer](../../scripts/qualification/finalizer.py) validates the
same schema definitions using a bounded interpreter for their supported keywords.
Required checks are defined once in the schema and read by the implementation:
.NET restore/build/test, image build/publication, packaged probe capability and
its no-server negative check. These come from plan 7.1 and the existing
[CI workflow](../../.github/workflows/ci-dotnet.yml). Scan status is not promoted
to a new required security check. Only explicit PASS for every required check
qualifies. FAIL/SKIPPED/NOT_RUN/UNKNOWN/null/missing never qualify.

The schema/runtime identifiers describe this qualification binding contract;
E1_RUNTIME_V1 does not implement or approve a future ECS runtime template.
The independent build adapter must observe the actual protected project's result
and required phase outcomes. It must not obtain its answers by copying the
supervised result or a completion notification. The future supervisor still owns
process-level results and source/image binding. Both records must agree with the
protected operation. There is no AWS adapter or build supervisor in WP3A.

## Ports, provenance and correlation

The finalizer accepts only a closed wakeup containing operation_id. This ID is a
lookup, never proof. Evidence.operation reads the immutable gateway-created
operation and protected dispatcher-owned build association. The build observation
must independently match that operation/build/project/source association; orphan
or cross-operation records fail. The dispatcher must prevent rebinding and cannot
let a requester manufacture operation IDs or associations. That future gateway
and dispatcher are not implemented or activated here.

Evidence.build reads independently observed facts; Evidence.result reads only the
supervisor-protected namespace; Evidence.manifest reads bucket/key/exact VersionId
and returns matching identity plus bytes. The SHA-256 is over those exact bytes.
The JSON decoder rejects duplicate keys, non-finite numbers and oversized input.
No application process is run by the finalizer. Application build code must not
write supervisor results; enforcement is the later supervisor/adapter boundary.

Protected ports and administrator-selected account/region are injected dependencies,
not request parameters. Project/repository/bucket names derive from accepted
neutral authority. JSON writer fields and Python subclass checks are not
credentials: production adapters must authenticate the fixed writers and protect
namespaces. A compromised security administrator is outside the accepted threat
model. No caller-supplied JSON document establishes trusted provenance.

Qualifications exposes only atomic conditional create and exact read. Only the
future finalizer identity may use the writer port. It offers no update, delete,
image publication, eligibility write, deployment or AWS proxy operation.

## Identity, publication and retries

Release ID is `sha256-` plus full lowercase SHA-256 of canonical qualification
content before adding release_id: sorted-key JSON, compact separators, ASCII
escapes, no NaN, one final LF. The tuple includes account/region/repository,
source, operation/build/project, image repository/digest, runtime/schema, explicit
checks, exact manifest bucket/key/VersionId/checksum and fixed writer identity.
Different build operations may therefore produce distinct qualified releases even
for the same image. This internal E1 ID does not replace existing public indexes.

The only publication key is `qualifications/demo-api/<release-id>.json`.
Publication uses conditional create and confirms persisted exact bytes. An exact
retry confirms identical bytes; different content at that key fails without
replacement. Write/read failure is not successful qualification. If a write
committed but its acknowledgement/read failed, retry confirms the same bytes.
A prior qualification remains historical if a later lookup fails; the failure
cannot manufacture a new success. No distributed transaction or compensation is
claimed. No status writer is introduced in this slice.

## Eligibility and limitations

Eligibility has a separate schema, SECURITY_ADMIN writer, release binding,
ELIGIBLE/REVOKED state and exact registry version. Validation proves shape/binding
only, not authenticity or currentness. Later delivery must read CURRENT protected
admin registry state and combine it with qualification, image availability,
runtime compatibility and deployment prerequisites. Finalization never reads or
writes eligibility, so revocation does not erase historical qualification.

Public finalization errors use fixed reason text, without transport exception
contents or evidence values. Records contain only bounded fields, never logs,
credentials, secret values or arbitrary environment/process output. Canary tests
cover unknown fields, discarded legacy tag metadata and transport failures.

WP2 authority, 18 compute nodes, empty instance maps, deny-only identities and eight
inactive recovery reservations remain unchanged. The WP2 JSON bundles still have
no executable payload; this code is not packaged or installed. No service trust,
IAM grant, image build, ECR push, workflow cutover or live migration occurs.
Git Bash cleanup remains FAILED/UNRESOLVED; Linux UNVALIDATED; provider validation
and live bootstrap/migration/install/compute/qualification remain UNVERIFIED,
with no migration, installation, deployment or qualification performed live.

## Offline acceptance

Run `python -I -B scripts/tests/qualification/run.py --report <temporary-path>`.
The runner uses the existing hermetic I/O guards and production validation logic,
plus deterministic in-memory ports. Run all five accepted suites unchanged in
meaning, canonical wiring/source inventory, syntax, local links, check-only
Terraform/Terragrunt formatting and provider-free compute expressions. No AWS or
dependency download is needed. Evidence is repository behavior, not AWS proof.

### V2 acceptance correction

The production finalizer remains byte-identical to WP3A V1; qualification authority
was not redesigned. The correction addresses two reproduced test defects: V1's
mutation loader rejected original-module adapter classes during setup and counted
that error as detection; removing the all-PASS guard survived its 51 behavioral
tests because non-PASS fixtures changed only one observation.

The corrected suite has 93 behavioral cases (the original 51 plus 42 paired-check
cases) and 17 mutation/control tests, 110 total. For each of the seven canonical
checks, both observations report matching FAIL, SKIPPED, NOT_RUN or UNKNOWN in
28 cases. Another 14 cases cover paired missing/null values, rejected by the
closed schema. Original one-sided cases and positive all-PASS qualification remain.

Adapters are constructed against the exact module under test. Mutation detection
requires a completed setup, a finalizer call and the intended qualification-outcome
assertion. Syntax, setup/type-identity and unrelated assertion failures are
HARNESS_INVALID, never security detections. An unchanged-source run executes all
93 behavioral cases and must survive with no failures/errors. Four deliberately
invalid controls verify classification, separately from security mutants.

Nine genuine mutations are detected: source, build ID, operation correlation,
image digest, manifest VersionId, checksum, persisted bytes, all-PASS enforcement
and deny-all. All 28 paired non-PASS assertions expose all-PASS guard removal.
Two redundant removals survive honestly: project equality remains protected by
fixed schema constants; required-field removal remains protected by check indexing
on the exercised finalizer path. These are not counted as detections. The normal
runner reports individual outcomes, reached cases and separate surviving/invalid
security-mutant lists. No security-significant mutant is accepted as surviving.

AWS adapters and live qualification remain deferred; WP3 remains incomplete.
