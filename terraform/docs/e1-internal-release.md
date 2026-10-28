# E1 WP3C internal release implementation

WP7 milestone disposition: the stage narrative below records its accepted package.
Legacy overlap is now retired; see [final E1 repository contract](e1-final-acceptance.md).
Installation/governance/live evidence remains unverified and compute stays inactive.

This repository checkpoint implements the human-authorized split trust plane.
It is pending independent review and integration. WP3 is not complete.
The immutable [spec](../../specs/iam-hardening/spec.md) and
[plan](../../specs/iam-hardening/plan.md) are unchanged. The explicit human
decision permits subordinate workers, exact-digest probe image override, and
quarantine exchange without introducing another E1 responsibility.

## Trust and compute

The trusted `e1-controller-release` CodeBuild project is non-privileged,
`NO_SOURCE`, with one fixed command invoking the protected Python runtime.
It does not execute application code, dotnet, Docker, or probes. Three separate
CodeBuild projects run the application-controlled work:

| Worker | Project | Privileged | Fixed observation |
| --- | --- | --- | --- |
| dotnet | e1-controller-release-payload-dotnet | false | PRE_BUILD restore; BUILD build; POST_BUILD test |
| image | e1-controller-release-payload-image | true | BUILD exports OCI and conditionally uploads it |
| probe | e1-controller-release-payload-probe | false | PRE_BUILD capability; BUILD expected no-server failure |

A mapped check contributes PASS only when its exact project/build phase succeeds
and that subordinate build's authoritative terminal status is `SUCCEEDED`.
A later terminal failure, including during FINALIZING, makes earlier successful
worker phases non-PASS for qualification.

The worker service role is `e1-controller-release-payload-exec`. Its complete
positive authority is `logs:CreateLogStream` and `logs:PutLogEvents` in the three
precreated worker log groups. Workers share this low-value logging authority.
Stealing its credentials or owning the image worker's Docker daemon is within
the threat model. It gives no ECR, S3, invocation, IAM, PassRole, deployment,
KMS, secret, or protected-controller authority. Only the exact three projects
in the exact account may assume it. The outer controller has a distinct role
with exact project/account CodeBuild trust. There is no VPC, EFS, shared cache,
Docker endpoint, filesystem, process namespace, IPC, or controller credential
transfer between workers and controller.

The historical WP2 skeleton stays at 18 nodes/identities. The previously
reserved finalizer and status Lambda responsibilities are materialized separately
from that skeleton; they are not silently inserted into its count. A complete
fixture selects four controller implementations (release gateway, release build,
qualification finalizer, neutral status), plus three subordinate projects with
one technical worker role. Other skeleton identities remain deny-only. All 11
request identities and eight recovery reservations remain inert. WP6 owns
external invocation/workflow cutover; WP4+ deployment and lifecycle are absent.

## Source, archive and publication

