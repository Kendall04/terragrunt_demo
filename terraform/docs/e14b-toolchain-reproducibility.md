# E14-B infrastructure and CI reproducibility

## Current local checksum disposition - 2026-10-25

The later [authenticated provider closure](../../operations/sql-backup/recovery/CHECKER-RESULT-AND-PROVIDER-ORIGIN.md)
resolved the missing origin proof without deleting DEV's Windows h1 or changing
any lock. The fixed generator preserves the exact reviewed DEV runtime bytes;
four inactive package digests changed, approvals remain empty. The earlier
missing-proof paragraphs below are historical observations.

The offline CI comparison now preserves strict equality of all AWS block content
except that one exact authenticated DEV-only platform line in the five runtime
layers. Its source receipt is hash pinned; arbitrary hash/version/constraint,
receipt or scope changes fail. PROD/shared/TLS selections remain unchanged. The
separate Sentinel6.27 root is recognized by its exact lock hash, with Windows-only
provider qualification kept distinct from fresh Linux validation.

The prior changed-suite checkpoint was31/32: historical caller pins conflicted
with the empty approval registry. The later local caller regeneration resolves
that discrepancy at32/32 without activation; its expanded WP6 historical-fixture
comparison still fails independently (61/62), so no whole-CI PASS is asserted. [Bounded security/pipeline
checkpoint](v2-architecture-pipelines-20261024.md#bounded-securitypipeline-closure-update---2026-10-25)
records that retained gate and source-only scope. No workflow or approval changed.


This bounded improvement starts from `72141a7f666ce058ce4d18eb3c3adc180e521ca4`.
E14 overall remains **PARTIALLY_RESOLVED**. It changes CI input identities and
security-root lock coverage without changing AWS authority, E11 selection,
protected approvals, deployment behavior or E14-A's application Dockerfile.

## Current input identities

The reviewed [CI manifest](../../.github/scripts/ci/toolchain.json) selects these
Linux/amd64 artifacts. Terraform, Terragrunt and actionlint retain their existing
versions. TFLint's implicit upstream latest is frozen at the officially observed
0.64.0; tfsec's latest URL is frozen at the observed 1.28.14. ShellCheck's apt
resolution is replaced with the official 0.11.0 standalone release. This is a
deliberate freeze of formerly moving inputs, not a general toolchain upgrade.

| Tool | Exact version | Verification source |
| --- | --- | --- |
| Terraform | 1.13.4 | HashiCorp versioned SHA256SUMS |
| Terragrunt | 0.93.3 | Official release SHA256SUMS |
| TFLint | 0.64.0 | Official release checksums.txt |
| tfsec | 1.28.14 | Official release checksums.txt |
| actionlint | 1.7.12 | Official release checksums.txt |
| ShellCheck | 0.11.0 | Official GitHub release asset SHA-256 |

On 2026-10-11, official upstream HTTPS manifests/API responses were read to
establish these hashes. All six official artifacts were separately downloaded
into temporary storage as data: their complete SHA-256 values and exact archive
members matched the manifest. No binary was installed system-wide. The verified
actionlint and ShellCheck binaries subsequently ran static checks from disposable
Linux paths; the other four binaries were not executed during artifact verification.
The manifest records exact artifact/evidence URLs and
SHA-256 values. Independent signature verification is not claimed. Future CI
downloads are verified against checked-in hashes, not a freshly downloaded
mutable checksum file. A replacement asset at the same URL fails closed.

The [installer](../../.github/scripts/ci/install-tools.py) accepts only reviewed
tools on Linux/amd64, uses HTTPS-only curl with failure handling, checks the
artifact before reading its exact archive member, and writes executables below
RUNNER_TEMP. It does not initialize providers, call AWS, use sudo or execute the
downloaded tools. CI adds that directory through GITHUB_PATH. Hygiene uses
standalone actionlint, removing its floating Go compiler/transitive build inputs,
and replaces the apt ShellCheck installation.

External actions in CI are fixed to verified upstream commit identities for
checkout v6, setup-dotnet v4, cache v4, setup-buildx v3 and build-push v5. The
already pinned protected checkout v4.2.2 and setup-terraform v3 are retained and
verified against official tag-to-commit metadata. Full commits and upstream tags
are recorded in the manifest; same-repository reusable workflows still use the
tested repository revision. Tokens remain contents:read in validation jobs; exact
event checkouts, untrusted-PR handling, E11 fail-closed selection/results, the
standalone E1 default gate and CD Safety enforcement remain in place.

[global.json](../../global.json) selects SDK 10.0.402 with roll-forward disabled,
matching E14-A's inspected SDK image. App CI installs that exact SDK and rejects
an input differing from the repository contract. Docker Buildx selects 0.37.1,
whose official release existence was verified and which matches E14-A's inspected
tool. Its action-managed download has no repository checksum pin; this narrower
version pin is not classified as a verified artifact download. The application
image manifests were deliberately refreshed by the owner-authorized .NET 10
[migration](validation.md#net-10-lts-local-migration---2026-10-16); the explicit
UID 1654 runtime contract is unchanged.

## Authoritative provider locks

All **14** TARGET environment/layer roots already had tracked provider locks.
They remain unchanged. They select AWS 5.100.0 and TLS 4.3.0; some roots retain the
reviewed TLS superset even where only AWS is required. The separate security root
now has an AWS-only lock, generated by the existing closed-source renderer from
the reviewed AWS block verbatim. It has the same AWS constraint/version/checksums
as the existing locks. No provider was initialized, downloaded or upgraded.

Official HashiCorp versioned provider checksum manifests independently confirm
the existing `zh:` archive identities for linux_amd64 and windows_amd64 for AWS
and TLS. These platform/hash relationships are recorded and statically checked.
The existing `h1:` entry is preserved; this work does not establish its platform
origin or claim new platform installation evidence. No lock belongs in the
Terragrunt security wrapper or child modules: provider selection belongs to the
authoritative Terraform root. Cached/copied locks are not separate authority.

The protected lifecycle already uses `-lockfile=readonly` and an administrator
provided filesystem provider mirror. Future security-root initialization is a
separately authorized admin operation and must also use readonly locks. Provider
schemas, actual mirror contents and platform installation remain unverified.

## Protected build and installation boundary

The existing [controller](../../scripts/internal_release/Controller.Dockerfile)
and [worker](../../scripts/internal_release/Worker.Dockerfile) assembly recipes
consume administrator-reviewed digest-pinned BASE inputs and install no packages.
The controller requires Python/boto3/awslambdaric; worker bases require the fixed
binding's SDK or Docker tools. Repository runtime approvals and installations
remain empty; no genuine base digest, dependency inventory or live readback is
invented. Filling these maps requires separately verified image contents,
immutable digest approval and the existing exact package/version/readback gates.

Deterministic control-bundle bytes, protected source identities, image acceptance
gates and lifecycle package references remain unchanged. The security lock is not
added to ordinary lifecycle bundles and changes no controller package identity.
The 137 retired legacy paths are inert evidence and receive no repairs.

## Intentional future updates

1. Review a concrete compatibility/security reason. Resolve the intended upstream
   tag to its commit through the official repository API, dereferencing annotated
   tags. Inspect the commit and action inputs; update the workflow and manifest
   together. A tag alone cannot become a verified execution identity.
2. For standalone tools, read the official versioned checksum manifest or release
   asset digest. Confirm the exact Linux/amd64 filename/member and SHA-256. Record
   version, artifact URL, evidence URL and verification method together. If no
   trustworthy identity is available, retain the reference and record a limitation;
   do not fabricate a checksum or mark it verified.
3. For providers, first review root constraints and supported platforms. Existing
   TARGET locks are generated from the immutable retired snapshot by WP5. A future
   update needs a new deliberately admitted canonical lock input/generator change,
   reviewed package identities and fixtures; never edit the retired snapshot or
   refresh inventory alone to admit new authority. An authorized provider-lock
   generation in a disposable provider-only root can then use explicit platforms
   and version constraints, without a backend. It is a separate network/download
   operation, not part of the offline gate. Preserve readonly runtime init and
   provision the exact reviewed mirror bytes through security administration.
4. For SDK updates, follow the [E14-A image procedure](e14-container-hardening.md),
   keep the approved .NET 10 LTS family, and update global.json/default/evidence together. Review
   NuGet resolution separately; the current application has no locked restore.
5. Run focused reproducibility/E11 checks and applicable E1, generated wiring,
   package, parsing, format and link checks before committing. Review inventory
   only for the actual changed/new sources; hashes attest freshness, not semantics.
   Follow [validation side-effect guidance](validation.md); no AWS/deployment or
   automatic dependency-update platform is introduced by this procedure.

## Remaining gaps and evidence limits

- GitHub-hosted ubuntu-latest, runner OS/system Python/Git/curl/unzip and jq remain
  runner supplied. Hermetic readiness tests deliberately keep /usr/bin:/bin; their
  environment scrub is unchanged. There is no checksum-pinned jq installation.
- The Buildx plugin's download and default BuildKit container image are not fixed
  to repository artifact hashes. NuGet/transitive resolution has no locked restore.
- The immutable setup-dotnet action selects the requested exact SDK, but its
  bundled installer first downloads a latest-LTS runtime. SDK/runtime archives
  have no repository checksum pins. This behavior was confirmed in the pinned
  action source and is a remaining toolchain input, not a fully verified download.
- Inactive protected plan entries retain the accepted immutable setup-terraform
  action and exact 1.13.4 selection. They do not consume the new CI checksum
  manifest. Their action-managed Terraform download has no repository artifact
  pin; changing that generated protected source requires its own reviewed update.
- `dorny/paths-filter@v4` in cd-scope.yml remains mutable. Its observed upstream
  commit is recorded as **MUTABLE_REFERENCE_RETAINED**, not a verified execution
  pin. That file is an accepted WP6 authority source; updating its protected source
  and approval identities is deferred, preserving this task's bounded contract.
- Actual protected base-image contents, dependencies/provider mirror, installed
  numeric versions, live readback, external GitHub protections and AWS behavior
  remain separate, unverified evidence. All activation maps remain empty.
- Offline fixtures validate recorded relationships and fail-closed handling; they
  cannot independently prove future upstream metadata or arbitrary fabricated
  hashes. Human upstream verification remains required for reviewed updates.

Focused offline entry points:

```text
python -I -B .github/scripts/ci/install-tools.py --check
python -I -B -m unittest discover -s scripts/tests/reproducibility -v
python -I -B -m unittest discover -s .github/scripts/ci/tests -v
```

Local validation completed 19 E14-B fixtures, 33 E11 tests and 8 E7 tests. Native
Ubuntu parsed 27 workflows and checked 32 normalized shell scripts. Verified
actionlint 1.7.12 passed all 27 workflows (including inline ShellCheck), and verified
ShellCheck 0.11.0 passed all 32 hygiene script inputs from disposable LF-normalized
copies. A direct run against Windows CRLF text was environmental failure evidence,
not a Linux CI result. Disposable
normalized CD fixtures passed 91 selector and 38 result/process checks, and all
five Linux process-supervision tests passed. The final E1 run completed all 983
tests (959 regressions and 24 WP7) successfully. Seven static checks passed; WP4D
and WP6 encountered malformed Windows Terraform console output. Individual
provider-free reruns of both passed all cases, structure checks and dev/prod
isolation. That composite report remains FAIL; successful reruns do not rewrite
it. A fresh complete composite confirmation subsequently returned
**E1_REPOSITORY_ACCEPTANCE_PASS**, with all 983 tests and all nine static checks
passing, no failures/errors/skips, complete inventory/parsing and unchanged
inactive activation maps. Its outside-repository report is `e14b-confirmation-acceptance/acceptance.json`
under the local temporary directory. An early control-bundle
fixture type error was corrected
by explicitly checking the text lock, preserving its resource-enforcement checks.

The required SDK 8.0.425 is not installed locally (only SDK 9/10 are available),
so the .NET suite and Docker build were not rerun. Native jq is unavailable;
the jq-dependent CD/readiness suites and full fresh Linux E3 are not claimed.
No SDK, jq or provider was installed to clear these limits. Check-only
Terraform/provider-free validation remains distinct from
provider initialization and AWS/runtime proof.

Potential shared integration paths are `.github/workflows/ci.yml`,
`.github/workflows/ci-terragrunt.yml`, `.github/workflows/ci-repo-hygiene.yml`,
`.github/workflows/ci-dotnet.yml`, `.github/workflows/ci-cd-safety.yml`,
`ci/authority/source-inventory.json`, `scripts/tests/authority/inventory.py`,
`scripts/tests/security_root/model.py`, `scripts/tests/control_bundles/test_wp2b.py`,
`terraform/AGENTS.md`, `terraform/docs/validation.md`,
`terraform/docs/decisions-and-limitations.md` and
`terraform/docs/e14-container-hardening.md`. Review source-inventory freshness
after combining batches; do not overwrite another agent's semantic changes with
this branch's hashes. No other agent branch was merged or cherry-picked here.

Only --check is an offline installer invocation. Invoking it with tool names
downloads and writes executables; no local installation is authorized merely by
this documentation. E14 overall must remain PARTIALLY_RESOLVED while these gaps
remain.


## Native lock provenance follow-up - 2026-10-23

The current DEV/PROD AWS equality failure has one exact cause in global, data,
platform, apps and edge: commit `b1f506329a30c96bd134134ea1d4d1297256becc`
added only `h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs=` to DEV.
Removing that single line in memory makes each AWS block identical to PROD.
Versions 5.100.0, constraints `~> 5.50`, the older h1 and all 15 zh values agree.
The fresh read-only [official versioned manifest](https://releases.hashicorp.com/terraform-provider-aws/5.100.0/terraform-provider-aws_5.100.0_SHA256SUMS)
confirms every existing zh (14 ZIPs plus the release manifest JSON), including
linux_amd64 and windows_amd64. No provider
archive was downloaded or provider/Terraform binary executed in this follow-up.

The original commit's [native repair record](validation.md#native-runtime-provider-lock-repair---2026-10-17)
reports origin-signed multi-platform lock generation and successful Windows
readonly initialization/schema loading. Fresh hashing of the existing two-file
windows_amd64 cache reproduces the added DEV h1 exactly. The calculation follows
[Terraform 1.13.4 PackageHashV1](https://github.com/hashicorp/terraform/blob/v1.13.4/internal/getproviders/hash.go)
and its pinned [Go x/mod 0.25.0 Hash1 implementation](https://github.com/golang/mod/blob/v0.25.0/sumdb/dirhash/hash.go).
This is a content-identity check of existing inert files, not new official-package
or signature verification. The raw lock-completion receipt is absent at its
historically cited C:\CodexDrop path; the inspected cache contains extracted files,
not the original ZIP. These bounded observations do not claim a whole-disk search.

Two concrete dependencies remain before normalizing PROD:

1. Recover the existing authenticated completion receipt or an already available
   official Windows archive matching zh
   `9f8b909d3ec50ade83c8062290378b1ec553edef6a447c56dadc01a99f4eaa93`,
   so its contents can independently bind the h1 to the official package.
   The [HashiCorp lock specification](https://developer.hashicorp.com/terraform/language/files/dependency-lock#new-provider-package-checksums)
   distinguishes archive and content hashes; an extracted cache alone cannot
   recreate the original archive identity.
2. Review a deliberately admitted canonical lock input/generator and exact
   protected package identities. `wp5.configuration` currently derives locks from
   the immutable retired shared lock; editing PROD locks alone would not make its
   generated lifecycle packages reproduce the new bytes. Keep retired sources,
   readonly initialization, exact package admission and validation unchanged until
   that correction is concretely reviewed.

Do not remove DEV's native hash to restore textual equality: that risks the
previously demonstrated Windows-cache verification failure. Do not bypass the
existing equality test or refresh unrelated inventory to manufacture acceptance.
No lock, provider version, generator, protected package or test was changed here.
The two existing lock tests were rerun: platform/version/hash-presence PASS;
DEV/PROD equality FAIL. The remaining 30 source-inventory findings stay scoped.
The external local assessment is `provider-lock-provenance/assessment.json` in the
worker evidence directory, with the official text metadata and per-file hashes.


The final bounded existing-evidence search inspected the ECS migration ZIP's 815
member names, its nine selected evidence entries and existing ECS/toolchain
metadata. No original provider ZIP or lock-completion receipt was found in that
scope. It did not read credentials, unpack more caches or inspect EKS content.
The five generated PROD locks match their current files; the five generated DEV
locks omit the later native h1. All eight currently recorded WP5 package SHA256
identities reproduce exactly. This confirms that copying the h1 into locks alone
would not be a consistent generator/package correction. The local search receipt
is `provider-lock-provenance/bounded-existing-evidence-search.json`, SHA256
`cfba543fb2f6252961bdac7b5a72e356f169083e98e830d10eb6cf2b078740ba`.
The dependent change is stopped pending the stated missing artifact and canonical
review; it was not denied and no mutation has an uncertain outcome. See the
[consolidated ECS checkpoint](v2-local-completion.md#consolidated-acceptance-summary).
