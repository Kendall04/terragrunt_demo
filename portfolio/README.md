# Cloud Platform ECS · local portfolio

Product Demo, Architecture Explorer and evidence view. Plain HTML/CSS/JavaScript;
Node standard library only, no installation/build/backend credentials required.

From the repository root:

```powershell
node portfolio/server.mjs
# Or the existing workspace-local runtime:
& '..\..\.toolchain\node\node.exe' portfolio/server.mjs
```

Open http://127.0.0.1:4181. Ctrl+C closes the owned server normally. An occupied
port fails; the script never adopts or stops another server. It binds loopback
only. GET/HEAD serve an explicit asset/source allowlist; mutation routes and
arbitrary files are unavailable. CSP blocks network connections and external assets.

The message form uses memory-only synthetic text, never real KMS/SQL encryption.
Reload/reset restores examples. No localStorage, AWS mode, credentials, resource
controls, tracking, external fonts or third-party requests. User text uses textContent.

Architecture facts derive from terraform/docs/architecture.md and the recovery
runbook. V1 and az6 are distinct historical views: az6 did not create ECS/ALB.
Evidence preserves the controlled prepared-target 142.63 s RTO and its limits;
PKI/mTLS, Sentinel/email and full unchanged recovery remain pending. No live AWS
state is queried or asserted. Read-only source links expose only four fixed repo
documents, not an arbitrary filesystem browser.

Browser qualification uses already installed Playwright 1.64.1 and Chrome under
the separately authorized isolated local testing scope. No package/browser install:

```powershell
$env:PLAYWRIGHT_MODULE='C:\path\to\existing\playwright\index.mjs'
$env:CHROME_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:UI_EVIDENCE_DIRECTORY='C:\path\to\new-owned-test-directory'
node portfolio/test-browser.mjs
```

The test starts its own server on an ephemeral loopback port and fresh browser
profile under the owned evidence directory, blocks external requests and closes
browser/server in finally. It never attaches to personal Chrome or reuses another
server/profile. It verifies synthetic CRUD/reset/XSS text handling, architecture
selection/scope, source links, historical/pending labels, mobile overflow and
desktop/mobile screenshots. A nonempty evidence destination refuses overwrite.
Unresolved teardown is reported; no PID discovery or forced cleanup is used.


## Provenance and bounded quality review

This is a hand-authored repository explorer, not an Archify-generated/exported
diagram. Its HTML/JavaScript facts cite the repository documents. The Page's
Archify-specific deliverable remains open; the UI explicitly labels this origin.

Keyboard navigation moves focus to the newly visible heading, offers a skip link
and native focusable buttons, names diagram groups/components and announces demo
message/validation changes. The browser test covers three views at 320/390/768px,
labels and focused navigation. This is a bounded functional review, not a complete
WCAG or assistive-technology certification. See ACCEPTANCE.md for remaining scope.
