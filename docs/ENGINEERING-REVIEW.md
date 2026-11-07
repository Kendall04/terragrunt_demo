# ECS V2 engineering review

Source baseline: `24cd87c0a780fe398d46553ee8c539bdd32eafa5`.
Read-only AWS inventory: **7 November 2026, 04:45–04:53 UTC**, account
`341936017254`, region `us-east-1`, authenticated `cnp-cert-admin`.
GitHub settings, source, execution records and logs were examined separately.
This review changes documentation only: no runtime, IAM, workflow, state, journal,
timer, artifact identity or infrastructure operation.

## Assessment

ECS V2 is a defensible **DEV recovery and observability laboratory**, with a
working application and independent public static DEMO. SQL cold recovery and
NAT/backup incident handling have authentic evidence. It is not a production HA
platform, a current automatic main-based CD system or a continuously certified
security baseline. The most useful remaining decisions are merge enforcement,
the single future DEV delivery path, and disposition of security/cost residuals.

## Current inventory and ownership

| Component | Readback | Owner / interpretation |
| --- | --- | --- |
| SQL | `i-010e3bf5edd05d11a`, `10.0.101.160`, us-east-1b, t3a.small running | Native Data owner; one active writer, no permanent recovery EC2 |
| NAT A/B | `i-05f144bae3b8671f0` / `i-00eeff5c609ca9f0f`, t3.micro; both ASGs desired=1, Healthy/InService | Global skeleton + ASG/E13 recovery; separate per-AZ egress |
| ECS | Blue revision 15, desired/running 1/1; green revision 9, 0/0 | Delivery-owned revision/count/traffic; green is a dormant nginx skeleton, not a second qualified V2 app |
| Application image | `sha256:5c4a1108170482089ca832e9ce3102d5f49e3b320675189d7773ddc52deef219` | Digest in active task and readiness sidecar; separate task/execution roles |
| API | `/health/live` and `/ready` HTTP 200 at 04:52 UTC | No POST/GET data enumeration or new functional write in this audit |
| Edge | API `4cjyis8dsa`, four routes with authorization NONE | Existing VPC Link/internal ALB path; not user-authenticated |
| Sentinel | Worker/watchdog/cleanup/NAT schedule enabled each minute; backup schedule every 15 minutes | Independent portable Terraform owner; shared observer Lambda dispatches SQL/NAT paths |
| Delivery control | Release/deploy gateways and delivery cleanup reserved concurrency 0; finalizer 1; three NAT handlers 1 each | Inhibition preserved; no application build/release initiated |
| SQL storage | Three encrypted 30-GiB gp3 volumes; two detached, current root DeleteOnTermination=false | AWS-managed EBS key; retained data requires separate disposition |
| NAT storage | Two 8-GiB roots, **Encrypted=false**, delete on termination | Real residual encryption gap, not a SQL-disk finding |
| Static hosting | CloudFront `E1PKEWJYYS672Q`, enabled/deployed, HTTPS 200 | Independent PAYG stack, private S3/OAC, no API origin; CSP `connect-src 'none'` |

Native state HEADs for global/data/platform/apps/edge/shared were read with
VersionId/ETag; no `.tflock` appeared in the complete runtime prefix listing.
State bodies and secret values were not downloaded. The last authenticated serials
remain dated evidence (Data 17, Sentinel 44, security 71); this audit does **not**
invent a current serial from an S3 HEAD or require an old serial after unrelated work.
No security-root override or ignored lock file was removed from the local checkout.

## Security findings and priorities

Priorities express engineering impact, not unmeasured exploitability. Installed
inline/managed policies, request-role trust and available boundaries were read.
No permission was exercised destructively or broadened. This is not a complete
Organizations SCP/session-policy simulation or a fresh SQL privilege inspection.
SQL permissions/TLS handoff are supported by the actual November trial receipts
and current readiness, not a new administrative database session.

