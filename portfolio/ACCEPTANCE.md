# Local portfolio acceptance checkpoint

This is local UI evidence, not complete UI/ECS acceptance. Current final isolated
Chrome receipt records **15 checks PASS** at 2026-10-23T17:31:18.062Z; SHA256:
`f52419d64df43ae03f238f3a729f009fe2259fbfc956bede73fba083c33a0c82`. The [test source](test-browser.mjs) covers all five
Archify diagrams at desktop/mobile, native zoom/reset/keyboard focus, visible SVG
nodes and opaque iframe isolation. No external requests/errors; browser/server closed.
Earlier clipping captures and a failed hidden-index geometry assertion are retained
outside the repository; they do not count as final acceptance. Previous 14-check
inspector evidence remains historical, separate from this new qualification.

- [x] Memory-only Product Demo: submit/reset, explicit synthetic data, literal text handling.
- [x] Source-backed V1/az6 historical navigation with distinct scopes and RTO limits.
- [x] Skip link, heading focus on view changes, keyboard node selection, accessible textbox/node/group names and action/validation announcements.
- [x] All three views at 320/390/768px without document overflow.
- [x] Explicit DEMO/no-live status; PKI/Sentinel pending; custom explorer provenance.
- [x] No external requests or console errors; fresh browser/server closed normally.
- [x] Five authentic Archify 3.1.0 outputs integrated; pinned sources/HTML and finalizer gates recorded in [generation evidence](../docs/interactive/GENERATION.json). The inspector remains explicitly hand-authored.
- [x] Portable Node contract/server suite wired into repo-hygiene source; 14 local tests PASS, no packages/browser required.
- [ ] Full CI/hygiene acceptance: hosted execution unrun and existing DEV/PROD provider-lock identity failure and 30 pre-existing source-inventory findings remain; no gate was skipped.
- [ ] Hosted/new repository and real CI/OIDC release scope from the Page. No hosting or remote change performed.

Separately open ECS gates: full unchanged EC2/systemd/remote-restore/API recovery,
deployed independent observer/live alert forwarding/confirmed email, PKI/mTLS/rotation and
Sentinel integration. PKI/Sentinel implementation sources/packages were unavailable
in the previously reviewed local roots; actual pinned contracts/access remain
required. Do not invent upstream APIs or mark those integrations complete.

This checks DOM names/focus/announcements and responsive behavior in one installed
Chrome; it does not certify complete WCAG or actual screen-reader coverage.

## Next executable local task

The [bounded provenance review](../terraform/docs/e14b-toolchain-reproducibility.md#native-lock-provenance-follow-up---2026-10-23)
identified DEV's single Windows h1 addition and confirmed all 15 official release
checksums plus the current cache content hash. Equality remains blocked pending the
original authenticated receipt/already available official archive and deliberate
canonical-generator/package-identity review. Recover that evidence first; preserve
the native DEV hash, provider 5.100.0 and exact protected validation. No binary
download, initialization or broad audit is implied. PKI/Sentinel source/access and real hosting/release remain separate open gates.


## Independent observer increment

- [x] Finite fresh check independent of backup creation, persistent change/reminder/recovery deduplication and sanitized local JSON candidates.
- [x] Inert independent service/timer proposals; cadence/reminders/expected-UP decisions explicit, no SQL dependency or installation.
- [ ] Actual independent host/role/config, authenticated producer failure ingestion, timer operation and real Sentinel/mail delivery.

See the [observer runbook](../operations/sql-backup/OBSERVER.md). This is local
readiness, not new AWS or delivery acceptance. Archify captures remain unchanged.

Observer local verification: Linux 24 PASS (15 new observer + nine existing
signal/component-binding); Windows 14 PASS / one POSIX-only skip. No service
installation, cloud check or external notification was performed.

- [x] Observer/signal tests integrated into repo-hygiene source before provider-lock checks/tool installs; no dependency/cloud requirement. Hosted execution remains unrun.