The trusted source adapter makes two REST metadata reads for the fixed public
repository's exact commit and recursive tree. Application bytes come from
`raw.githubusercontent.com` at that same commit and must match each selected
Git blob SHA-1 before materialization. Only regular 0644/0755 application files
are admitted. There are no Git hooks, submodules, checkout filters, application
processes, inherited files, or branch/latest fallback. No GitHub token is supplied;
the two metadata reads still depend on anonymous REST availability. Rate-limit
and acquisition failures stop without blind retries. The [live DEV delivery
record](deployment.md#real-sourcetransport-qualification-and-distinct-digest-dev-rollback)
separates native acquisition diagnostics from genuine WP3 qualification.
The unchanged WP3B supervisor retains raw source bytes and seals its local
copies. Its restore/build/test and image ports cross the worker boundary.

The controller conditionally creates an attempt-scoped source object and verifies
its returned exact VersionId and bytes. Dotnet and image receive separate
presigned exact-version GET capabilities for fresh copies of approved A.
The image input never comes from the dotnet worker. Workers have no S3 IAM
permissions. The image output capability signs one quarantine key and the
required `If-None-Match: *` header. A conflicting second write fails. URLs are
short-lived delegated capabilities, not controller credentials; they are not
included in protected evidence or sanitized status.

Quarantine bytes are untrusted. After exact worker identity and successful AWS
BUILD/terminal status, the controller obtains output VersionId through S3,
reads that exact version, and computes its checksum. No worker-reported digest,
VersionId, JSON, stdout or log establishes authority. The OCI parser reads data
without extracting or executing it, verifies referenced SHA-256 blobs, bounds
sizes, and rejects links, traversal and unreferenced content. The controller
uploads content through exact-repository ECR APIs, then checks ECR's immutable
manifest digest. Existing layers/images require validated ECR responses; tags
are not authoritative. Repository administration/deletion stays with security
admin, separate from content publication.

This is not a reproducible or hermetic image guarantee: a fully compromised
worker can choose hostile application artifact bytes. The authorized security
claim is that exact A was supplied under the fixed worker contract and the
independently selected output after successful AWS execution was published as D.
The worker cannot forge protected evidence or acquire publication authority.
The unchanged WP3B local seal protects controller-held inputs; it is not remote
filesystem attestation of a compromised worker.

The probe runs D as its exact CodeBuild environment image. The only image
override is the validated neutral repository SHA-256 URI. CodeBuild service
image-pull credentials and an exact probe-project/account ECR policy avoid ECR
credentials in the compromised worker role. Capability and no-server checks map
to separate fixed phases. Application stdout alone never establishes success.

## Protected state and event ordering

The internal release gateway accepts only an approved full source commit. An
admin-owned source-approval record authorizes that repository/commit. It writes
immutable operation intent, starts only the outer controller with a correlation
idempotency token, and persists exact operation/build reverse bindings. The
controller waits boundedly for that binding; no authority-bearing request
overrides are accepted. An interrupted gateway can leave an unbound failed
attempt; it cannot create qualification from it.

Missing-object checks use namespace-restricted `ListObjectsV2` with an exact-key
prefix and `MaxKeys=1`; no controller receives unrestricted bucket listing.
Presigned exchange requests explicitly use SigV4 so the create-only header is
part of the signature. Outer execution is bounded to 60 minutes and each worker
to 15 minutes, with bounded polling and capability expiry.

Only build/release writes attempts and digest manifests. Before exact image and
manifest identity, failure produces terminal non-qualification evidence. After
exact manifest publication/readback, probe failure produces failed supervised
evidence. WP3A rejects both. Only the finalizer writes qualification; eligibility
remains admin-only and unimplemented. Status reads protected operations/results
and returns a bounded state, never logs, URLs, environment or quarantine data.

The exact outer controller completion EventBridge rule wakes the finalizer.
Worker events cannot invoke it. The event is not success evidence. The finalizer
independently calls BatchGetBuilds for the bound outer project/build. Fixed outer
BUILD succeeds only after all seven checks and protected result persistence;
the adapter derives that observation independently of supervised-result checks.
The accepted WP3A finalizer then verifies exact operation, result and manifest.

Protected evidence denies non-admin deletion and enforces conditional writes
and separate writers. Its old generic noncurrent-version expiration is removed.
Quarantine is a separate versioned, encrypted, public-blocked bucket with one-day
current/noncurrent expiry; it is never qualification evidence.

## Packages and installation prerequisites

The accepted build and finalizer bundles remain respectively
`ef9ce1edd5331ea6dccebfa4ea9783c40650fd6b075e87c2ce0f3c6553701ec4` and
`0e34a5cd928e91694083a46aba1291b1526b7c1c47faaed4fe51a4ea60eb8fae`.
Gateway/status executable packages contain exact admitted support sources.
Their class digests and consumer references are in the canonical catalog; other
delivery/lifecycle/recovery packages remain unchanged.

AWS adapters live in the independently pinned immutable runtime support, outside
the accepted build/finalizer package identities. The runtime downloads only its
protected exact bundle key/VersionId, verifies bytes/digest, and retains the
verified installation across warm Lambda invocations. The controller image also
contains accepted core/schema support required by shared adapter imports; the
installed core takes precedence. No payload path is an import/plugin path.

[Controller image recipe](../../scripts/internal_release/Controller.Dockerfile)
and [worker recipe](../../scripts/internal_release/Worker.Dockerfile) assemble
explicit files without dependency installation. Security admin must supply and
review immutable base images: controller Python/boto3/awslambdaric; dotnet worker
Python/.NET SDK 8; image worker Python/Docker/buildx/containerd. Probe runtime must
support the application's sh/dotnet contract. No image was built or published
here. Final approved image digests, support digest, exact installed bundle
VersionIds, and readback/install proof are required before materialization.

Canonical installation/runtime maps are empty and live facts are unavailable.
The module's protected installation/runtime inputs demonstrate the future
admin promotion boundary; the root currently wires canonical empty records.
Wrong/missing consumer, digest, VersionId, readback, publisher, support identity,
runtime repository/digest, or worker binding fails closed. The controller also
requires all three worker runtime approvals. Fixtures do not populate canonical
state and cannot be mistaken for installed evidence.

## Offline evidence and remaining gaps

Run `python -I -B scripts/tests/internal_release/run.py` for hermetic SDK response,
positive split trace, negative authority, topology and mutation controls.
`check_packages.py` checks deterministic identities and executes extracted
gateway/status packages in fresh hermetic processes with SDK doubles.
`evaluate_compute.py` in the same directory runs Terraform console against a
temporary locals-only configuration with no backend/provider. Its canonical
maps are empty; valid fixtures produce four controllers and three workers.
The separate WP3C policy evaluator admits only the emitted literal identity
policy grammar; it does not claim SCP/resource-policy or live AWS evaluation.
Unsupported grammar fails the test. WP1's evaluator and evidence meaning remain
unchanged. Topology mutation detections are structural contract assertions,
reported separately from behavioral adapter mutations and source admission.

Live OS/container isolation, CodeBuild phase behavior, OCI runtime export, image
pulls, AWS adapters and service policies require deployed validation. They have
not been exercised against AWS. Git Bash remains FAILED/UNRESOLVED cleanup;
supported Linux UNVALIDATED; provider-backed Terraform and backend/bootstrap
UNVERIFIED; migration/bundle installation UNVERIFIED/NOT PERFORMED; controller
and worker compute UNVERIFIED/NOT DEPLOYED; qualification, build supervision and
image publication UNVERIFIED/NOT PERFORMED. No provider initialization, state
operation, AWS access, external-settings inspection or remote mutation occurred.
