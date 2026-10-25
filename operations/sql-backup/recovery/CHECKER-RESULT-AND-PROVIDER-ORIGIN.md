# Completed local checker and provider-origin investigation — 2026-10-25

The checker completed. **Overall result: WP2A_FOUNDATION_FAIL**, not an accepted
installation. No AWS/SSM, teardown, provider execution, installation, approval
regeneration, push or image build occurred.

## Reader diagnosis and completed result

Session67523/PID519 was a hermetic source validator, not a Terraform/application
writer. It continued accumulating CPU but waited in `p9_client_rpc` on the Windows
mount; its interrupt traceback stopped in `configuration_paths`/`Path.is_file`.
The walkers filtered ignored caches after recursively traversing them. Logs were
preserved and a single cooperative SIGINT ended that reader; no force kill.

Both walkers now prune **the same existing ignored names** before descent and fail
closed on linked/unreadable source. No new directories are exempted. Actual-repo
parity verified exactly185 IaC paths and594 inventoried paths; no admission scope
was dropped. The ten catalog/traversal cases passed. Source coverage has zero
discrepancies; changed semantic dispositions remain UNVERIFIED.

A corrected mounted run still paid heavy per-file9P I/O. Its output was preserved
and that exact owned reader PID514 was also stopped once with SIGINT before the
final run. Native Windows lacks symlink privilege (WinError1314); no setting,
privilege or principal was changed to bypass that restriction.

The **same checker and tests** then ran in the existing Linux environment against
a disposable native-filesystem source fixture:789 files/5,371,366bytes, no provider
binaries, credentials, Git data or build outputs. Every copied file matched its
original SHA256; both configuration and inventory path sets matched the original.
Protected-root auxiliary files and historical characterization sources were also
included. The fixture was removed normally after preserving the report.

Completed in18.323s: **29 cases,25 passed,1 failure,3 errors,0 skips**.

- Three errors and the admission error reach the strict DEV provider-lock mismatch.
- The failure is the older historical positive characterization expecting
  WITNESS_ALLOW but obtaining UNKNOWN. The same failure was reproduced directly on
  the original checkout, so it is not a Linux-source-fixture artifact. DEV/PROD
  characterization nodes remain PARTIAL/UNKNOWN; they were not relabeled as allowed.
- No full foundation/native AWS PASS is claimed. Passing negative cases with a
  separate baseline failure must not be presented as full security acceptance.

Evidence is preserved in task-3/catalog-closure: checker-native.json/log,
native-source-equivalence.json, original-baseline-probe.json/log, the two interrupted
logs, pruning-parity.json and pruning-review.json. The source-only fixture ZIP is
1,607,301bytes, SHA256
`323d4a035dcb9f6bbb6be8d53a5302f3f377e7a5c6cb74ec0e4f2cda19a1cb2b`.

## Extra h1 identified, authenticity still not established

Git commit **b1f506329a30c96bd134134ea1d4d1297256becc** added the same extra checksum
to the five DEV runtime locks, explicitly for native Windows. It retained AWS5.100.0,
constraints and existing hashes. Its validation note reports an origin-signed
`providers lock -platform=windows_amd64 -platform=linux_amd64` operation and names
`C:\CodexDrop\temp\terragrunt-demo-aws5100-native-lock-20261017\lock-completion-metadata.json`.
That exact receipt and its selected-evidence filename were absent in the two checked
locations; no broad search was repeated.

One streaming read of the already installed windows_amd64 package reproduced
**h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs=**, exactly the extra checksum:

| Existing file | Bytes | SHA256 |
| --- | ---: | --- |
| LICENSE.txt | 16,761 | `4e2bb185ebd706f76329206869ccb348b92b6236100cfb07775fe31530dab0d5` |
| terraform-provider-aws_v5.100.0_x5.exe | 718,820,352 | `12b413fada9bad9125f344749181020bb373f45726c7879790a95999eff19e7d` |

No provider was executed/copied/downloaded. This establishes **cache/lock identity
and Windows provenance**, not independent authentication of the installed package.
The toolchain receipt authenticates Terraform/Terragrunt executables, not this
provider ZIP. Do not confuse those receipts.

[Terraform1.13.4 source](https://raw.githubusercontent.com/hashicorp/terraform/v1.13.4/internal/getproviders/hash.go)
distinguishes archive zh from content h1 and delegates content hashing to
[Go dirhash](https://raw.githubusercontent.com/golang/mod/master/sumdb/dirhash/hash.go).
The [official AWS5.100.0 SHA256 list](https://releases.hashicorp.com/terraform-provider-aws/5.100.0/terraform-provider-aws_5.100.0_SHA256SUMS)
publishes Windows-amd64 ZIP SHA256
`9f8b909d3ec50ade83c8062290378b1ec553edef6a447c56dadc01a99f4eaa93`.
It does not directly authenticate an unpacked directory's h1. Additional platform
hashes are consistent with [Terraform's lock-file model](https://developer.hashicorp.com/terraform/language/files/dependency-lock),
so the extra h1 is not itself proof of corruption.

**Minimum next step:** recover the referenced origin-verification receipt or an
already authenticated official Windows-amd64 ZIP; verify its archive checksum and
package h1 against the retained lock. If that artifact must be fetched, obtain the
required authority for that exact package first; no new binary was fetched here.
Only after origin verification should the fixed generator be deliberately updated
to preserve the legitimate cross-platform hash set, with fresh package digests and
tests. Do not delete the Windows hash, accept cache equality as origin proof or
silently regenerate the five locks.

The historical graph failure is a separate source-model characterization task:
isolate the intended historical snapshot/applicability before changing its expected
witness. Never turn UNKNOWN into ALLOW or exclude current controls merely for a PASS.
release/deploy-dev approvals remain empty; SSM remains unresolved and no new cycle
or stale budget is authorized. Manual AWS deletions still require current reconciliation.

## NAT reference for the independent EKS worker — no ECS edits

- `terraform/modules/target/dev/global/wp5-nat.tf.json`: exact slots a/b, two EIPs,
  protected launch-template inputs; empty map leaves ASGs uncreated. Each ASG has
  min=max=desired1 in one selected subnet. This has no warm replacement overlap.
- `scripts/wp4d/nat_resolver.py`: exactly two distinct ASG/AZ/EIP/route-table slots
  in one VPC; a unique Healthy/InService member plus independent EC2/IAM observations.
  Caller events cannot nominate an unrelated instance.
- `scripts/recovery/nat.py`, `scripts/tests/recovery/`, and
  `scripts/tests/wp4d/test_wp4d.py`: bounded actions/evidence/generation negatives;
  private default-route ownership belongs to the controllers, not competing TF.
- Per-AZ ASG replacement is not proven cross-AZ failover or zero downtime. Native
  zone-failure/egress continuity was not qualified here. EKS must adapt its own
  identities/state/egress requirements; these ECS bindings are not a drop-in rollout.
