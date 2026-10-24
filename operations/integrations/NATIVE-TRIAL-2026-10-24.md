# Terraform/Terragrunt observer trial b2 — retired, partial acceptance

Status: **CLOSED_CLEAN_PARTIAL_ACCEPTANCE**, 2026-10-24 **07:01:54 UTC**.
Root cause: UNRESOLVED at the exact IAM-condition level. Authorization failure before
script execution is demonstrated; successful execution of the observer is not.

## Native evidence and boundary

Account341936017254/us-east-1, run `ecs-sentinel-r20261024b2`, source
`2c8c3e7b79ba84029ec3965ea0cb4202cc0ddd55`. Owner approved the sealed packet
`5eadc0b1bda0c74a7f1a439de8ecefedd3253e23443a6eb80f5c08f8be474af1` and subsequent
specific supplements. New USD2, T0 05:41:51 UTC; no prior allowance reset. Billed cost
was not queried or confirmed. Sealed packet and binary artifacts remain immutable.

43 direct resources were created. AL2023 bootstrapped the hash-qualified bundle and
reported `INSTALLED_TIMER_INERT`. SNS subscription was natively confirmed. One empty
AWS Lambda .NET10 dispatch returned Completed/CursorSaved=true and persisted a DynamoDB
control cursor. This is real managed runtime/storage proof, not producer acceptance.

**0 events and 0 notices** were sent; observer timer never activated, mapping and
dispatch rule stayed disabled. No authenticated manifest/checker/SQS/periodic-health/
dedupe/recovery/inbox acceptance follows from b2. The separate [b1 pilot](NATIVE-TRIAL-2026-10-23.md)
did prove synthetic ingestion, persistence and two owner-confirmed inbox notices;
its ten Pending effects were never retrospectively drained. SQL az6 is another scope.

Terraform destroyed the remaining41 addresses at06:58:38 UTC after exporting evidence,
disabling own-table deletion protection and deleting the two own code-object versions.
28 exact native checks at06:59:06 confirmed runtime absence, including terminated host,
missing root disk/ENI/network, Lambdas/mapping/rule, queues, table, bucket, logs, SNS,
subscription and own IAM roles/boundaries/profile. No SSM metadata rows remained.
Terminal backend state serial11/version `vUFMvB59cQNp_5ZPaXJn2NBsC246mUqZ` is retained,
SHA256 `225ad5ff6ee09202872dcb835c03045648484a7ed125efa7d446b65edaf9f73c`.

Original backend/KMS policies restored, temporary inline removed, Part4 defaultv5 and
Part7 defaultv3 restored. Temporary Part4v8/Part7v4 removed. Archived historical Part4v7
content recreated asv9; its old ID/date were irrecoverable as approved. Other original
policy-version identities/dates were verified unchanged. No original backup/retention
write or EKS resource/state action occurred. No resource remains for local diagnosis.

Closure receipt SHA256:
`dfdc763edd4b60542730c14fe90939b225966f646d945219809280d791f576b8`.
Native absence receipt:
`73446171e2cc711a6644020f9d0479bff1f1902eb51d8849330eb37a2df6b228`.
Access reversal receipt:
`cbc8aeb877753f0a7028b36698d60fd85fc1623fde1f6d74097f1c5f151082c8`.
Full receipts remain in the preserved runtime-r20261024b2 evidence directory; no large
binary archives, credentials, email confirmation tokens or raw state are copied into Git.

## SSM comparison — what the evidence establishes

| Check | Preserved observation | Implication |
| --- | --- | --- |
| Document | Own `ecs-sentinel-r20261024b2-observer-control`, owner341936017254, Command/JSON/schema2.2 | Not an AWS-managed document or a Session document |
| ARN | `arn:aws:ssm:us-east-1:341936017254:document/ecs-sentinel-r20261024b2-observer-control` | Same exact ARN in operator/node permissions |
| Version/hash | Version1/default1, Sha256 `29b383c0a0a1731781ab6c3f828d5945de4afdbbc8912b17f2f495b52a3a66fe` | Both requests pinned identical version/hash; fetched content matched saved state |
| Action/step | Action=status, sole step ObserverControl, fixed Python command using aws:runShellScript plugin | No arbitrary command input, no alternate AWS-RunShellScript document attempted |
| Destination | `i-009e213ec6cf1e3cb`, own Trial tag, profile/role `ecs-sentinel-r20261024b2-observer`; Online | Registration/bootstrap was real, not execution permission proof |
| Caller | TerragruntDemoDevOperator assumed by existing administrator; no session policy passed in the captured runner | Operator role snapshot had no permissions boundary; admin was not substituted for SSM |
| Node policy | Own-document GetDocument/DescribeDocument; inline equals boundary; same deadline/region | Static agreement, not proof that every agent request was authorized |
| Original global conditions | DateLessThan, RequestedRegion, instance Trial; separate ViaAWSService true/false branches | A matching statement in one assumed context is not the service's actual evaluation |
| Supplement708 | Exact document+instance ViaAWSService=true branch drops region/tag; expiry remains | Installed/read back, one retry after propagation; did NOT resolve denial |

