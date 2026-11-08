# SQL recovery → ECS service: executable offline cutover plan

Local implementation in the existing `recovery/prepare.py`; no SDK, executor, token acquisition, secret value, infrastructure mutation or traffic switch. This joins existing cold-host receipt metadata to the actual WP4 closed request validator and existing taskdef renderer arguments. A consistent JSON input never authenticates itself or authorizes activation.

## Run now, locally

From repository root, with the existing Python:

```text
python -I -B operations/sql-backup/recovery/prepare.py service-plan --trial r20261024c1t --input operations/sql-backup/recovery/fixtures/service-cutover.synthetic.json
python -I -B -m unittest discover -s operations/sql-backup/recovery -p test_service_plan.py -v
python -I -B scripts/tests/run_recovery_ci.py
```

The fixture is explicitly synthetic: instance IDs, VPC/SGs, versions, hashes, release/history and times. Do not apply its references. The first command prints a concrete ordered plan, exact renderer argument array, validated WP4 deliver/rollback request bodies, role/key review and blocking live gates. It never sends those requests. `AllowsActivation`, `EvidenceAuthenticated`, `FullEcsRecoveryProven` stay false.

The service suite is now explicitly included in the existing CI entrypoint: **12 suites/176 PASS/0SKIP in WSL**, including ten service-contract tests, eight real Bash/jq tests and the thirteen opt-in V2 contract tests and negatives for fencing, identity, backup, public/routing endpoint, schema/rollback and repeated operation identity. This is not hosted CI or SQL/ECS runtime acceptance.

## What is actually checked

- Cold receipt must bind the same target/source and terminated-source fence, correct account/region, new target after recovery request, CHECKDB-readable restore, ordered readiness/fence timestamps and a fresh final observation. Quiescent/stopped SQL or a failed probe alone does not replace source termination.
- SQL must be in the same application VPC, match the target instance ID and private RFC1918 subnet, have no public IPv4 and propose a single private-IP SQL listener. Link-local/metadata addresses, unspecified/broadcast/network endpoints and foreign instance/VPC fail. Only TCP1433 from the exact task SG is admitted in the supplied ingress metadata.
- Connection metadata contains only protected connection-secret ARN, immutable version ID, endpoint/database and key ARNs. Raw Password/connection-string fields fail. It cannot substitute the SA/app-password secret for the connection secret. Existing application-text/connection-secret CMK and separate backup CMK remain distinct; execution role needs only connection-secret/GetSecretValue/decrypt, task role application text Encrypt/Decrypt, SQL role selected S3 backup version/decrypt.
- The release ID identifies a qualification record; the image URI separately fixes a same-account regional digest, and protected qualification must establish their relationship. Restored/candidate/rollback schema fingerprints must agree; rollback/new delivery/history IDs must be distinct valid operations. These fingerprints still need protected release/restore provenance live; caller declarations are not compatibility attestations.
- Routing references must match the current dev ALB and blue/green target conventions. Public URL must match the declared same-region HTTP API ID. Job/controller bindings, real API ownership, VPC route/NACL membership and permission effectiveness still need native readback.

The code calls **`scripts.workflow_requests.contract.request('deploy-dev', ...)`**, using its actual gateway and authorization validators. The public body stays release/history/replicas, never a raw endpoint, secret or arbitrary resource override. Existing pinned repository/ref/OIDC configuration is not changed. WP4 remains the only task revision/count/listener writer; E2 durable operation ownership and unknown-outcome/replay guards remain mandatory.

## Executable references and remaining live work

