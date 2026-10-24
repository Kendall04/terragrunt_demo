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

The service suite is now explicitly included in the existing CI entrypoint: **6 suites/77 PASS/0SKIP in WSL**, including the six new service-contract tests and negatives for fencing, identity, backup, public/routing endpoint, schema/rollback and repeated operation identity. This is not hosted CI or SQL/ECS runtime acceptance.

## What is actually checked

- Cold receipt must bind the same target/source and terminated-source fence, correct account/region, new target after recovery request, CHECKDB-readable restore, ordered readiness/fence timestamps and a fresh final observation. Quiescent/stopped SQL or a failed probe alone does not replace source termination.
- SQL must be in the same application VPC, match the target instance ID and private RFC1918 subnet, have no public IPv4 and propose a single private-IP SQL listener. Link-local/metadata addresses, unspecified/broadcast/network endpoints and foreign instance/VPC fail. Only TCP1433 from the exact task SG is admitted in the supplied ingress metadata.
- Connection metadata contains only protected connection-secret ARN, immutable version ID, endpoint/database and key ARNs. Raw Password/connection-string fields fail. It cannot substitute the SA/app-password secret for the connection secret. Existing application-text/connection-secret CMK and separate backup CMK remain distinct; execution role needs only connection-secret/GetSecretValue/decrypt, task role application text Encrypt/Decrypt, SQL role selected S3 backup version/decrypt.
- Release ID must match the same-account regional ECR image digest. Restored/candidate/rollback schema fingerprints must agree; rollback/new delivery/history IDs must be distinct valid operations. These fingerprints still need protected release/restore provenance live; caller declarations are not compatibility attestations.
- Routing references must match the current dev ALB and blue/green target conventions. Public URL must match the declared same-region HTTP API ID. Job/controller bindings, real API ownership, VPC route/NACL membership and permission effectiveness still need native readback.

The code calls **`scripts.workflow_requests.contract.request('deploy-dev', ...)`**, using its actual gateway and authorization validators. The public body stays release/history/replicas, never a raw endpoint, secret or arbitrary resource override. Existing pinned repository/ref/OIDC configuration is not changed. WP4 remains the only task revision/count/listener writer; E2 durable operation ownership and unknown-outcome/replay guards remain mandatory.

## Executable references and remaining live work

| Step | Existing executable or output | Actual boundary |
| --- | --- | --- |
| Source fencing + cold restore | `host.py restore --cold-request ...` | Native future readback and authorization required; cannot use a synthetic receipt to turn on writes |
| New connection version | Plan emits ARN/version metadata only | Approved secret writer must create/verify the new version outside Terraform, under the reviewed ownership/transaction. No value writer was added |
| Candidate task JSON | Output `RendererArguments` calls `scripts/render-demo-api-taskdef.sh` | This renderer exists; its canonical Git blob passes Bash syntax. `jq` is absent locally, so materialization was **not executed**, no fake jq substituted. Windows mount has CRLF; use a Linux LF checkout/export. No tool was installed |
| Pin candidate configuration | Exact Secrets Manager version selector `ARN:::VersionId`; proposed migration-off environment append | Existing protected WP4 config must be deliberately rebound/reviewed; caller cannot override it. Fargate Linux platform>=1.4.0 required for version selector |
| Fresh tasks / candidate validation | Existing WP4 flow, `scripts/ecs-readiness-gate.sh` and E3 | New candidate tasks must fetch the reviewed version; existing tasks do not refresh secrets automatically. No direct update-service bypass |
| Controlled traffic switch | Existing WP4/E2-owned transition | Task-local SQL/KMS readiness and final E3 check first. Do not advertise public replacement validation before switching if no candidate public route exists |
| Declare service ready | Plan requires public `/ready`, old-marker decrypt, fresh POST/read and total request→public-ready time | Only after the controlled switch; failed public checks leave service recovery unaccepted. No public HTTP request was made here |
| Rollback | Actual WP4 rollback-release request shape | Compatible old image against the SAME restored DB endpoint/version; never reconnect to the terminated original DB or claim schema rollback |
| Owner review / retirement | Existing approved lifecycle ownership | Future plan must include live viewing window, complete application resources, IAM/budget and retirement. Isolated30-object/USD4 proposal does not include full app reconstruction |

[Official ECS secret projection semantics](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html): secrets are injected at task start and version selectors require Linux platform1.4.0+. Metadata tests do not prove installed platform, permissions or which task used a secret.

### Concrete architecture gaps preserved, not hidden

Current cold bootstrap/runtime verifier is loopback-only. A valid future **application SQL host mode** must instead bind the exact private IP, preserve no-public-IP/task-SG isolation, adapt fresh query/socket-owner proof and revalidate restore/API after that change. Do not blindly allow0.0.0.0 or claim SQL supports a new multi-address configuration from a metadata field. The dry plan's private address is a proposed mode, not proof current helpers implement it.

Current task template defaults startup migrations. The plan emits the proposed environment append `Database__RunMigrationsOnStartup=false` but changes no operational template. Recovery must not let startup migrations alter the restored schema before compatibility/rollback review. Normal delivery/migration ownership needs a deliberate qualified recovery binding; disabling migrations globally would change unrelated deployment behavior.

Minimum recommended integration: restore into the application's existing private VPC/subnet and reviewed DB SG, update a versioned protected connection reference, create candidate tasks through the installed delivery owner, validate, then switch/verify publicly. No peering, new business service, PKI or alternate deployment controller is introduced. The full saved plan, existing infrastructure availability, bindings, permissions and new cost still require a grouped native admission. SSM's unresolved denial is not bypassed by this local plan.
