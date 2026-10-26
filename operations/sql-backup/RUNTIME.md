# Executable SQL cohost runtime - local assembly contract

The executable artifact is a deterministic uncompressed tar, not the previous source
review ZIP. `package.py` retains its normal plan-default installer and adds explicit
`BinaryComponent` lineage when the selected publication contains a component manifest.
Supply both exact `--component-manifest-sha256` and `--component-source-commit`; input
inventory/bytes/identity must match before output. The package header's SourceCommit is
**the helper/packaging source**, while BinaryComponent.SourceCommit is the CLR component's
actual build origin. Those may differ and neither is an installation authorization.

Native input reused unchanged: component `b2bf8d82938e690561a85e45b3ab9e2a383413cf`,
manifest SHA256 `b0a98b236d25fa2d0bcc72269ac42e294276c53603f48945bc99ecfb3664c978`,
237 inventoried files, self-contained linux-x64/.NET10.0.13. Its C# and project bytes
remain identical to the current source. Only the later package lock was added. Every
one of the31 Linux library versions/content hashes matches that lock. The Windows-only
SNI package is absent from that Linux dependency closure; it is not silently replaced.
All binary input bytes are verified against the original pinned manifest before assembly.
The original publication, symbols and evidence remain untouched.

A fresh cross-RID locked publish was attempted and refused (NU1004, then missing Windows
runtime packs NU1100). The existing Windows-only SNI cache also does not match the current
lock hash. No install/download, hash relaxation or fabricated locked-restore PASS follows.
These failures remain recorded. The current runtime deliberately reuses the qualified
native closure instead of claiming a new compile. Fresh-build reproducibility, particularly
Windows/RID restoration, remains open. No dependency version or committed lock was changed.
The artifact qualification must report this provenance and actual Linux execution separately.

Layout: `bin/SqlBackup` is the Linux ELF apphost, accompanied by its verified CLR/dependencies
and original component manifest. Root helpers include package/cohost/observer/publisher,
credential provisioning and local release verification. They are canonical UTF8/LF; native
files remain byte-identical. PDBs alone are omitted from the archive with their original
names explicitly recorded. The inspector binds that declared omission to the original
manifest; an outer hash recalculation cannot substitute binary identity/content.

Helpers/ELF executable mode0755, libraries/config metadata0644; staged host configuration
root:service-group0640; service state0700. No credentials, profiles, private keys, DB dump,
connection string or actual host configuration is embedded. Opt-in settings are supplied
and hash-inventoried at installation. Source manifest, mode, archive bounds and exact
component lineage are checked before installation. No timer is enabled by installation.

The persistent `cohost.py activate` entrypoint defaults to a local plan. With separately
approved native external readiness, root may use `--apply --confirm-root-activation <package-sha>`
after the existing post-restore credential handoff. It verifies integrity/window, exact DB,
completed provisioning receipt and root-private material before requesting the declarative
target. It never prints/reads credential file contents. Unknown/failed systemctl outcomes
stop without retries. A matching hash is only local-byte acknowledgement, never owner consent.
The proposed boot script calls this same entrypoint; rerunning SQL's whole user-data is
neither necessary nor safe. Fixture roots require a double port before any action.

Local runtime qualification should execute the actual packaged ELF on Ubuntu WSL, verify
build-info against BinaryComponent, exercise no-cloud/check/replay/maintenance/error gates,
and install/reinstall the real archive only in a private disposable root. Real checker/SQS
ports may be substituted in full observer tests and must be labelled as doubles. Any
CHECK_COMMAND_RESULT produced there is test data, never authenticated AWS evidence. Never
execute `--aws` against a live store, contact IMDS, launch SQL/systemd, or send email here.
Published component/unit tests and source wiring remain additional evidence, not live proof.