| Priority / classification | Evidence and impact | Appropriate next decision |
| --- | --- | --- |
| High · effective exposure | API routes have `AuthorizationType=NONE`; authorized application path can return decrypted synthetic text and incur KMS/API/SQL cost. CORS/CloudFront do not authenticate it. | Retire the lab endpoint in its window. Require real backend authorization before any public AWS Edition or sensitive data. Public DEMO is independent. |
| High · merge-control gap | Active main/develop ruleset requires PR but no status checks and zero approving reviews. Current CI itself enforces results, but merge policy does not. | Review required `CI Validation` and `CD Safety Validation` checks before changing CI. No rules changed here. |
| High · active image debt | Installed NAT image `8ce1c0ed…` retains a completed October scan with 19 HIGH/24 MEDIUM/9 LOW/1 UNDEFINED. Image worker `1d160fc3…` has 15 CRITICAL/56 HIGH. | Patch/requalify before longer-lived use or another protected image build. No refresh scan or runtime replacement in this audit. |
| Medium · storage protection gap | Both actual NAT root EBS volumes are unencrypted; SQL roots are encrypted with `alias/aws/ebs`. | Encrypt future NAT launch versions through a reviewed replacement. Do not claim every volume uses a CMK. |
| Medium · transit boundary | Public TLS terminates at API Gateway; VPC Link→ALB→task uses SG-restricted HTTP. SQL TLS verifies name/trust with a demo self-signed leaf. | Explicitly accept lab boundary; internal TLS and certificate lifecycle are production work, not proof supplied by perimeter HTTPS. |
| Medium · audit coverage | No CloudTrail trail/event data store returned in this account/region read. Inspected project buckets have no server access logging. | Review needed S3/KMS data-event coverage for a persistent service; event history and Sentinel archives are different audit mechanisms. No organization-wide absence claimed. |
| Medium · database durability | FULL recovery + COPY_ONLY full backups, no transaction-log backup chain. One SQL host and one region. | Define log growth/rotation policy for longer use; no PITR, automatic SQL failover or regional recovery claim. |
| Medium · temporary authority | Backup/Sentinel runtime conditions end 9-Nov 04:00; retirement delta ends 06:00. Some earlier SQL TLS/subnet-recovery grants expired 7-Nov 04:00. | Revalidate exact permissions before a future recovery; installed/running SQL does not imply new recovery is currently authorized or viable. Do not extend automatically. |
| Medium · container hardening debt | Active task has no explicit read-only-root or capability-drop settings. Image recipe uses UID 1654; missing task `user` does not imply root. | Review writable-path needs before enforcing container restrictions. No task change here. |
| Medium · security ownership | DEV/shared historical dependencies and administrative operator privileges remain broader than a production-isolated design. | Keep PROD out of scope; do not treat read access to a small inline delta as the complete effective policy. |
| Low · stale authority clutter | Old expired inline grants remain installed; role SQL still has exact migrator-secret access although the SQL migrator login is disabled. | Inventory/retire only after dependency review; expired Allow is not active permission, and disabled login does not prevent host-level secret retrieval. |
| Low · evidence tooling gap | Continuity export's `backup-observer` filter matches `observationId` (NAT reports); SQL storage receipts use `observation`. | Separate filters in a later small tooling correction. This audit separately paginated SQL logs; it does not equate NAT rows with successful backups. |

Request OIDC trust is restricted to the two historical exact reusable workflow
SHAs, `sts.amazonaws.com`, repository/environment subjects. GitHub environments
also restrict the historical branch. These are useful controls, not proof of a
currently admitted main-based deployment. The [CI/CD review](CI-CD-REVIEW.md)
describes composition and inactive wrappers.

The SQL runtime is separate from migration and host administration: demonstrated
grants are SELECT/INSERT on `dbo.DemoTexts`, SELECT on EF metadata, no db_owner/DDL;
migrator disabled. A host administrator or compromised instance role with secret
read access is a different trust boundary. Secrets remain out of Terraform and
public artifacts. KMS Encrypt/Decrypt prevents plaintext storage, not access by a
compromised authorized application. The full [trust model](V2-TRUST-AND-THREATS.md)
retains these limitations.

### Static analysis and dependencies

The exact current-main CI run re-executed **TFLint 0.64.0: 24 warnings** and
**tfsec 1.28.14: 46 findings**, matching rule/resource/message/source hashes and
multiplicity. The previously reported 24/46 totals remain reproducible; they are
not 70 independently confirmed vulnerabilities. No suppressions or acceptance
baseline edits were made.

| Family | Count | Interpretation |
| --- | ---: | --- |
| TFLint required_version / required_provider | 7 / 2 | Child-module declarations; owners/locks already pin versions |
| TFLint unused declarations / deprecated index | 14 / 1 | Maintainability, not an authorization vulnerability |
| tfsec S3 encryption / CMK / logging / versioning | 7 each | Generated JSON relationships can defeat static resolution. Actual SSE-S3/versioning contradict missing-encryption/versioning interpretations; CMK control and missing object-access audit are genuine distinctions. |
| tfsec ECR scanning | 18 | Installed repositories inspected have scanOnPush=true; not every source declaration is deployed. Scan configuration alone says nothing about findings. |

