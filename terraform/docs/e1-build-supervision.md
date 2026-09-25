# E1 WP3B — exact-source supervision and executable packaging

TARGET repository implementation, pending independent review. WP3 remains
incomplete. No AWS adapter, process/container isolation adapter, installed runtime,
image publication, service trust or compute activation is supplied here.

## Architecture decision and evidence boundary

The owner decision following WP3A integration preserves the accepted
[qualification contracts](../../ci/schemas/e1-qualification.schema.json) and
[finalizer](../../scripts/qualification/finalizer.py) unchanged. A qualification-
consumable supervised result requires real immutable image identity and exact
manifest bucket/key/VersionId/checksum, including for FAILED results.

The separate [terminal attempt schema](../../ci/schemas/e1-build-attempt.schema.json)
is `E1_BUILD_ATTEMPT_TERMINAL_V1`. It is protected supervisor-owned internal
execution evidence, never qualification, eligibility, deployment evidence or an
external status response. It contains protected operation/build/project/account/
region/repository/approved-source context, observed source only when verified,
terminal stage, a bounded failure classification and all seven check states.
Artifact fields and release IDs are forbidden. Source acquisition failure records
no observed source and seven NOT_RUN checks. Early failure cannot manufacture a
digest or VersionId. WP3A rejects this envelope without fallback conversion.

An exact manifest identity is the boundary between the envelopes. Image creation
without verified manifest publication still produces terminal evidence only.
After exact manifest readback, a probe failure produces a structurally valid
FAILED WP3A supervised result retaining the real artifact identities. The finalizer
independently rejects its non-PASS check. The terminal record cannot repair or
outrank a supervised result. Future neutral status sanitization is deferred.

## Trusted host and application boundary

The [supervisor](../../scripts/build_supervision/supervisor.py) accepts an
operation-ID-only wakeup and protected context/ports injected by an administrator-
controlled host. The dispatcher operation must match every context identity.
Repository, project, image destination and manifest namespace are fixed by the
accepted contracts and canonical security configuration. Unknown wakeup/context
fields reject. No environment or application JSON selects adapters, commands,
source, Dockerfile, credentials, runtime image or storage paths.

`Control`, `Payload`, `Images`, `Manifests` and `Records` are narrow trusted ports.
Their Python interface identity is a configuration check, not authentication.
The application never receives these Python objects or supervisor store handles.
The deployment adapter must enforce that distinction independently.

The trusted acquisition adapter exports committed `demo-api` content from the
approved repository and full 40-character commit into a fresh core-selected
directory. Its repository/commit/path receipt must match the protected operation.
Exact Git acquisition remains a trusted port; no live checkout/GitHub adapter is
included. V2 implements content preservation in the production core rather than
accepting an adapter's opaque claim that a workspace is sealed.

## V2 protected source seal and two contexts

The core reads the acquired `demo-api` tree before application execution and
retains its bytes in an immutable tuple private to the supervisor. A deterministic
SHA-256 seal binds repository, full commit, canonical root `demo-api`, sorted
normalized relative paths, directory/file type, normalized regular-file mode
(0644/0755), and each file's SHA-256. It contains no absolute paths, timestamps,
temporary names or file contents. The private bytes and seal are not copied into
public errors, manifests or WP3A evidence.

This covers the complete committed Docker context, including Dockerfile,
`.dockerignore`, application/probe source, project/solution files, configuration,
and committed scripts/metadata. Required Docker/project/solution inputs must exist.
The current [Dockerfile](../../demo-api/Dockerfile) copies the project/source and
runs its own restore and publish; it does not consume earlier test/build outputs.
The [.dockerignore](../../demo-api/.dockerignore) excludes bin/obj. Initial exports
containing bin/obj or Git metadata fail closed instead of adopting generated data
as source. Limits are 10,000 nodes, 16 MiB per file and 64 MiB total retained bytes.

The core creates two distinct contexts in a private per-invocation temporary root:

- **Mutable execution workspace:** materialized from retained source bytes, then
  used for fixed restore/build/test commands. After every stage, including an
  exceptional execution outcome, the core rereads every sealed node and requires
  equal type, mode and bytes. Changes, deletion or replacement stop the attempt
  before image construction with `SOURCE_INTEGRITY_VIOLATION`. A successful process
  exit does not override a failed integrity check.
- **Protected image context:** freshly materialized from the retained bytes after
  tests, never copied from the mutable workspace. The core enumerates the entire
  materialized tree and recomputes the seal before calling image_build. The builder
  receives this context and its fixed Dockerfile, not the execution workspace.
  A second full verification after the builder returns prevents publication if
  the builder left altered context content.

