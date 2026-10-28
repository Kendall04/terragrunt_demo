# Catalog closure and installation prerequisites — 2026-10-25

Update: [completed checker, I/O diagnosis and Windows provider-hash identity](CHECKER-RESULT-AND-PROVIDER-ORIGIN.md). Full checker completed:29 cases,1 failure,3 errors; no global PASS. The earlier pending-session checkpoint below is historical.

Local continuation from paused WIP `7cd596f`; no AWS, SSM, deployment, teardown,
permission installation, push or image rebuild. The owner reports manual resource
deletions; historical inventories therefore cannot establish current existence.
EKS is a separate worker's scope and is untouched.

## Closed local source scope

The [supplemental catalog](../../../ci/authority/target/supplemental-iac.json) pins
exactly eleven already tracked IaC paths with LF-normalized SHA256 and introducing/
last-change Git commits. Its hash is pinned in the existing source model:
`806ae4b34467dd3f558bd1890192ec29bd301dd9b65577393be86cb27d3ba0ab`.

| Source group | Files | Disposition |
| --- | ---: | --- |
| `operations/integrations/ssm-diagnostic/review/{bootstrap,runtime}` | 4 | Closed d1 review templates/locks, fourteen resources historically retired; no replay authority or proof of SSM success |
| `operations/sql-backup/recovery/provider.lock.hcl` | 1 | AWS5.100.0 input to explicit recovery plans, not a selectable root or provider upgrade |
| `terraform/infra/sentinel-backup` and `terraform/live/sentinel-backup` | 6 | Existing separate admin-owned root, pipeline, disabled optional observer, fixed wrapper, mock-plan test and AWS6.27 lock; not part of ordinary TARGET selection |

These files were introduced in `7a2499c`, `df32f1d`, `ca919a7`, `4d6e229` and
`bcac19f`; the current Sentinel source refinements are recorded at `2c8c3e7`.
The underlying eleven files were not edited. Classifying them neither imports them
into E16/WP5 packages nor authorizes their backend bootstrap, IAM or deployment.
`execution_authorized=false` remains mandatory.

The source discovery algorithm is unchanged: no folder/prefix wildcard was added.
Eight focused tests PASS: real repository exact-set coverage; no TARGET expansion;
extra root and nested auto-tfvars rejection; known source/provider-byte mutation;
missing source; catalog self-approval/hash/path tampering; CRLF-only normalization;
and symlink rejection **before following source bytes**. These are local source
admission checks, not a claim about AWS permissions.

Structural source coverage reconciled 127 exact paths against Git history/current
task changes: 98 additions and29 refreshes, zero removed entries, zero remaining
inventory discrepancies. Every refreshed/new semantic disposition is `UNVERIFIED`.
This does not automatically approve code semantics, governance or runtime behavior.
The prior-source inventory and review delta are preserved in Git/task evidence.

## Earlier retained blocker - resolved by the later authenticated closure

The generated provider lock differs from retained HEAD locks for DEV
`global`, `data`, `platform`, `apps`, `edge`. Each retained lock has the additional
`h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs=` checksum for AWS5.100.0.
The generator has `h1:edXOJWE4ORX8Fm+dpVpICzMZJat4AX0VRCAy/xkcOc0=` and the official
ZIP-hash list but not that additional platform-package hash.

Authentic provenance for the extra h1 is still unproved. No checksum was removed,
approved, added to an exception or normalized to make the full checker green. No
provider binary was downloaded/executed and no Terraform init was run. The existing
byte comparison must continue to fail until the package provenance is established
or a separately reviewed lock update has adequate evidence. A pinned catalog is
not a replacement for provider provenance. Full checker started in WSL as session67523/PID519. At the checkpoint it was still
active after8m22s, waiting on p9_client_rpc (Windows-mounted filesystem I/O).
Its log has the eight catalog cases passing, but no final report yet; it was
neither restarted nor interrupted. The focused catalog PASS does not imply full
foundation acceptance. Collect final-checker.json/log before declaring its result.

## Local checker closure update - 2026-10-25

The earlier lock/reader paragraphs above are historical checkpoints. Independent
signed ZIP verification now proves the Windows h1. The fixed generator preserves
all five DEV runtime locks; no lock was edited or platform checksum discarded.
A later stale bootstrap pin was reconciled against exact reviewed commit5110f5c.
The full local foundation checker now passes36/36 with no admission discrepancies;
all219 support pins pass. The old historical UNKNOWN was caused by two later d1
review snapshots, isolated only in the disposable pre-E1 view with exact hashes.
CURRENT still sees them, and unknown/drift negatives remain enforced.
See [final result, origin and limitations](CHECKER-RESULT-AND-PROVIDER-ORIGIN.md).

No new approvals or installations were emitted. Four inactive DEV package hashes
were refreshed; release/deploy approvals remain empty. The source catalog alone
does not authorize publication, IAM, state access, SSM or deployment. The generator
now deliberately consumes the already cataloged lock as a fixed package input;
this is not a general permission to import supplemental roots.

## Fresh installation request — DRAFT, not ready to approve/apply

No approval record is emitted. Previous `release` and `deploy-dev` approvals remain
invalidated/empty; their historical originals remain intact. In particular, do not
copy old G1–G9 flags, renew timestamps or label an old source hash APPROVED.

Before presenting one concrete installation decision:

1. Local provenance/source-checker gate is complete as recorded above. Preserve
   that receipt and strict comparison; do not rerun completed builds or generate
   approval records from this local PASS.
2. Reconcile actual retained/deleted resources with current authorized read-only
   identity, state ownership, backend, roles, installed image/bundle versions and
   current GitHub governance/OIDC. None was re-read in this local task. Do not
   reconstruct manually deleted resources from historical state without review.
3. Bind the exact reviewed source revision and fresh governance verification to
   new request approvals using the existing installation mechanism. Keep V1 default;
   opt-in V2 applies only to protected `normal-delivery/deploy-dev`. The local source
   catalog does not give the requester control of that selection.
4. Publish/verify through existing owners only after approval: local Python
   controller image `sha256:48b67dff2fb9b936975b73adfb15957522519f49928f9a34f68a5182a10fbba8`
   and local API image `sha256:c8a59d8dc9f9f8dcc7cc624f803817f49dafcdf40ec4a538474211de4c8911f9`.
   Actual ECR digests/version IDs must come from readback. Local smoke is not hosted
   release qualification; API source inputs are pinned by `demo-api/deploy/local-image-qualification.json`.
5. Qualify a new recovery host package from current changed helper sources using
   the existing package path; do not reuse an older sealed tar as if it contained
   the new connection-version/backup/private-listener helpers. No duplicate large
   artifact was assembled here.
6. Review the existing integrated plan's current IDs/access/lifecycle and costs
   together. The proposed102-address/USD6 scenario is still unapproved, and prior
   budgets are closed. Secret-version retention, current IAM policy-version slots,
   exact backend deltas and regional read/mapping exposure remain material.

SSM remains unresolved. No RunCommand retry, alternate document/principal/transport,
Session Manager, reboot or new diagnostic is authorized. API stays simple, PKI stays
out, Sentinel stays a platform integration with final Terraform/Terragrunt ownership.
No current AWS absence or full ECS E2E acceptance is asserted.
