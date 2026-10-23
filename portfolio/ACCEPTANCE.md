# Local portfolio acceptance checkpoint

This is local UI evidence, not complete UI/ECS acceptance. The final isolated
browser receipt records 14 checks PASS at 2026-10-23T07:15:37.083Z; SHA256:
`923ed7bc5d0f5c05303126a0d0ea6455506effa88e0a79aa519450240345ff2e`. The [test source](test-browser.mjs) defines the checks.
The earlier failed focus regression receipt is preserved, not counted as PASS.

- [x] Memory-only Product Demo: submit/reset, explicit synthetic data, literal text handling.
- [x] Source-backed V1/az6 historical navigation with distinct scopes and RTO limits.
- [x] Skip link, heading focus on view changes, keyboard node selection, accessible textbox/node/group names and action/validation announcements.
- [x] All three views at 320/390/768px without document overflow.
- [x] Explicit DEMO/no-live status; PKI/Sentinel pending; custom explorer provenance.
- [x] No external requests or console errors; fresh browser/server closed normally.
- [ ] Actual Archify-generated/exported diagrams. Current HTML/JS explorer is hand-authored, not Archify output.
- [x] Portable Node contract/server suite wired into repo-hygiene source; 10 local tests PASS, no packages/browser required.
- [ ] Full CI/hygiene acceptance: hosted execution unrun and existing DEV/PROD provider-lock identity failure and 30 pre-existing source-inventory findings remain; no gate was skipped.
- [ ] Hosted/new repository and real CI/OIDC release scope from the Page. No hosting or remote change performed.

Separately open ECS gates: full unchanged EC2/systemd/remote-restore/API recovery,
live alert forwarding/independent schedule/confirmed email, PKI/mTLS/rotation and
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
download, initialization or broad audit is implied. Actual Archify output and
PKI/Sentinel source/access remain separate open gates.