Additional generated files in the execution workspace (bin/obj, extra source,
fake manifests/probe helpers, alternate generated Dockerfiles) are permitted when
they do not replace sealed nodes. They are never included in the retained snapshot
or image context. An extra file in the protected image context changes its seal
and rejects before image construction. There is no generated-image-input exception.

Symlinks, Windows reparse points/junctions, regular-file hardlinks, special nodes,
case-colliding names, absolute/traversal paths, alternate data streams and unsafe
portable path aliases are rejected for sealed inputs. Every component is checked
with lstat before reading; O_NOFOLLOW is additionally used where available.
No unvalidated link is intentionally followed. An application-created extra link
is not an image input; replacing a sealed node or ancestor with a link rejects.

These are executable offline filesystem/content controls, not proof of OS-level
immutability. The host must protect the supervisor's memory/acquisition/image
roots from payload access and quiesce all payload descendants before returning
from a stage. Container/process isolation and protection against concurrent hostile
host access remain separately UNVERIFIED; WP3C is not implemented by these tests.

Each application invocation receives a complete fixed environment, not an overlay
on `os.environ`. Only fixed PATH, private HOME/cache locations, .NET settings and
metadata-disable configuration are supplied; probes receive three fixed timeout
settings. Credential canaries test enumeration, known-name reads and copying the
supplied environment into simulated logs/artifacts. No supervisor environment is
serialized into evidence or public diagnostics.

This demonstrates the environment-construction boundary with offline process
doubles. It does **not** prove OS/container isolation. A future trusted adapter
must isolate filesystem, processes, sockets, credential files and metadata
endpoints; provide private per-attempt HOME/cache mounts; prevent source/image
handle substitution; and keep publication capabilities outside payload execution.
These obligations are explicit port contracts, not claimed live enforcement.

## Fixed pipeline and observations

Commands derive from [CI](../../.github/workflows/ci-dotnet.yml):

1. `dotnet restore ./demo-api/terragrunt-demo.sln`
2. `dotnet build ./demo-api/terragrunt-demo.sln --configuration Release --no-restore`
3. `dotnet test ./demo-api/terragrunt-demo.sln --configuration Release --no-build --verbosity normal`
4. Materialize and verify the separate protected image context; build using its
   `demo-api` and `demo-api/Dockerfile`, then reverify before publication.
5. Publish the sealed image handle to the neutral application repository and
   obtain the trusted immutable digest receipt.
6. Generate and publish canonical candidate bytes; confirm the returned exact
   version, readback bytes and transport checksum.
7. Run `readiness-probe --check-capability` and the no-server `readiness-probe`
   against that published registry/repository/digest, never a tag or local rebuild.
8. Publish and confirm the protected WP3A supervised result.

Manifest publication precedes probes so late probe failures can retain exact
artifact identity as required by the owner decision. CI cache mechanics and the
separate repository readiness-contract test job are not additional qualification
checks. The seven WP3A checks remain unchanged.

Trusted execution observations contain stage, explicit execution state, bounded
exit code and capability-marker verification. The capability probe requires exit
zero and trusted wrapper verification of the exact capability marker. The
no-server check requires normal exit 1; exit zero, configuration/launch failure
and outer timeout cannot pass. The production probe defines these outcomes.
Arbitrary stdout, stderr, generated JSON and logs are never parsed as stage facts.
The fixed wrapper's observation is trusted; intentionally approved malicious
application source faking its own tests is outside the bounded plan guarantee.

All checks start NOT_RUN. A completed unsuccessful stage becomes FAIL; skipped
and unknown results remain non-PASS. A failed prerequisite stops later execution.
Unexpected adapter failures use fixed public diagnostics without exception text.
No path calls the qualification finalizer or writes eligibility.

V2 terminal validation uses one closed completed-prefix table. Source failure
requires seven NOT_RUN checks and absent observed source. Restore/build/test/
image-build/image-publication failures require every prerequisite PASS, the current
check non-PASS, and every later check NOT_RUN. `image_context` failure allows only
restore/build/test PASS. Manifest write/readback failure requires the first five
checks PASS with both probes NOT_RUN. `result_publish` failure permits all seven
PASS, or a non-PASS probe followed only by NOT_RUN. Non-source terminal stages
require the verified observed source. Probe failures themselves continue to use
the unchanged failed WP3A supervised envelope, never terminal substitution.

## Publication and retry

The image port can only add content to the approved neutral application repository.
It has no policy, lifecycle, delete, KMS or IAM administration capability. Its
receipt binds attempt, sealed handle, registry, repository and SHA-256 digest.
Application-supplied digest strings and tag-only receipts do not establish identity.