| Step | Existing executable or output | Actual boundary |
| --- | --- | --- |
| Source fencing + cold restore | `host.py restore --cold-request ...` | Native future readback and authorization required; cannot use a synthetic receipt to turn on writes |
| New connection version | Plan emits ARN/version metadata only | Approved secret writer must create/verify the new version outside Terraform, under the reviewed ownership/transaction. No value writer was added |
| Candidate task JSON | Output `RendererArguments` calls `scripts/render-demo-api-taskdef.sh` | Real Bash/jq 1.8.2 materialization and full local task review PASS for both colors with synthetic metadata. Verified isolated binary, no global install. LF fixture/export used for Windows-mounted source; no fake jq |
| Pin candidate configuration | Exact Secrets Manager version selector `ARN:::VersionId`; explicit `--recovery` renderer profile sets migration-off | The current WP4 V1 source cannot represent the pinned selector/migration-off profile. A new reviewed protected runtime/binding model is required; caller cannot override it. No workflow or installed binding was changed. Fargate Linux platform>=1.4.0 required for version selector |
| Fresh tasks / candidate validation | Existing WP4 flow, `scripts/ecs-readiness-gate.sh` and E3 | New candidate tasks must fetch the reviewed version; existing tasks do not refresh secrets automatically. No direct update-service bypass |
| Controlled traffic switch | Existing WP4/E2-owned transition | Task-local SQL/KMS readiness and final E3 check first. Do not advertise public replacement validation before switching if no candidate public route exists |
| Declare service ready | Plan requires public `/ready`, old-marker decrypt, fresh POST/read and total request→public-ready time | Only after the controlled switch; failed public checks leave service recovery unaccepted. No public HTTP request was made here |
| Rollback | Actual WP4 rollback-release request shape | Compatible old image against the SAME restored DB endpoint/version; never reconnect to the terminated original DB or claim schema rollback |
| Owner review / retirement | Existing approved lifecycle ownership | Future plan must include live viewing window, complete application resources, IAM/budget and retirement. Isolated30-object/USD4 proposal does not include full app reconstruction |

[Official ECS secret projection semantics](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html): secrets are injected at task start and version selectors require Linux platform1.4.0+. Metadata tests do not prove installed platform, permissions or which task used a secret.

### Concrete architecture gaps preserved, not hidden

Current cold bootstrap/runtime verifier is loopback-only. The new local **post-restore application-listener plan/check** selects one exact private IP, requires no-public-IP/task-SG isolation and adapts the fresh query/socket-owner proof. Its native transition and revalidation remain unexecuted. Do not blindly allow0.0.0.0 or claim SQL supports a new multi-address configuration from a metadata field. The dry plan's private address is a proposed mode, not proof current helpers implement it.

Current task template defaults startup migrations. The renderer now implements explicit `--recovery`, requiring a same-account/region immutable secret version, image digest and KMS key ARN, and adds `Database__RunMigrationsOnStartup=false` only to the application container. Normal rendering and the operational template remain unchanged; no installed WP4 binding selects this mode yet. Recovery must not let startup migrations alter the restored schema before compatibility/rollback review. Normal delivery/migration ownership needs a deliberate qualified recovery binding; disabling migrations globally would change unrelated deployment behavior.

Minimum recommended integration: restore into the application's existing private VPC/subnet and reviewed DB SG, update a versioned protected connection reference, create candidate tasks through the installed delivery owner, validate, then switch/verify publicly. No peering, new business service, PKI or alternate deployment controller is introduced. The full saved plan, existing infrastructure availability, bindings, permissions and new cost still require a grouped native admission. SSM's unresolved denial is not bypassed by this local plan.

## Executable local recovery profile and task review - 2026-10-24

The existing renderer supports `--recovery` for the reviewed dev plan. It preserves the readiness sidecar without credentials/environment/ports, pins the same image digest in both containers, and disables application startup migrations. It requires explicit immutable connection-secret version metadata and a same-account/region KMS key ARN. Ordinary rendering retains its previous defaults. This is local task JSON preparation, not a new deployment owner or a caller override to the closed WP4 request.

