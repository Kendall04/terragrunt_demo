# Local recovery wiring and API image qualification — 2026-10-25

This implements the four wiring gaps from the integrated proposal. No AWS, SSM,
service installation, secret read/write, ECR push or remote workflow was executed.
The proposed 102-address/USD6 trial remains unapproved and SSM remains unresolved.

## Implemented behavior

1. **Protected V2 emission:** security root and controller module accept
   `dev_delivery_contract`, default `V1`. Only the installed configuration of
   `normal-delivery/deploy-dev` receives the selection. Gateway, PROD, emergency,
   cleanup and NAT do not acquire a V2 selector. The existing closed request and
   installed runtime factory remain the validators; callers cannot supply it.
   Source generator: `scripts/tests/security_root/{model,wp4d}.py`.
2. **Explicit target subnet:** DEV data now has optional
   `recovery_target_subnet_id`, default null; null keeps the first original private
   subnet. A selected canonical subnet ID must belong to `private_subnet_ids`.
   SAME_AZ/CROSS_AZ means choosing the corresponding reviewed ID; membership alone
   does not prove actual AZ, VPC or routing. Existing native host network/fence
   readback remains necessary. PROD and provider locks are unchanged. Authored in
   `scripts/tests/security_root/ordinary.py`, emitted in the DEV data root.
3. **Backup listener compatibility:** existing `ec2_credentials.py` optionally reads
   `Runtime.SqlEndpoint` from the hash-reviewed approval. Default stays loopback.
   Private mode requires an exact instance ID and fresh IMDSv2 account/region/own IP
   match before reading the SA secret. SQL bootstrap and both generated credential
   files use the same endpoint. Explicit `Runtime.RecoveryTrial` binds only
   `recoverydb_restore_<Trial>` on that private host; default lab DB remains demodb.
   Wildcard, public, metadata and noncanonical IPs or database aliases fail.
   Values remain only in private EC2 files; no units are started or modified here.
4. **Connection-version writer:** added `connection-version` to the existing
   `recovery/host.py`, default plan-only. It reuses `prepare.service_plan`, native
   listener/process/network/fence checks and the explicit root/instance-role runner.
   Before a future write it checks the exact canonical input hash, a recent operator
   review (600s), exact target generation, secret ARN/key and an existing AWSCURRENT.
   The hash is an operator acknowledgement, **not** owner authority or a new human
   approval deadline. A historical receipt/hash alone cannot authorize activation.

The writer uses the predetermined VersionId as ClientRequestToken and stage
`ecs-recovery-<Trial>`, never AWSCURRENT/AWSPREVIOUS. One root-private 0600 JSON file
supplies the value to the existing CLI; no secret is in argv, output, Terraform or
Windows. The file is removed on success/error, SDK/CLI retries are disabled, and the
runner's durable STARTED marker prevents replay after a denied/unknown operation.
DescribeSecret verifies original stages unchanged after the one PUT, then the
listener/network is checked again. The receipt contains metadata/hashes only and
`AllowsActivation=false`. Native observations still do not eliminate every race.

Run the new action without `--execute` for its inert CLI plan. A future admitted
host execution also requires `--listener-plan`, `--connection-write-approved-sha256`,
exact host/AZ and the existing explicit trial acknowledgement. No current script,
fixture, JSON label or this document grants permission to run it against AWS.

## Permission/installation delta for later review only

- SQL role: DescribeSecret and PutSecretValue on the one actual suffixed connection
  secret ARN. The implemented writer does not need ListSecretVersionIds. Existing
  app-secret read remains on EC2. PutSecretValue is broader than the code's one-stage
  convention; acknowledge that all sessions of the shared role receive the capability.
- The reused native network checker needs regional EC2 DescribeInstances,
  DescribeSubnets and DescribeSecurityGroups. They expose metadata beyond the two
  recorded hosts; no EC2 write/SSM action is added here.
- Administrator cleanup needs UpdateSecretVersionStage on that same secret, only
  removing the own `ecs-recovery-<Trial>` label. Individual-version deletion remains
  unavailable; a deprecated encrypted version can remain. No original-secret deletion.
- Protected installation must publish current package digests and opt in via the
  security root. Do not substitute an older sealed recovery artifact. All previous
  installed bundles/images/receipts stay immutable. No runtime IAM grant was installed.

## Verified local results

