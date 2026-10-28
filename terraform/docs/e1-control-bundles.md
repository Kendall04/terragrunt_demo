# E1 WP2B — protected control-bundle foundation

WP7 milestone disposition: the stage narrative below records its accepted package.
Legacy overlap is now retired; see [final E1 repository contract](e1-final-acceptance.md).
Installation/governance/live evidence remains unverified and compute stays inactive.

Classification: `E1_WP2B_PROTECTED_CONTROL_BUNDLE_FOUNDATION`.
TARGET repository foundation only. No uploaded bundle, installed controller,
active consumer, verified backend or completed WP2/E1 security is claimed.
Baseline: `dc25593717798c0dce861deadbc24e3510c88668` (accepted WP2A).

## Plan reconciliation

[Plan section 5.1](../../specs/iam-hardening/plan.md#51-entry-and-execution)
requires versioned, hash-checked, admin-published bundles and fixed buildspec,
source, image, role, network and logging. Dependencies belong in a reviewed bundle
or pinned controller image; caller/application caches cannot supply control code.
[Section 6.2](../../specs/iam-hardening/plan.md#62-legitimate-lifecycle-through-protected-terraform-execution)
requires reviewed lifecycle source including modules, locks, user data and helpers,
with an admin-controlled active set. Sections 1 and 8 identify the controller
classes. These decisions authorize this foundation without changing the spec/plan.

WP2B implements one dedicated S3 bundle store. No KMS or ECR resource is needed
for these non-executable reservation artifacts. SSE-S3 protects storage at rest;
SHA-256 verifies content independently of encryption. Future controller images,
dependencies, executable payloads, buildspecs and activation remain uninstalled.
Existing application release artifacts and GitHub diagnostic artifacts do not
become privileged bundle sources. Their workflows are unchanged.

## Canonical catalog and exact identity

The `control_bundles` section of
[authority.json](../infra/security/authority.json) is the sole target catalog.
The inherited top-level WP2A stage still identifies the root foundation; the
extension has its own WP2B stage. Protected ownership categories remain unchanged.
The controller-code and artifact-protection implementation labels now explicitly
describe **bundle foundation only**, not all controller/evidence controls.

Nine classes reserve 26 fixed future consumer bindings:

| Class | Reserved bindings | Future engine |
| --- | --- | --- |
| request-gateway | Nine non-plan request capabilities, with fixed environments | Lambda |
| build | Neutral release | CodeBuild |
| qualification-finalizer | Neutral qualification | Lambda |
| status | Neutral, dev, prod | Lambda |
| environment-lifecycle | Ordinary and high-risk, dev and prod | CodeBuild |
| normal-delivery | Dev deployment and prod promotion, including eligible manifest rollback | CodeBuild |
| emergency-recovery | Dev and prod existing-color recovery | CodeBuild |
| cleanup-recovery | Dev and prod bounded cleanup | Lambda |
| nat-recovery | Dev and prod NAT recovery | Lambda |

These are code/configuration slots, not new public responsibilities or installed
functions/projects. A shared class artifact contains fixed per-consumer bindings;
later separately configured compute must select its binding through admin-owned
configuration, never from a request payload. Classes do not share credentials.

`E1_BUNDLE_JSON_V1` is a deterministic transport envelope, not an executable or
archive format. Each artifact includes class, owner, engine, fixed consumer map,
runtime restrictions, operational=false and a sorted file-to-base64-content map.
Currently the only payload is [NOTICE.txt](../infra/security/bundles/NOTICE.txt),
which states that there is no executable controller. It is not a fake installed
controller or a copy of current privileged scripts.

Encoding is sorted-key JSON, ASCII escapes, compact separators, no NaN, and one
final LF. Source text is UTF-8 with CRLF normalized to LF before packaging;
standalone CR and NUL are rejected. The SHA-256 is over the **exact resulting
artifact bytes**, without normalization during verification. Whitespace changes
in a downloaded artifact therefore fail verification. ZIP timestamps, host paths,
filesystem ordering and file mtimes cannot affect this format.

Logical class name is separate from `sha256:<64 lowercase hex digits>`.
The object key is `bundles/sha256/<digest>.json`. Consumer references carry class,
consumer, digest, key and storage ID. Every reference must match its catalog entry.
Changing source or bound configuration changes the artifact hash and requires a
new identity plus updated admin-reviewed references. Updating only one side fails.
The digest does not include its own field or its derived reference: no hash cycle.

## Protected storage

The root calls only its request-identity module and
[control_bundle_storage](../infra/security/modules/control_bundle_storage/main.tf.json).
Bucket naming is fixed from the canonical prefix plus admin-selected account and
region. There is no caller bucket input, dev/prod include or ordinary root owner.
This bucket is **not** the externally bootstrapped security-state bucket.

Resources are the bucket, versioning, public-access block, bucket-owner-enforced
ownership, SSE-S3 default encryption and bucket policy. Force destroy is false;
prevent_destroy is true. No object, lifecycle expiration, replication, access
point, read grant, IAM role, queue, Lambda or CodeBuild resource is introduced.

The canonical policy denies all S3 access to non-admin principals, denies
non-TLS access, and denies PutObject without `If-None-Match`. S3's create-only
header is `If-None-Match: *`. The contract uses small single PutObject uploads;
multipart/copy is not an admitted installation mechanism. No future reader is
currently granted access. The ARN exception identifies the separately held
administrator; it does not authenticate the caller or grant IAM permission.
Admin credentials and initial policy installation remain external prerequisites.

AWS semantics checked for this slice:
[conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html),
[principal ARN conditions](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalarn).
Versioning alone is not immutability. Create-only writes avoid replacing a current
object; non-admin deletion/policy/versioning/lifecycle changes are denied. The
administrator remains able to intentionally change the protected contract, as
allowed by the spec. No WORM claim against that administrator is made.

## Administrator installation contract

The [offline packager](../../scripts/tests/security_root/pack_bundle.py) validates
repository admission before preparing or verifying an artifact. It has no upload,
approval, extraction or execution capability. Example, with a disposable path:

```text
python -I -B scripts/tests/security_root/pack_bundle.py build --output <temporary-file>
python -I -B scripts/tests/security_root/pack_bundle.py build --verify <temporary-file>
```

It never overwrites an output and refuses output inside the repository. The
installation proposal includes the exact identity, create-only header and content
checksum, and still reports approval/installation UNVERIFIED and activation=false.

A later separately authenticated administrator must:

1. Review the exact immutable repository revision, complete source/configuration
   and dependency closure; record that approval outside requester authority.
2. Prepare and verify the canonical bytes against the reviewed catalog digest.
3. Confirm the separately protected bucket/policy/versioning prerequisites, then
   upload only to the content-addressed key with the create-only header/checksum.
4. Capture the returned non-null S3 VersionId, read **that exact version** back,
   and verify its bytes against the approved digest. S3 ETag is not the digest.
5. Publish the version and exact reference through separately reviewed protected
   configuration. A conflict is not permission to overwrite or silently select
   another version. Changed content requires a new identity and approval.

Those AWS steps are not implemented or executed here. `version_id=null` means
uninstalled, not latest. All active sets are empty. The current resolver returns
only an exact **reservation**; it cannot authorize execution. Installing real
executables, capturing live versions and enabling consumers require a later
reviewed grammar/wiring extension and positive/negative execution evidence.
No CLI option can turn the current reservation into an installed/active record.

## Substitution boundary and evidence

The canonical future runtime contract forbids source/revision/secondary-source,
buildspec, environment-variable, image, command/script, object-key, Terraform/
Terragrunt bundle, role, debug, network, logging, cache and plugin overrides.
No runtime image or buildspec is currently bound. Missing bindings mean execution
is unavailable. Future installed lifecycle revisions may only be chosen from the
admin-controlled active set as required by the plan; arbitrary SHAs are not
approval. Old retained content never implies active eligibility.

[Closed admission](../../scripts/tests/security_root/model.py) now admits exactly
the storage module and notice alongside the WP2A sources. It compares generated
Terraform wiring, validates canonical storage policies/classes/references and
checks actual artifact hashes. Added bucket/KMS/ECR/IAM/policy surfaces, ordinary
duplicates, alternate modules and extra protected-root payloads fail admission;
refreshing the general source inventory cannot admit them. Unknown IaC is rejected,
not interpreted. Later executable payloads need an explicit admission extension.

All eleven request identities retain the original no-Allow trust and deny-all
identity policy. No attachment or resource-policy Allow is added. The legacy
snapshot is unchanged and still excluded from target acceptance. This does not
revoke existing broad CURRENT authority or secure the live account.

Run the dedicated suite with `python -I -B scripts/tests/control_bundles/run.py`.
Its mutations edit disposable copies of production source/wiring and check failure
reasons; positive packaging and explicitly updated content identities prevent
reject-everything success. WP2A's 18 tests retain their assertions; their fixture
copies the newly admitted notice. WP1 code/evidence meaning is unchanged:
CURRENT positive/PARTIAL witnesses and negative completeness only in closed
synthetic universes. Neither suite reverse-engineers bundle Terraform as CURRENT.

Provider-backed validation remains UNVERIFIED/not initialized. Git Bash selector
cleanup remains FAILED/UNRESOLVED; supported Linux remains UNVALIDATED. Live
bootstrap, bucket protection and installation remain UNVERIFIED. No cloud action
or controller execution is performed by these offline tests.

## Subsequent WP2C foundation

[WP2C](e1-controller-compute.md) adds protected compute declarations in a separate
module, with empty Lambda/CodeBuild instance maps and deny-only execution roles.
The no-compute statements above describe WP2B itself. Its nine artifact identities,
26 references, null versions, unverified installation and storage contract remain
unchanged. Reservation resolution is still not invocation authorization.