`prepare.py service-taskdef` validates the **complete** rendered task against the current reviewed template projection and service input. Extra fields, alternate roles, probe privileges/commands/image, plaintext connection environment, missing/true migrations flag or changed secret version are refused. A PASS hashes the candidate and template but keeps `AllowsActivation=false`, `EvidenceAuthenticated=false`, and `PublicApiRecoveryProven=false`. It reads no secret value and does not register, start or route a task. The native installed Fargate platform must still support version selectors (Linux >=1.4.0).

After rendering the synthetic fixture locally with the command array printed by `service-plan` (append `--recovery` is already included in that array), review the output:

```text
python -I -B operations/sql-backup/recovery/prepare.py service-taskdef --trial r20261024c1t --input operations/sql-backup/recovery/fixtures/service-cutover.synthetic.json --evidence candidate-taskdef.review.json
```

Owner-approved standalone Linux AMD64 **jq 1.8.2** is now isolated in the project cache, SHA256 `b1c22172dd303f3be49e935aa56aa48a8b7a46e0bc838b4997d3bb451495870f`, verified against the official release checksum before execution. Its actual version was checked under UID65534. Only the test process PATH includes that cache; no apt, global PATH or WSL service/settings changes. Source: [official release](https://github.com/jqlang/jq/releases/tag/jq-1.8.2). Real renderer tests now materialize both colors, preserve normal defaults, reject invalid inputs before output, and reject rendered template/probe injection through the actual local artifact reviewer. These are real Bash/jq executions with synthetic metadata; AWS is blocked in fixtures. They do not prove secret existence, image eligibility, an installed controller, Fargate or public recovery. A 2.4 KiB review artifact and small qualification manifest are retained locally; no new large recovery archive, upload or deployment. Historical pre-tool qualification remains unchanged.

Public validation is explicitly **after** the WP4-controlled switch: GET `/ready`, GET `/text?page=1&pageSize=100` to decrypt the verified restored marker, one fresh unique synthetic POST `/text`, then GET to compare the same returned marker ID and plaintext. HTTP 200 alone is insufficient. The marker bindings must come from the verified restore receipt and fresh POST result; this input alone cannot authenticate them, and first-page lookup must fail rather than accept a missing marker. Public transport/E3 receipts and whole-request-to-public-ready timing remain unproved.

The recovery bootstrap/restore stays loopback by default. The explicit post-restore private-listener plan/check below now provides exact socket-owner/query and native network comparisons locally; actual transition and native qualification are still required before this task definition can reach recovered SQL. No wildcard listener, new network, role change, SSM retry or host execution was introduced here. A future integrated trial must also select the protected recovery binding, preserve source fencing, admit full IAM/cost/teardown, and reserve a proposed 20-minute owner LIVE viewing window within its budget; notify Kendall before retirement and do not wait indefinitely.

## Explicit post-restore private listener - local contract

The cold bootstrap and all existing source/restore actions retain loopback. No user-data, SQL setting, service, SG, route or IAM policy changed. After a completed cold restore, the existing preparer can produce a **plan only** for the single private listener:

```text
python -I -B operations/sql-backup/recovery/prepare.py listener-plan --trial r20261024c1t --input operations/sql-backup/recovery/fixtures/service-cutover.synthetic.json
```

That synthetic output is not authority or a native fence. It lists the future reviewed sequence (stop SQL, set `network.ipaddress` to the exact reviewed private IP, start SQL) without running it. The source must be positively confirmed terminated before any setting change. The initial restore and CHECKDB stay on loopback; the listener transition follows, before protected Fargate configuration/new tasks. No wildcard/multi-address listener is introduced. If fencing or transition state is uncertain, activation stops; there is no fallback to the original SQL.

Two existing-host entrypoints were added, both inert without `--execute`:

- `host.py listener-network-check`: require `--listener-plan` containing the full service input, including the original cold fence's **SourceLaunchUtc** and TargetLaunchUtc. With separately approved execution/root/identity/directory arguments, compare actual STS instance-role identity, source termination/generation, target generation/profile/Trial, one private-only ENI/IP, exact VPC/subnet CIDR and exact DB/task SG owners. DB ingress must be only TCP1433 from that task SG; public/CIDR/IPv6/extra groups fail. This pre-transition observation needs no secret read or SQL query and authorizes no mutation.
- `host.py listener-check`: independently repeat those network/fence reads, read the existing SA secret **only on the instance**, run a fresh authenticated SQL query to the exact private IP and repeat network/fence comparison. Verify persisted/selected IP, unique kernel listener inode and SQL service executable/owner/start-time binding before/after the query. SQL's logical PID is still separate from the kernel PID. Wrong endpoint, another process, listener replacement, restart or uncertain network fails. No SQL or service setting changes occur in either entrypoint.

Future command admission still requires the normal `--execute --acknowledge TRIAL --expected-instance-id ID --expected-az AZ --directory PRIVATE_DIR` gates, reviewed source hashes/host paths and new explicit cycle/transport authority. These commands were **not** sent through SSM, the console or another principal. Existing b2/d1 denials were not retried. This is no alternate path around them. The preserved synthetic fixture deliberately lacks native SourceLaunchUtc; it cannot be used as native execution input.

The future instance role needs its existing STS identity and SA-secret access plus regional `ec2:DescribeInstances`, `DescribeSubnets`, `DescribeSecurityGroups` for the exact requested IDs. These describe APIs use regional inventory-style authorization and may reveal other metadata if granted; this code installs **no permission** and does not establish current effectiveness. An initial read denial stops before SQL/secret work; a later denial stops acceptance. Neither is retried or moved to another role. Callback/creation/teardown authority remains for the next grouped native plan.

`verify_effective.py` defaults to `127.0.0.1` and retains the original loopback report schema. Private observations add an exact expected endpoint and require an explicit matching private profile when consumed. A private report is rejected by the old loopback gate. Configuration 2048MB, ownership/start-time and before/after checks remain in both modes. Snapshots cannot eliminate all races; they are bounded observations, not a durable exclusive-write lease.

No private SQL process, socket, network or public API was started for these tests. The 11 explicit offline suites cover both legacy and private paths using synthetic kernel/control-plane responses; an actual Microsoft SQL private binding/fresh-query proof is still pending. The current self-signed SQL trust exception (`-C`/TrustServerCertificate) remains a separately known limitation, not PKI integration or a new TLS claim. After the private transition, local SQL tools must target that private IP explicitly; do not rerun old loopback source/restore commands. Fresh Fargate tasks, protected secret/profile binding, E3/public read-write/decrypt receipts and total RTO remain next integration gates.

Configuration reference: [Microsoft mssql-conf](https://learn.microsoft.com/en-us/sql/linux/configure/mssql-conf?view=sql-server-ver16). No configuration command was executed here.

## Actual WP4 boundary found during renderer qualification

The auxiliary Bash renderer prepares review JSON. **WP4A/WP4B remains the only application task/count/routing owner**, and it constructs tasks through `scripts/normal_delivery/authorization.py:runtime` using the closed `ci/authority/normal-delivery-model.json`; it does not consume this arbitrary caller-supplied task JSON. No second controller was added.

The recovery plan previously accepted `demo/dev/db/...` for a connection secret, whereas WP4 V1 admits only the base ARN `demo/dev/app/db-connection-string-XXXXXX`. This mismatch is corrected by extracting/reusing WP4's exact base-ARN validator, with an explicitly synthetic matching fixture. The helper still rejects selectors in the **base ARN** field and leaves V1 acceptance unchanged. The projection appends the immutable version only in the local recovery task. No secret was created, read or modified.

A focused test calls the actual WP4 model validator: the normal task passes; the recovery task with version selector/startup migrations disabled is rejected. **This is an integration blocker, not permission to weaken the existing model or send the currently valid normal-delivery request for recovery.** Twenty existing WP4 authorization regressions also pass after the shared-helper extraction. Caller requests stay closed (`action`, release/history and replicas), with no secret/profile/endpoint override.

The local opt-in V2 implementation is now available for review in [WP4-V2-REVIEW.md](WP4-V2-REVIEW.md), selected only from protected versioned facts: base connection ARN plus exact secret VersionId, immutable model/reference hashes, migrations-off on the app, unchanged credential-free probe and valid Fargate platform. It must bind the same restored target/network/fencing observations, release/schema compatibility and operation ownership; validate membership and rollback against the same recovered DB. It must not silently reinterpret V1, add a caller flag, grant IAM or install settings. Qualifying/publishing that new protected model and running an integrated cycle require their own reviewed scope. The API, PKI exclusion, old receipts and live resources remain unchanged.

Local V2 status: implemented and tested, not selected by the installed factory or deployed. V1 keeps its rules and rejects V2 bindings/authorizers/journals. The new types reuse the existing state machine and its E2/E3 boundaries; they add no IAM or public request fields. Installation/package selection remains a material review gate, and the native receipt/image/profile qualification described in the review is still required. No old trial budget or SSM command was reused.

## Bound API read/write sequence - local correction, 2026-10-27

`host.check_api_recovery(port, source_record, probe)` now implements the existing
four-request acceptance sequence, rather than accepting a successful HTTP response
or matching plaintext alone: dependency readiness; restored marker ID+plaintext
read; one fresh synthetic POST; and a second read containing that exact POST ID
and plaintext. Both reads must retain the restored marker and exclude the known
post-backup marker. Duplicate/malformed IDs, an existing write probe, or a reused
POST ID refuse. An unknown/denied POST is not retried; reconcile the existing host
STARTED marker and outcome before any separately admitted continuation.

The actual restore function now uses this shared sequence. Its existing API context
already performs `/ready`, so it passes `require_ready=False`; the shared function
defaults to checking readiness when used by a separately admitted future public
adapter. It constructs no client, reads no credential and accepts no URL/redirect
override. The caller must bind the transport to the reviewed endpoint and preserve
WP4/E2/E3 ownership. No public adapter, command or alternate SSM transport was added.

Restore receipts now include `ApiRecoveryCheck` with the old/new numeric IDs and
fixed check results, without plaintext. `PublicEndpointAuthenticated` and
`FullEcsRecoveryProven` remain false. Older sealed receipts/artifacts/approvals stay
unchanged; this source must be packaged under a new manifest before approved native
use. It is not evidence that public Fargate recovery has executed.

The original defect was reproduced first: the POST returned ID999 but the read
contained ID2 with the same text, and the old workflow accepted it. The regression
now refuses. Seven additional test methods cover the actual restore wiring,
ordered sequence, missing/contradictory markers, duplicate IDs, readiness failure,
already-present probes and denied/uncertain writes without retries. Final results:
37 recovery cases +3 cold-execution cases on Windows; 4 existing production-main
entrypoint cases in WSL Ubuntu24.04, zero skips. These use real helper/entrypoint
code and transport doubles, never AWS, SQL engine or public traffic. The existing
`run_recovery_ci.py` already discovers `test_recovery.py`, so the added cases enter
the existing hygiene job without a new workflow or hosted run.

Remaining native acceptance is unchanged: authenticated cold fence/restore/private
listener and connection version, protected V2 delivery/routing, public endpoint
proof and full RTO, plus portable Sentinel's durable AWS/notice path. This correction
removes a demonstrated local false-positive; it does not close those gates or solve
SSM authorization. No deployment, teardown, IAM change, installation or budget use.

## Self-contained recovery runtime packaging - 2026-10-27

The existing bundle builder now includes the exact source dependency closure used
by the listener/connection validators: four root helpers/bootstrap and ten explicit
pure WP3/WP4/WP6 validator/model/template files. It includes no approvals, installed
configuration, credentials or SDK/cloud execution adapter. No second deployment
controller is installed by packaging these original source modules.

An extracted-package regression first reproduced `ModuleNotFoundError: scripts`;
after including the lazy gateway/delivery imports, a fresh isolated Python process
can run the actual listener plan without the repository on sys.path. External
effects are denied inside that process. The other new regressions reject a foreign
source commit, changed helper bytes even with a rewritten internal hash, and a
missing dependency even with a self-consistent manifest. Three new cases and two
affected existing bundle cases pass; the prior44 API/cold/POSIX cases are unchanged.
`test_bundle_runtime.py` is explicitly wired into the existing offline CI runner.

Before future publication/installation, use the source-pinned inspection mode:

```text
python operations/sql-backup/recovery/bundle.py inspect --archive RECOVERY.tar --sha256 EXPECTED_ARCHIVE_SHA256 --commit REVIEWED_SOURCE_COMMIT
```

It requires `RECOVERY_HOST_WITH_SERVICE_VALIDATORS_V2`, the exact source commit,
current helper/support bytes (LF/CRLF normalization only), and no unexpected root
support files. Historical two-argument inspection remains available for preserving
old evidence; it is not current-source qualification. The self-reported commit or
an archive hash grants no authority. New binaries retain their actual original build
identity; no rebuild, upload, permission installation or native acceptance is implied.
Old az6/cold locks and sealed tar/ZIP receipts remain historical and unchanged.

## Fixed private-listener transition - local automation, 2026-10-27

The existing host runner now exposes `listener-transition` and the separate
read-only `listener-transition-review`. Both are inert without the existing explicit
execution/acknowledgement/Linux-root/instance-role/expected-host/private-directory
gates. No action was executed on a real host. The earlier three manually sequenced
steps now run as one fixed procedure; no arbitrary command, hostname, port or SG
override was added. A transition also requires the exact reviewed service-input
SHA256 through `--listener-transition-approved-sha256` and a review age0..600s.
That hash binds input consistency, not owner permission or transport authorization.

Order: validate exact native source termination/target/network; authenticate the
existing loopback SQL runtime; record preflight and stop intent; stop the service;
verify inactive/MainPID0/no TCP1433 listener; recheck the same network; record config
intent and set only the reviewed private IP; use the strict original mssql-conf
getter to confirm it while SQL remains stopped; recheck network; record start
intent and start normally; run the existing private socket-owner/fresh-query and
network checks before recording verification. A denied/unknown step, bad config,
changed generation/network or failed final query halts. No retry, compensating
restart/rollback, force-PID action, SG change or fallback to the old database occurs.

Seven append-only private phase files precede/confirm the effects. The original
STARTED marker prevents replay of the CLI action; direct transition calls also
refuse existing phase history. Reconciliation validates history/input/target/network
hashes and uses the existing fresh private-listener observation without mutating
SQL or rewriting the original records. It never declares an unresolved original
operation successful or safe to replay. The normal application activation and
connection-version gates remain separate and `AllowsActivation=false` throughout.
Transport permission and native trial approval are still required; this is not an
alternate route around the preserved SSM denial or the teardown prohibition.

Affected qualification:11 new transition cases +10 existing private-listener cases
+3 extracted-package cases PASS. External effects, root admission and private POSIX
directory metadata are explicitly doubled in the Windows tests; they do not prove
Linux permissions, real systemd/SQL behavior or AWS execution. No WSL fallback,
service installation, network change, credential access or new dependency occurred.
The explicit existing CI runner includes the transition suite; hosted/native Linux
acceptance remains for the approved VM/CI environment and future admitted cycle.


## Strict database recovery opt-in â€” 27 October 2026

[Current strict source/restore and protected task handoff](STRICT-DATABASE-RECOVERY.md)
connects the existing validated-v2 API policy to the recovery helper and renderer.
New private connection writes require verified strict principal metadata; legacy
loopback history is preserved and never used as fallback. Source-only implementation
and 154 affected Linux tests do not establish SQL TLS or native ECS acceptance.