[The full existing classification](V2-STATIC-FINDINGS-20261105.json) retains all
70 entries. [check-static-findings.py](../.github/scripts/ci/check-static-findings.py)
accepts only that exact debt; even removing findings requires separate baseline
review. No scanner-only remediation was attempted. The Windows TFLint on PATH is
0.60.0, so it was not represented as the pinned 0.64.0 reproduction; the authentic
CI logs provide that run and the documentation PR repeats the unchanged checks.

The active application digest's existing ECR scan is COMPLETE with zero findings,
dated **5-Nov 23:50 UTC**. It was read, not restarted. This is not a new vulnerability
scan or a platform-wide clean bill. Auxiliary image counts retain their actual scan
dates. A fresh four-project locked restore and `dotnet list ... package --vulnerable
--include-transitive --format json --no-restore`, using the existing Linux SDK
10.0.402 runtime, reported no vulnerable packages from the NuGet feed. The clean
tracked-source export, SDK output and JSON result are retained privately. This
checks known feed advisories, not every container OS package or unknown vulnerability.
No dependency or lockfile was changed. No organization-wide secret
or full-history vulnerability certification is claimed by a documentation diff scan.

## Recovery and resilience

| Capability | Demonstrated guarantee | Explicit limit / evidence |
| --- | --- | --- |
| Cold CROSS-AZ | A→B, new EC2, source fence/termination, exact backup restore, CHECKDB, schema/data identity and API/KMS; **41m31.5s** full RTO | Includes reconciled failures; supervised planned cutover, not first-pass unattended failover. [Execution](V2-RECOVERY-SECURITY-20261105.md#cold-recovery-execution--6-november-utc). |
| Cold SAME-AZ | New B host, same integrity/application checks, reboot + producer persistence; **24m42.6s** | Corrected trial without corrective replay. No permanent second database. |
| Writer fencing | Drain actual ECS tasks/sessions; disable logins; READ_ONLY; verify exact old EC2 terminated before activation | Unreachable/stopped is insufficient. An old retained disk is stale after new writes; no automatic rollback. [Runbook](../operations/sql-backup/recovery/NATIVE-RECOVERY.md). |
| RPO | Hourly objective plus backup/upload time; final fenced backups preserved synthetic rows in planned trials | Final planned backup is not zero disaster RPO. No abrupt-loss/PITR/region-loss experiment. |
| Backup integrity | CHECKSUM/VERIFYONLY, full SHA256/size/version/CMK manifest; restored copies CHECKDB and data identity | Object hash/VERIFYONLY alone is not a current restore test. |
| Retention | Exact new prefix, verified pair tags, seven-day current expiration, one-day noncurrent expiration, marker cleanup and incomplete-upload abort | Asynchronous Lifecycle, not exact seven-day physical erasure. Protect newest two pairs; orphan/ambiguous/old-enrollment cases fail closed. Historical rules preserved. |
| Restore holds | Stage an independent verified version pair outside Lifecycle before restore | Manifest/backup expiration is not atomic; removing a tag is not a guaranteed cancellation. A hold protects a selected input, not an infinite retention policy. |
| NAT | ASG/E13 :6 replaced A; EIP/route/SDC and actual private HTTPS recovered in **2m29.191s** | Sampled outage onset; no zero interruption/cross-AZ automatic failover. Two earlier partial detections preserved. |
| Sentinel NAT | Real loss persisted in **59.115s**, resolved in 2m54.414s, one recovery email received | Short outage resolved before escalation; no failure-email claim. One probe-throttling Unknown remains evidence. |
| Sentinel backup | Genuine stale backup detected/escalated/resolved; archived SSE-KMS, SNS and inbox correlated | Producer recovery was a prearmed native experiment timer, not Sentinel remediation. |
| Delivery rollback | V1 distinct-digest A→B→A genuine run history | No V2 main-based blue/green/CD certification inferred. Image rollback does not undo shared SQL schema. |

Seven-day rules are still installed with exact prefix/tag scope, alongside the
three preexisting unrelated rules. Code inspection confirms both newest pairs
are fully verified before admitting older pairs; bad newest evidence does not
fall back silently. S3 versioning is not Object Lock; administrator deletion/key
loss remains outside its guarantee. [AWS Lifecycle semantics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html)
distinguish current expiration (delete marker) from permanent noncurrent deletion.
No object or version was deleted or retagged during this review.

### Automatic monitoring actually observed

The read-only export covers **6-Nov 17:08–7-Nov 04:45 UTC**, after the last
installation and supervised third NAT trial. First/last healthy samples are
**17:08:05.508–04:44:05.529: 11h36m00.021s**. There are **697 healthy watchdog
samples**, no unhealthy samples and no visibility gap over 90s; **1,394 worker
ticks**, 739 Completed/655 BudgetYield, maximum **58/64** requests, zero reported
failed jobs. This is sampled health and durable progress, not zero backlog or
12/24 hours extrapolated into the future.

The latest watchdog read reports complete backlog: **three recent archives**,
zero due checks/effects/failed jobs, oldest due 04:41:56.870. It still verifies
**four historical permanent failures and four compensations**, zero active permanent
failures. The last worker completed two effects with 49 requests. Operations DLQ
has approximately **14** messages; reports queue and reports DLQ zero at readback.
No ReceiveMessage, purge, replay, compensation rewrite or manual worker invocation
occurred. Historical debt remains distinct from current watchdog health.

The shared observer log group contains NAT and SQL reports. Separate complete
SQL pagination found **47 exact-version/hash receipts for 12 hourly backups**,
17:00 through 04:00; the latest data time is 7-Nov 04:00:03.232. The main exporter
instead collected **697 NAT Pass** observations under its misleadingly named
`backup-observer` field. Both are recorded accurately, without counting them as
697 SQL backups. Existing systemd installation/reboot evidence establishes the
producer; this audit read its outputs, not a new host command.

Four inbox receptions supplied externally through ChatGPT/Gmail and the later
directly verified third-NAT resolution remain the [original notification evidence](SENTINEL-CHAOS-20261106.md).
No new email was sent or reread for this audit. CloudWatch alarm emails and SNS
publish acknowledgements are not substitutes for domain/inbox evidence.

## Costs and retirement

One Cost Explorer query, daily UnblendedCost grouped by service, returned:

| UTC day | Account-wide USD | AWS status |
| --- | ---: | --- |
| Nov 1 | 1.149401 | Estimated |
| Nov 2 | 1.153471 | Estimated |
| Nov 3 | 1.163797 | Estimated |
| Nov 4 | 1.695231 | Estimated |
| Nov 5 | 2.366425 | Estimated |
| Nov 6 | 1.797738 | Estimated/incomplete |
| Nov 7 | 0 | Not yet populated; not free operation |

Total returned **USD 9.3260625267**. This includes unrelated/shared account services
(including RDS) and delayed billing. It cannot be subtracted from the laboratory's
USD 20 authorization or attributed entirely to ECS. No per-resource cost allocation
proof or final invoice is available. One Cost Explorer API request itself models
USD 0.01 under [AWS pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
No new infrastructure or scan/build charge was initiated; ordinary read/log/S3
requests fit the existing model contingency.

Keep three separate concepts:

- **Laboratory model:** last recorded approximately USD **14.72/20**, with existing
  compute/network, observability, storage and contingency through its approved window.
  This audit adds roughly USD 0.01 for the cost query, not a new unlimited reserve.
- **Permanent DEMO hosting:** PAYG, separately approved USD **1/month**, model
  USD **0.10–0.20/month** for low traffic. No hard AWS cap. No backend, WAF or paid
  flat-rate subscription; AWS rejected the earlier Free attempt. [Hosting details](../portfolio/product/HOSTING.md).
- **Residual storage/security:** two detached SQL disks ~USD **4.80/month**;
  all three retained 30-GiB gp3 roots ~USD **7.20/month**. S3 current/noncurrent
  versions/holds, ECR shared layers, CMKs, secret versions, logs/alarms and any
  unreleased IPv4/network resources remain additional exposure. Image-size sums
  are not deduplicated ECR billing. No per-ECS key/secret billing attribution is claimed.

The existing closure remains **9-Nov 02:30–04:00 UTC**. Permission expiry is not
shutdown. [The closure checklist](../terraform/docs/portfolio-operations.md) separates
compute/network retirement from protected disks, backups/journal and static hosting.
Old saved Data destroy binaries reference replaced instances and must not be reused.
This audit did not generate or execute a teardown plan.

## Documentation disposition

The tracked inventory contained **129 Markdown files**. Filename/path references
were checked across source, tests, workflow JSON/YAML, manifests and generators.
Six transient documents are removed; a seventh is consolidated to a short link
bridge. Three new entry/review pages replace fragmented narrative. No license,
source receipt, private journal, original diagram or cryptographic approval is deleted.

| Previous document | Disposition / reason |
| --- | --- |
| `docs/HANDOFF-20261027.md` | Removed: superseded session handoff and stale plan/authorization checkpoint; README is the current entry point. |
| `terraform/docs/batch2-integration.md` | Removed: temporary local integration log; validation retains its immutable Git citation. Later CI covers current source. |
| `terraform/docs/final-github-actions-cicd.md` | Removed: prepublication checkpoint superseded by actual V1 runs and this CI audit; deployment retains immutable Git citation. |
| `terraform/docs/case-study.md` | Removed: 851-line narrative duplicates implementation/evidence and contains obsolete state. Exact path remains in historical CI classification only. |
| `terraform/docs/interview-guide.md` | Removed: duplicate talking points; README/atlas/guarantee matrix provide verifiable explanation. CI's old path classification remains untouched. |
| `terraform/docs/ci-cd-target-architecture.md` | Removed: old proposal replaced by one current CI/CD review; historical source citation retained in deployment. Selector compatibility remains. |
| `terraform/docs/v2-architecture-review.md` | Condensed: bridge preserves the frozen local-qualification link; full October proposal is in Git. |
| README, operations guide, architecture/bootstrap/security/decision/validation entries | Updated: distinguish deployed V2, native operation and historical/default contracts; repair false pending/no-hosting/disposable-SQL claims. |
| Agent maps and backup/portable READMEs | Updated: prevent new work starting from obsolete installation or recovery status. |
| V1 execution records, dated V2 trials, Sentinel incidents, static finding classification | Preserved: genuine measurements/failures and immutable evidence references. |
| E1/E2/E13/E15/E16 contracts, `specs/`, `ci/authority/` | Preserved: approval hashes, acceptance `DOCUMENTS`, generators, ownership and security dependencies. Removing them would require the forbidden CI/control redesign. |
| Atlas originals, generation/traceability manifests, local qualification manifests | Preserved: exact historical provenance, including snapshots that intentionally describe earlier commits. No hash refreshed to disguise a change. |

Removed prose is recoverable at
[baseline source](https://github.com/Kendall04/terragrunt_demo/tree/24cd87c0a780fe398d46553ee8c539bdd32eafa5).
Private `documents.private.json` records each original path, line count and incoming
text/code references. The old `v2-local-completion.md` and October pipeline design
remain historical because manifests/diagram links depend on them; no bulk move
breaks those paths. The immutable specifications remain byte-identical.

## Verification and evidence trail

Private evidence directory: `repository-review-20261107-01` under the existing
Codex evidence root. It holds AWS inventory/policies/state HEADs, API status headers,
complete SQL/continuity exports, GitHub workflow/settings/run logs, document
reference inventory and validation outputs. Raw policies/logs are not copied into
the public repository. Public claims above identify the relevant code, dates,
counts and immutable source; they do not expose secret values or raw SQL rows.

The source audit read the actual .NET startup/permission/KMS path, Data/native
fencing helpers, retention admission, portable observer/worker contracts, source
selectors and hosting manifests. It used current readbacks where available and
labelled older proofs explicitly. No SSM command, secret-value read, application
POST, new Lambda invocation or experiment was needed.

Local checks: immutable-contract/documentation gate PASS; **41 CI selector/lock
tests PASS**; **35 portfolio tests PASS** on the existing Linux Node 22 image,
with external networking disabled. Two Windows runs encountered loopback
`ECONNRESET` on varying HTTP cases; their failure logs remain preserved, and no
assertion or timeout was relaxed. Linux and CI provide the controlled comparison.
The link audit covers 126 Markdown files and 1,044 relative links: maintained
documents have no broken links/anchors after the historical PKI anchor is retained.
Thirty stale paths remain inside historical specifications (20 in the two
hash-approved IAM specs, ten in the original readiness implementation plan). They
refer to the pre-native tree. The approved IAM bytes are enforced by acceptance;
the readiness plan is retained with its original accepted design boundary, not
treated as a current file map. Both are excluded from the maintained reading path. No
removed transient document is required by a current local link.

Final local/CI results and integration links are recorded in the PR. Required
checks include documentation links, immutable approved-contract hashes, diagram
pins, portfolio contracts, CI selector tests and unchanged functional CI. New
documentation must not be merged by deleting tests or editing gate expectations.

## Small decision list

**Before presenting:** retain the precise DEV scope and authentic evidence, make
CI checks mandatory for future merges, and preserve a safe closure/retention
decision. Choose a repository-wide license if reuse is intended; none is currently
declared, while Archify/font licenses remain intact. Public static DEMO is suitable
for presentation; the unauthenticated runtime is not a public application product.

**Before another long-lived lab or delivery trial:** patch/requalify active
auxiliary runtimes, encrypt future NAT volumes, reconcile expired recovery grants,
and agree one V2 delivery path. These are targeted changes, not a new control plane.

**Outside the demonstrated DEV scope:** multi-writer SQL HA, PITR, regional/account
disaster guarantees, production identity/authorization, end-to-end internal TLS,
comprehensive audit coverage and production security certification. They should
remain explicit limits rather than a new mandatory portfolio roadmap.