Candidate manifests use the existing closed release-manifest shape. Protected
context supplies non-authoritative GitHub run metadata and a stable timestamp;
source and image fields derive from verified observations. The protected operation
and build identity are bound by the supervised result rather than new legacy
manifest fields. No optimistic helper defaults supply check outcomes.

The key retains `releases/demo-api/by-digest/sha256-<digest>.json`. The manifest
port binds the stable attempt to exact intended bytes and its original write
receipt. It must return that same receipt on retry, reject conflicting replacement,
and never adopt latest. Exact-version readback confirms echoed identity, bytes and
checksum. No write-only acknowledgement constitutes established manifest identity.

Both result types share one immutable attempt slot keyed by operation/build.
Conditional create plus exact read confirmation prevents conflicting terminal and
supervised replacements. Exact persisted retry returns the original record without
rerunning the build. A failed attempt is not resumed under the same build identity;
a new protected build identity is needed for another execution.

Before final record publication, payload/image/manifest retries must obey their
documented stable-attempt contracts. An adapter unable to establish those facts
fails rather than claiming idempotency. No distributed workflow engine is added.
After ambiguous result acknowledgement, an exact read may confirm the committed
result. Otherwise terminal publication is attempted in the same slot. Conflicting
or unverifiable persistence fails closed; an in-memory result alone is never
reported as published. Terminal-store failure returns only a redacted error.

## Executable packages and controller runtime

The existing [WP2 bundle codec](../../scripts/tests/security_root/bundles.py) now
includes allowlisted executable files for `build/release` and
`qualification-finalizer/qualification`. Other classes retain their prior bytes
and semantics. Artifacts remain canonical content-addressed JSON envelopes, with
base64 UTF-8/LF source files, fixed host entrypoints and Python >=3.10 stdlib-only
runtime metadata. No tar/zip timestamp, temporary file, absolute local path,
credential or development state is admitted.

The [entrypoint](../../scripts/build_supervision/entrypoint.py) is callable by the
protected host with authenticated adapters. Direct CLI execution fails closed.
There is no dynamic plugin selector or ambient-credential bootstrap. Tests decode
the exact package files into a disposable tree and execute its build entrypoint.
The finalizer's packaged code/schema bytes remain accepted WP3A bytes.

A minimal authority projection contains only protected project/repository/bucket
names, avoiding circular inclusion of bundle digests in their own content. Its
values derive from canonical authority and are covered by package digest. The
existing installer still requires admin publication, actual returned VersionId
and exact readback. Executable content changes require new content identity and
consumer references; no live installed version is invented.

Controller runtime image and application image are separate trust domains.
The build controller requires an ADMIN_VERIFIED, SECURITY_ROOT_OWNED image for
`build/release` at the account/region `e1-controller-build` repository pinned by
full SHA-256. Application publication cannot select that runtime. Canonical live
runtime identity remains unavailable (`null`, UNVERIFIED); tests alone use
synthetic digests. The existing WP2 compute template remains fail-closed and does
not consume executable packages until later reviewed WP3C integration.

## Validation and deferred work

Run `python -I -B scripts/tests/build_supervision/run.py --report <temporary-path>`
alongside the accepted WP1–WP3A suites. Tests exercise success, every stage's
failure, early/late envelope choice, canaries, immutable publication, conflict and
retry, package determinism, package execution and separate WP3A compatibility.
Mutation reports distinguish reached behavioral failures, redundant guards and
invalid harness controls; unchanged source must survive.

V2 adds real disposable filesystem attacks against source/Dockerfile/project/probe
files after each dotnet stage, deletion/type changes, outside symlinks, extra image
inputs, and context corruption. A positive generated-output trace preserves the
sealed image bytes and qualifies through unchanged WP3A. Regression mutations
exercise mutable-context substitution, removed post-stage verification, removed
image-context comparison, unsafe link following, extra-input admission and terminal
prefix checks. Setup/import failures are never behavioral detections.

WP2 remains 18 nodes, empty gateway/project instance maps, creation_supported=false
and operational=false. All 11 request identities and 18 execution identities stay
deny-only with no trust Allow. All eight recovery reservations remain inactive.
No Lambda, CodeBuild, StartBuild, service trust, positive runtime IAM, request
invocation, status API, delivery, lifecycle, recovery or legacy cutover is added.

Git Bash: FAILED / UNRESOLVED cleanup issue. Supported Linux: UNVALIDATED.
Provider-backed Terraform and live backend/bootstrap: UNVERIFIED. Live migration
and bundle installation: UNVERIFIED / NOT PERFORMED. Live controller compute:
UNVERIFIED / NOT DEPLOYED. Live qualification, build supervision and image
publication: UNVERIFIED / NOT PERFORMED. WP3C activation is deferred.