Two known accepted commands:

- 06:09:13: `a3894787-1d3d-430a-9d6d-900578376935`.
- 06:40:56: `e5d894d1-1ce7-4d49-8c4f-bd8a72f5ede3` (one approved retry).

Both finished Failed/AccessDenied/ResponseCode=-1 with no execution start, output or
script stderr. The [small captured fixture](fixtures/ssm-b2-status.json) preserves
their exact trimmed results, intents/acceptances and original receipt hashes. The
trimmed collector omitted DocumentName/DocumentVersion/PluginName from result.json;
the separate first ListCommandInvocations record binds name/version/step. This loss of
receipt detail is a demonstrated tooling defect, but is not evidence of the AWS cause.

AWS documents [-1 as not started or not received](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html),
and [AccessDenied as the initiating user/role lacking target access](https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html).
That supports a pre-execution authorization failure, not a SQL/Python/systemd defect.
Online status, accepted SendCommand and an empty Lambda invocation do not narrow it to
a particular missing key. No agent authorization log, service re-evaluation context,
SCP evaluation or complete diagnostic trace was captured. Do not infer one.

AWS [requires a ViaAWSService=true allowance when using global conditions for SendCommand](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-setting-up.html).
Our forwarded-context hypothesis was grounded in that requirement, but the failed
retry disproves claiming that708 was a validated fix. Expiry was still in the future.
Missing/wrong context, other effective restrictions and asynchronous propagation
remain hypotheses; none justifies removing conditions or adding wildcard administration.
The [IAM simulator](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html)
evaluates supplied policies/context and may differ from live behavior. Simulating an
invented ViaAWSService/tag/date context cannot reveal what SSM actually evaluated.
No simulation was performed or represented as native success in this follow-up.

## Minimal local correction and next decision

The offline [status gate](ssm_execution.py) requires a successful terminal invocation,
zero script response, exact accepted-command/instance/document/version/step binding,
ordered execution timestamps and the existing OBSERVED JSON contract. It returns only
CONFIRMED_STATUS_ONLY, never backup acceptance. Captured denials, missing provenance,
replayed/wrong identity results and systemd acceptance without status output fail closed.
Constructed success cases in tests are explicitly synthetic. This corrects evidence
admission; it does **not** fix AWS authorization or replace the unchanged host bundle.

Any future collector must preserve the full non-secret invocation identity fields and
the current policy version/hash before deciding success. A specific AWS-policy fix is
not ready: require a permitted diagnostic trace identifying the denied evaluation
before proposing new access. No calls, retries, permission installation or new cycle
are authorized by this document. No alternative document/principal/control path.

SSM finite controls are trial orchestration, not part of the backup-to-Sentinel event
contract. For the portfolio, recommend considering an immutable bounded startup
sequence after SNS is confirmed, so producer acceptance need not depend on interactive
root SSM controls. Keep expiry, finite event/notice budgets, receipt export and cleanup.
This is a future design decision with its own plan/access review; not implemented and
not permission to bypass this denial. SSM can remain optional operations tooling.

No new service, PKI, business API feature, NAT action or notification backend is needed.

## Local regression of this follow-up

27 host/receipt Python tests and17 Node source/server/Archify-contract tests PASS.
The six new receipt tests run within the existing host CI recipe. No browser test,
AWS query, simulator, installation, provider initialization or build was run by this
follow-up. Previous Chrome16 results remain historical, not relabelled as current.
Generated Archify HTML/pins and sealed trial artifacts are unchanged.
