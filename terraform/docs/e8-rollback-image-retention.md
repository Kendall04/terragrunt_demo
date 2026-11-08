# E8 — rollback image retention (partial)

CURRENT repository contract; AWS has never been deployed. This increment removes
the configured application-image expiration hazard and tightens the existing
availability observation. Bounded retention, cleanup and live rollback proof
remain unresolved. E1 already resolved overwriteable manifests; it is unchanged.

## Reproduced risk and authoritative ownership

At initial revision `8ccc7c4edf56467403d6942eb0745f31ba546935`, the active
[ownership generator](../../scripts/tests/security_root/ownership.py) emitted one
priority-1 `expire` rule per protected repository: `tagStatus=any`,
`countType=imageCountMoreThan`, `countNumber=15`. The
[captured generated structures](../../scripts/tests/retention/baseline-policy.json)
and [deterministic tests](../../scripts/tests/retention/test_retention.py) preserve
that evidence. This is an offline risk reproduction, not an ECR preview result.

The neutral security root owns `demo-dev-shared-demo-ms`,
`demo-prod-shared-demo-ms` and `demo-shared-demo-ms`. Accepted WP3 publishes only
to `demo-shared-demo-ms`; dev and prod consume that neutral repository and may
reference the same digest. The environment repositories are protected declarations,
not evidence of environment-specific publication. Both TARGET shared modules
consume protected publications; neither declares a competing repository/policy.
Retired WP7 archives preserve provenance and are not active policy sources.

[WP3 publication](../../scripts/internal_release/publisher.py) validates a single
Linux/amd64 OCI image and publishes its content-addressed manifest without
`imageTag`. Qualified images are therefore **untagged**. Qualification binds
source, repository and digest to exact protected S3 manifest bucket/key, VersionId
and byte checksum. Task URIs use the installed account/region and exact repository
`@sha256:...`. S3 evidence survival does not establish ECR availability, and
immutable tag configuration does not prevent image deletion.

Representative scenario: D0 remains deployed in prod and eligible for dev rollback
(or required by a held operation). Fifteen newer distinct images are pushed to
the neutral repository. D0 becomes sixteenth by push order and matches expiration
while its exact manifest/receipt survive. One or multiple release/current tags
would not change `any` selection. Later scale-up/recovery can fail to pull D0 even
if an already running task still serves it.

## Retention horizon and guarantees

The [decision register](decisions-and-limitations.md) defines no approved numeric
or time horizon. Accepted normal rollback selects an environment's protected
successful history UUID subject to fresh authorization; it is not restricted to
the most recent prior success. Emergency restoration reserves the successful
inactive color's exact revision while still selected by the observed service.
Narrowing either here would silently revoke existing recovery possibilities.

| Image classification | Repository treatment / recovery meaning |
| --- | --- |
| Qualified release | Retained; qualification alone grants no deployment or rollback |
| Current release, each environment | Retained regardless of age or newer pushes |
| Eligible prior successful rollback | Retained; successful-history validation, current eligibility and independent prod approval still required |
| Active/pending operation | Retained, including candidate and former active dependencies of partially completed delivery |
| UNCERTAIN operation | Retained with all historical/candidate dependencies; E2 holds do not expire by time |
| Emergency reservation | Retained; existing restoration requires the successful inactive-color revision still selected by the service |
| Superseded/revoked release | Retained; this does not prove no shared-environment or held-operation reference |
| Untagged/unreferenced build | Retained too; untagged status does not establish disposability under WP3 |

The implemented repository horizon is **no automatic expiration of any image in
these three repositories**. Generated
[protected resources](../infra/security/modules/protected_resources/main.tf.json)
omit all three ECR lifecycle-policy resources. There is no replacement count, age,
tag-prefix or priority rule; no image becomes automatically eligible for expiration.
This conservative safeguard exceeds the minimal proposed current/prior/operation
set. It is not an owner-approved permanent unbounded storage policy or a promise
of arbitrary historical rollback: missing qualification/history, revoked
eligibility, incompatible schema or failed prod approval still forbids recovery.