| Check | Result and boundary |
| --- | --- |
| Recovery CI, existing explicit entrypoint plus new writer suite | **194 PASS, 13 suites, zero skips**, WSL; includes real Bash/jq, wrong fence/endpoint/schema, historical review, secret/version/key/override negatives, one-write denial and STARTED replay prevention. AWS/SQL ports remain doubles. |
| Backup review/credential provisioning | **25 PASS, zero skips**, root-owned isolated temporary WSL fixtures; actual file permissions and same private endpoint, no real SQL/secrets/services. |
| WP4D loader/factory/V1/V2 | **44 PASS, zero skips**, including seven extracted-bundle cases. Original Windows short-name temp alias caused one path-only assertion; rerun in canonical task-owned temporary path passed. |
| Terraform configuration behavior | Actual provider-free Terraform console/validate PASS: generated V1/V2 configurations, unchanged other bindings, enum rejection, either reviewed subnet, foreign/invalid subnet rejection. No backend/provider initialization. |
| New focused protected-selector regressions | **2 PASS**: actual authored root opt-in and valid request plus attempted contract/profile/version/PROD overrides. The full global admission guard remains unchanged. |
| Generated outputs | Five changed generated files match their authored model. Existing five DEV provider-lock contents match HEAD; incidental blank-line rewrites from the renderer were restored. |

The full old repository admission checker is **not claimed PASS**. It rejects 11
already tracked separate Sentinel/recovery/diagnostic IaC files outside its closed
catalog. The set was verified against HEAD; this change introduced none of them and
did not relax the guard. Scoped source/behavior checks above passed. Integrating those
separate owners into the final repository CI admission remains explicit future work.

Generation also exposed two **pre-existing stale WP6 source pins** for
`scripts/normal_delivery/{delivery,authorization}.py`: current worktree bytes matched
HEAD but differed from the approval's older hashes. Source pins were refreshed and
the two local approvals (`release`, `deploy-dev`) invalidated, not fabricated for new
bytes. Their full original content remains in Git and the external preserved snapshot
SHA256 `c87068f68c7b334355964d140cfe28d1216a159e25932b3621dea8cb5c88617f`.
Generated local request roles consequently remain inert until properly reapproved.
**No deployed role/policy, installed factory or GitHub setting was changed.**

## Actual .NET 10 image, separate from the Python controller

Built the **unchanged application Dockerfile** from 26 tracked Git blobs, 61,721 bytes,
API source commit `c0da05bec7bd1681826a468d4041d9222d462838` (API subtree unchanged by
the wiring changes). Source context contains no bin/obj, credential stores or host
NuGet configuration. No large image archive was exported.

- Official SDK `10.0.402@sha256:3a48280a9a7c6276c3eeaba1efa6a08820f18c84fb9e6274c187719ecfaf9fbc`.
- Official ASP.NET `10.0.13@sha256:e4b445f93a5deeb6bd7de300febceb8dd7e481ac65ccf1b474eddc3642a3010f`.
- Actual locked NuGet restore and `dotnet publish --no-restore` succeeded. Existing
  default WSL Docker builder/cache and 4GB/2CPU bound were reused; no daemon/builder
  settings or global tool versions changed. Required pinned bases were fetched once.
- Local tag `ecs-demo-api:c0da05b-net10-local`.
- OCI manifest **`sha256:c8a59d8dc9f9f8dcc7cc624f803817f49dafcdf40ec4a538474211de4c8911f9`**.
- Config `sha256:59d5d4d6a1ee1dc15facf093745b432db7d34348b33b7351effe1e146b26912e`;
  uncompressed local image size 456,433,882 bytes.

**Native local container PASS:** UID1654; .NET and ASP.NET 10.0.13; `/health`200,
`/health/live`200, `/ready`503 without dependencies. Actual migrations-disabled log
checked. Network none, no published ports, read-only root, cap-drop ALL, no-new-privileges,
512MiB/1CPU, synthetic configuration only. Own disposable container stopped normally
and absence verified. No SQL, KMS, AWS/ECS execution or real credentials were involved.
This is not SQL-ready acceptance, a hosted CI/release qualification, ECR publication,
a CVE assessment or independent reproducible OCI-digest proof.

## Remaining next gate

Local implementations and actual API image smoke are complete. SSM authorization
cause remains unknown. Final native SQL/CLI package verification, cold fencing/restore,
secret/version publication, protected V2 installation, hosted release/current approvals,
public ECS readiness and real periodic Sentinel/outbox behavior require the separately
admitted integrated cycle. Original az6/b1/b2/d1 limitations remain unchanged. No new
AWS budget or permission is inferred from these local results.