Target: the project's SQL recipe is **Ubuntu22.04**, not the historical AL2023 observer.
Ubuntu24.04 WSL native ELF execution tests Linux loading and selected command paths only.
Target AMI packages/GLIBC/ICU/OpenSSL/ODBC/SQL, instance-role S3/KMS, actual boot/timers,
credentials, native backup/restore and public Fargate still need an admitted target test.
AL2023 receives no runtime/SQL qualification from this artifact and no new host is proposed.

SSM is **not a dependency of cohost observation or the external heartbeat watchdog**:
normal operation uses local services plus S3/SQS and the existing scheduled Lambda. The
b2/d1 AccessDenied remains a historical unresolved diagnostic, not a Sentinel failure or
mandatory new observer status probe. However the existing complete cold-recovery runner
still uses remote execution for source/restore/credential handoff. That operational path
needs explicit native admission/evidence before the102-address integrated cycle; neither
this artifact nor an alternate SSH/document/principal resolves or bypasses a rejected call.
Do not recreate a dedicated observer just to re-run d1. Any future change to recovery's
control transport is a separate reviewed design, not implied by local assembly.

Publication/permissions/next trial remain one unapprovedUSD6 proposal. The local archive
hash binds the exact future object key/version and artifact S3/KMS statements described in
[the wiring review](recovery/COHOST-WIRING-REVIEW.md); actual VersionId only exists after an
approved immutable upload and readback. No authority, policy, source approval, state or
remote setting is regenerated here. Preserve new artifact/terminal-state receipts and
historical backups; retire only own approved versions/resources under the future packet.


## Executed qualification - 2026-10-26

The actual executable tar `SqlBackup-cohost-0cabbbb.tar` (133,672,960bytes,
250 payload files plus manifest) is locally qualified. SHA256:
`feda7d1495637db751a92d818f4150bc305b7bb72f05431142446a72c16d5984`.
Its helper source is0cabbbb91fc39e20e26345bdfae37bdb3b9e082a and its explicit CLR
component origin remainsb2bf8d82938e690561a85e45b3ab9e2a383413cf, not a new compilation.

39 actual-tar checks passed on Ubuntu24.04 WSL/x86_64/glibc2.39. The ELF ran as
`nobody`; its native apphost libraries resolved. Real archive install/idempotence,
permissions/integrity/tamper refusal, no-cloud maintenance/UNKNOWN, synthetic health
replay, installed observer/publisher pending retry/recovery/20-attempt cap and the
installed credential/activation handoff passed. Cloud/SQL/systemctl ports were local
doubles and ephemeral synthetic material only. No systemd timer, SQL process, IMDS,
AWS call or email was used. Disposable installation was removed normally. Streaming
reconstruction reproduced the tar SHA without a second large runtime archive.

Exact Git-blob comparison confirms9 original component source/project files unchanged;
all31 included Linux dependency versions/content hashes match the current lock.
All237 input publication files matched the old pinned manifest before assembly; only
its PDB was omitted with explicit lineage. The committed source lock and approvals
remain unchanged. NU1004/NU1100 were technical offline restore failures in preparation
for **local dotnet publish**, not a denied AWS upload or security-review rejection.
The Windows SNI cache mismatch stopped its proposed use; that package is not in the
Linux closure. No rejected operation, alternate principal, new SDK or weakened lock
was used to assemble this previously qualified Linux component with new helpers.

Evidence is retained in task-3/cohost-runtime-1285831: runtime-artifact-qualified.json,
runtime-manifest.json, native-runtime-qualification.json, source-dependency-equivalence.json
and bounded logs. The assembly's original pending receipt is preserved separately.
The review directory contains draft publication/access/try-and-retire consent; no request
was sent andUSD6 is still unapproved. The runtime tar is the executable deliverable;
the small review ZIP references it by SHA rather than duplicating133MB of binaries.

This closes local artifact loading/staging/flow qualification, not a new build from a
clean machine or Ubuntu22.04 SQL/cloud scheduling/cold-recovery/Fargate acceptance.
SSM is absent from normal cohost/watchdog operation; the existing full recovery runner's
remote-control admission remains a separate unresolved gate. No denied status was retried.
