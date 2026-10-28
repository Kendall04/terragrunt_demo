# Batch 2 integration evidence — 2026-10-11

Baseline: `72141a7f666ce058ce4d18eb3c3adc180e521ca4`.
Integration branch: `codex/demo-improvements-batch2`.

The original E14-B `88fd1ebb44aa7ca9a33144d58f83c7be833b02f7`,
E13 `396a6c0c3f4d9349e9ddfdfece7a34f5f45f2c57`, and
E2 `140fda4e76b9bbf0eee806bd791d6589c42c9078` commits are retained
through separate no-fast-forward merges, in that order. Main remains at the
baseline in another worktree outside this conversation's authorized write roots.
No remote, AWS, provider initialization, state, deployment, fetch or push operation
was performed. Agent worktrees were not edited.

## Source and contract reconciliation

The WP5 package source list includes both the fixed NAT bootstrap and environment
mutation adapter. WP4D retains both NAT reliability and application arbitration.
Authority package identities were recomputed with the canonical WP4D/WP5 artifact
builders; the security renderer regenerated the combined Terraform. The source
inventory was regenerated using the authoritative scanner, preserving semantic
dispositions. Inventory freshness is not semantic approval or AWS evidence.

[E2](e2-environment-mutation.md) retains conditional If-Match ownership,
environment/domain isolation, generation-bound cleanup and stale-writer rejection.
There is no expiry or automatic takeover. Interrupted/uncertain operations require
administrative termination/effect reconciliation. [E13](e13-nat-reliability.md)
retains independent EIP, route and source/destination-check duties, bounded retries,
separate 14-day delivery/execution failure queues, exact environment queue grants,
bootstrap/network observations and administrator-approved launch versions.
NAT handlers have no E2 coordination grants: their independent narrow mutations
retain the accepted protected membership/installation boundaries. Global lifecycle
and administrative NAT replacement retain their existing quiescence requirements;
E2 is not represented as excluding separately authenticated administration.

[E14-B](e14b-toolchain-reproducibility.md) retains all tool/action identities,
SDK 8.0.425 with roll-forward disabled, security-root AWS lock and 14 TARGET locks.
E11's conservative selection/result enforcement remains. Inactive maps remain
external identities 0/11, WP4D 0/16 and WP5 0/8; synthetic fixtures activate nothing.

The E7 IAM regression now asserts the exact four E2 lifecycle coordination
statements before excluding those admitted statements from its historical E7
projection. Its original hash and metric action/resource/tag assertions remain.
Hygiene now includes `scripts/nat/*.sh` in Bash syntax and ShellCheck. Knowledge
checking includes E2, E13 and E14-B runbook links. Current architecture, delivery,
operations, validation and decision rows retain all three contracts; immutable
historical material and approved E1 spec hashes were preserved.

## Executed checks and honest limitations

The combined source passed 19 reproducibility, 33 E11 selection and 8 E7 tests.
Installed Terraform performs only provider-free disposable expression/structure
checks and check-only formatting. The complete E1 gate is the separate authoritative
report `batch2-final-acceptance/acceptance.json` under the local temporary directory;
its exact revision/tree, counts, all AC1–AC16, statuses and activation data determine
acceptance. An initial run overlapped bounded integration corrections and reported
inventory drift; that failed report is retained and does not count as acceptance.

Linux validation used local Ubuntu because remote operations were prohibited.
Versioned source was copied only to a new disposable temporary directory, with LF
normalization for Windows line endings. Initial CRLF failures were environmental,
not successful checks. After normalization, YAML parsing (27 workflows), Bash
syntax (33 scripts), actionlint 1.7.12, ShellCheck 0.11.0 including NAT bootstrap,
Terragrunt 0.93.3 check-only HCL formatting, 117 CD selector checks, 38 workflow
result/process checks and all 5 process-supervision tests passed.

TFLint 0.64.0 returned exit 2 on both baseline and integrated trees: 24 warnings
(7 required_version, 1 deprecated_index, 14 unused_declarations, 2 required_providers).
Rule/file/meaning comparisons found no additions or removals. tfsec 1.28.14 returned
exit 1 on both trees: 46 findings (18 ECR scanning; 7 each S3 logging, versioning,
public access blocking and encryption). Rule/resource/file/severity/meaning
comparisons also found no additions or removals. No warnings were suppressed,
no soft-fail flag was used, and no general lint remediation was introduced.
Cached upstream artifacts were SHA-256 checked against the integrated manifest
before extraction/execution; no downloads or global installation occurred.

Local Ubuntu lacks jq. The three jq-dependent CD scope/layer/gate suites and the
full E3 readiness entry point could not complete; their real nonzero exits and
missing-jq diagnostics are recorded, and neither suite acceptance nor E3 PASS is
claimed. No jq shim, dependency download or remote execution replaced them.

The pinned .NET SDK 8.0.425 is unavailable locally (SDK 9/10 are installed).
Supplemental validation used the exact integrated application source in a
disposable copy with SDK 9.0.101; the repository SDK contract was not changed.
Offline restore used only the existing NuGet cache with audit network access off;
build and publish completed with zero warnings/errors. All 99 net8.0 tests passed,
zero failures/skips, with environment-only Windows EventLog suppression. The first
run had 2 EventLog-access failures and is retained. Published Production startup
returned HTTP 200 from /health with migrations disabled and synthetic unused DB
configuration; probe capability passed. No DB/KMS dependency probe was invoked.
These checks do not prove a build using the pinned SDK. Docker's daemon was
unavailable, so no fresh Batch 2 container build/runtime evidence is claimed;
[Batch 1 evidence](e14-container-hardening.md#batch1-integrated-linux-evidence--2026-10-11)
remains dated evidence for its earlier tree.

Report/log files live outside the repository under `batch2-linux`,
`batch2-integrated-acceptance` and `batch2-final-acceptance` in the local temporary
directory. The missing jq suites and exact SDK/container execution remain explicit
validation gaps; main must not be described as integrated or the entire joint
acceptance as passed while required evidence remains missing.

Live S3 conditional behavior, provider schemas, genuine installations, network
egress, AMI replacement, alarm/SNS delivery, ECS/Fargate and deployed rollback are
unverified. Repository checks cannot substitute for those future experiments.