AWS [lifecycle evaluation](https://docs.aws.amazon.com/AmazonECR/latest/userguide/LifecyclePolicies.html)
evaluates all rules then applies priority, with smaller numbers first. Count uses
push order and age uses timestamps; neither consults S3/ECS references. Tagged
prefix/pattern lists must all match tags on the image, including multiple-tag
images. An untagged rule selects WP3 qualified images. A high-priority expiration
rule is not a `keep` action; its own threshold can expire protected content.
Repository lifecycle rules cannot reconcile external current/history/journal
references or E2 generations. Omitting expiration avoids a false dynamic-set guarantee.

## Availability and authority

The existing [Facts adapter](../../scripts/wp4d/adapters.py) uses the already
authorized `ecr:DescribeImages` on the installed neutral repository/exact digest.
E8 adds explicit `registryId` and requires one response matching account,
repository and digest, without a continuation token, and explicit `imageStatus=ACTIVE`.
Foreign, missing, incomplete or ambiguous identities and archived/activating/unknown
storage reject; no tag/latest fallback, rebuild or caller-selected
repository is admitted. Timeout, access denial and image-not-found exceptions fail
closed through existing authorization. This metadata check is not a layer-download
or real task-pull verification. The current AWS [ImageDetail API](https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_ImageDetail.html)
defines ACTIVE/ARCHIVED/ACTIVATING; an installed SDK that omits this optional field
fails closed until genuine runtime readback demonstrates support. No SDK/toolchain
installation or update is performed by E8.

Normal history rollback and emergency restoration reauthorize through this same
port. Tests prove missing images produce FAILURE before mutation in both
environments, with no success receipt. Mid-delivery loss blocks later steps under
the existing failure classification. Post-switch E4 continuation with missing
availability remains UNCERTAIN with no later mutation/success and its E2 ACTIVE
hold retained. Terminal success/status retries remain historical evidence, not a
statement of current availability.

The read is a snapshot: an administrator, repository deletion or externally
installed policy can remove the image afterward. E2 arbitrates accepted environment
mutations, not ECR administration; registry reads and ECS/ALB writes are not atomic.
Future cleanup needs an explicitly authorized protection/fencing contract to
prevent that race. No IAM read expansion, deletion, registry administration,
PassRole or invocation authority is added. The shared WP4D support edit mechanically
changes all sixteen deterministic package hashes in canonical authority;
installations, runtime approvals, environment bindings and public approvals stay
empty. E1 qualification/exact manifest identity, independent prod approval, E2
mutation guards/cleanup generations and E4 original-owner/deadline constraints remain.

## Cleanup, cost and remaining decision

No cleanup/tag controller, deletion endpoint or always-running service is added.
Untagged disposable images have **no automatic expiration** here. Storage growth
is unbounded, including failed builds, superseded releases and unused environment
repositories. S3 quarantine expiry remains unchanged and does not bound ECR bytes.
Additional retained unique image/layer bytes can increase storage cost; no new
compute service or invented budget is introduced.

Remaining owner decision: limit normal rollback to the most recent prior
successful eligible release (count of successes, not ECR pushes), a time window,
or another explicit history set; define budget and treatment of emergency-selected
revisions and indefinite UNCERTAIN holds. A time window must never discard current
or held-operation dependencies. No time SLA is selected. Count versus time changes
accepted rollback rights and cleanup materially and needs explicit authorization.

Future deletion authority must reconcile exact manifest versions/digests, current
services/routing, eligible history, both environments, active/UNCERTAIN journals
and emergency reservations. Missing/corrupt/unavailable evidence must block deletion.
Stale observations/concurrently issued calls require proven fencing/quiescence;
ordinary E2 head observations alone are insufficient. Age, count, tag absence or
caller-selected digest cannot authorize deletion. Such a controller materially
expands E8 and is deferred.

## Validation and live limits

`python -I -B scripts/tests/retention/run.py` runs 18 focused hermetic tests.
The [E1 gate](../../scripts/tests/final_acceptance/gate.py) includes them as an
additional check, preserving the accepted 983 E1/WP count. Tests inspect actual
generated structures, reproduce the old rule on sixteen images with zero/one/multiple
tags, execute installed fact reads inside normal rollback/emergency/E4 fixtures,
and compare baseline fingerprints to confine protected configuration changes to
policy removal and WP4D package identities. Existing renderer, inventory, packages,
IAM/trust/PassRole, installation, E2/E4 and KDD checks remain required.

Future separately authorized installation must verify actual policies are absent
on all three repositories, including externally installed/inherited policies, then
observe exact ECR identities and real pulls/restoration. Before future lifecycle
cleanup, retain genuine ECR preview results using representative referenced images
and multiple tags. No preview, AWS API, provider initialization, installation,
deletion or deployment occurred here. Provider schemas and live policy/IAM/read/
pull/race behavior remain UNVERIFIED. E8 is PARTIALLY_RESOLVED pending horizon/cleanup
decisions and deployed evidence.

Local validation on 2026-10-12: the final E1 gate returned
`E1_REPOSITORY_ACCEPTANCE_PASS`, with all 983 E1/WP, 41 E2, 28 E4 and 23 E2-R
tests passing, no failures/errors/skips, and AC1–AC16 passing. The additional E8
18-test suite and E13 40-test suite passed. All thirteen gate checks passed,
including exact generation, inventory/parsing, deterministic extracted packages,
provider-free NAT/E2/WP4D/WP5/WP6 expression checks, current KDD links/immutable
approved contracts, Terraform check-only formatting and diff whitespace.
Separately, E7 (8), E11 (33) and E14-B (19) passed. E7's authority fingerprint
was stale at the initial HEAD; it was corrected to that verified baseline while
still excluding only source-derived WP4D/WP5 package hashes. No IAM assertion was
relaxed. The preliminary gate was stopped for concrete fixture/availability
corrections; only the final complete report establishes acceptance.

TFLint/tfsec, ShellCheck and actionlint were unavailable locally; no new lint
success or accepted-debt equivalence is claimed. No dependencies were installed.
The unchanged .NET application suite was not rerun because this increment changes
only protected Python, generated ECR configuration, tests and documentation.
