// Isolated Chrome, DEMO + explicit HTTP doubles. Never dispatches to AWS.
import assert from "node:assert/strict";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import { randomBytes, createHash } from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createProductServer } from "./server.mjs";
import { catalog } from "./diagrams.mjs";
import { build } from "./build.mjs";
import { createPreview } from "./preview.mjs";
const destination = process.env.UI_EVIDENCE_DIRECTORY;
assert(
  destination && process.env.PLAYWRIGHT_MODULE && process.env.CHROME_EXECUTABLE,
  "Explicit existing Chrome/Playwright and new evidence directory required",
);
await mkdir(destination, { recursive: true });
assert.equal((await readdir(destination)).length, 0, "Preserve prior evidence");
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const servers = [],
  receipt = {
    kind: "DEMO_AND_HTTP_DOUBLES_NOT_AWS",
    at: new Date().toISOString(),
    checks: [],
    captures: [],
    externalRequests: [],
    browserErrors: [],
  };
async function serve(options) {
  const s = createProductServer(options);
  servers.push(s);
  await new Promise((r) => s.listen(0, "127.0.0.1", r));
  return `http://127.0.0.1:${s.address().port}`;
}
const demo = await serve({});
let browser;
function pass(s) {
  receipt.checks.push(s);
}
async function capture(page, name) {
  if (await page.locator("#diagram-frame").count()) {
    const f = await (
      await page.locator("#diagram-frame").elementHandle()
    ).contentFrame();
    await f.waitForURL(
      "**" + (await page.locator("#diagram-frame").getAttribute("src")),
    );
    await f.locator("svg [data-node-id]").first().waitFor();
    await f.locator(".diagram-nav [data-view=reset]").click();
  }
  await page.evaluate(
    () =>
      new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  const bytes = await page.screenshot({
    path: path.join(destination, name + ".png"),
    fullPage: true,
  });
  receipt.captures.push({
    file: name + ".png",
    sha256: createHash("sha256").update(bytes).digest("hex"),
  });
}
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_EXECUTABLE,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  await context.route("**/*", (r) => {
    if (new URL(r.request().url()).origin !== demo) {
      receipt.externalRequests.push(r.request().url());
      return r.abort();
    }
    return r.continue();
  });
  const p = await context.newPage();
  p.on("pageerror", (e) => receipt.browserErrors.push(e.message));
  let apiCalls = 0;
  p.on("request", (r) => {
    if (r.url().includes("/_api/")) apiCalls++;
  });
  await p.goto(demo + "/demo");
  await p.locator(".message-row").first().waitFor();
  await p.keyboard.press("Tab");
  assert(
    await p.locator(".skip").evaluate((n) => n === document.activeElement),
  );
  await p.keyboard.press("Enter");
  assert(await p.locator("main").evaluate((n) => n === document.activeElement));
  pass("Keyboard skip link");
  const xss = "<img src=x onerror=window.injected=true> · texto sintético";
  await p.locator("#message").fill(xss);
  await p.locator("#send").click();
  await p.locator(".message-row").filter({ hasText: xss }).waitFor();
  assert.equal(await p.locator(".message-row img").count(), 0);
  assert.equal(await p.evaluate(() => window.injected), undefined);
  await p.locator("#reset").click();
  assert.equal(await p.locator(".message-row").count(), 2);
  pass("DEMO create/read/reset and literal XSS");
  await capture(p, "desktop-product");
  await p.locator('aside a[href="/resilience"]').click();
  assert(await p.locator("h1").evaluate((n) => n === document.activeElement));
  for (const [key, label] of [
    ["nat", "NAT / E13"],
    ["sql", "SQL recovery"],
    ["backup", "Backup / Sentinel"],
  ]) {
    await p.getByRole("button", { name: label, exact: true }).click();
    await p
      .getByRole("button", { name: "Paso siguiente", exact: true })
      .click();
    assert.equal(await p.locator("progress").getAttribute("value"), "1");
    await capture(p, "desktop-resilience-" + key);
    await p.getByRole("button", { name: "Reiniciar", exact: true }).click();
  }
  await p.getByRole("button", { name: "Reproducir", exact: true }).click();
  await p.waitForFunction(() => document.querySelector("progress").value > 0);
  await p.getByRole("button", { name: "Pausar", exact: true }).click();
  pass("Three honest historical replays, pause/step/reset");
  await p.locator('aside a[href="/architecture"]').click();
  const diagrams = await catalog();
  for (const width of [1440, 390]) {
    await p.setViewportSize({ width, height: 1000 });
    for (const d of diagrams) {
      await p.locator("#diagram-select").selectOption(d.id);
      const f = await (
        await p.locator("#diagram-frame").elementHandle()
      ).contentFrame();
      await f.waitForURL("**/diagrams/" + d.id + ".html");
      await f.locator("svg [data-node-id]").first().waitFor();
      await f.locator(".diagram-nav [data-view=reset]").click();
      assert((await f.locator("svg [data-node-id]").count()) > 0);
      assert(
        await f.evaluate(() => {
          try {
            parent.document.body;
            return false;
          } catch {
            return true;
          }
        }),
      );
      const node = f.locator("svg [data-node-id]").first();
      const before = await node.evaluate(
        (n) => n.getBoundingClientRect().width,
      );
      await f.locator(".diagram-nav [data-view=in]").click();
      await f.waitForFunction(
        (w) =>
          document.querySelector("svg [data-node-id]").getBoundingClientRect()
            .width > w,
        before,
      );
      await f.locator(".diagram-nav [data-view=reset]").click();
      assert(
        await p.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${width}/${d.id}`,
      );
      const frameBytes = await p
        .locator("#diagram-frame")
        .screenshot({ path: path.join(destination, `${width}-${d.id}.png`) });
      receipt.captures.push({
        file: `${width}-${d.id}.png`,
        sha256: createHash("sha256").update(frameBytes).digest("hex"),
        diagram: d.id,
        width,
      });
    }
    await p.locator("#diagram-select").selectOption("v2-sentinel");
    await capture(p, width === 1440 ? "desktop-explorer" : "mobile-explorer");
  }
  await p.getByRole("button", { name: "Hoja de lectura", exact: true }).click();
  const reader = await (
    await p.locator("#diagram-frame").elementHandle()
  ).contentFrame();
  await reader.waitForURL("**/reading/v2-sentinel.html");
  await reader.locator("svg").first().waitFor();
  assert.equal(await reader.locator("a[href]").count(), 0);
  await p.getByRole("button", { name: "Volver al visor", exact: true }).click();
  await p.locator(".textual summary").click();
  await p.locator("[data-inspect]").first().click();
  assert((await p.locator("#node-inspector .source-links a").count()) > 0);
  pass(
    "12 pinned diagrams desktop/mobile, zoom/fit, opaque sandbox, sources, reader and text alternative",
  );
  for (const width of [320, 390, 768]) {
    await p.setViewportSize({ width, height: 844 });
    for (const view of ["/demo", "/resilience", "/architecture", "/evidence"]) {
      await p.locator(`aside a[href="${view}"]`).click();
      assert(
        await p.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${width}${view}`,
      );
      assert(
        await p.locator("h1").evaluate((n) => n === document.activeElement),
      );
      assert(await p.locator("#global-mode").isVisible());
      if (width === 390) await capture(p, "mobile-" + view.slice(1));
    }
  }
  assert.equal(apiCalls, 0);
  assert.deepEqual(receipt.externalRequests, []);
  pass("DEMO zero API/external calls, keyboard routes, 320/390/768 responsive");
  const staticDirectory = path.join(destination, "static-package");
  receipt.staticManifest = await build(staticDirectory);
  const staticServer = await createPreview(staticDirectory);
  servers.push(staticServer);
  await new Promise((r) => staticServer.listen(0, "127.0.0.1", r));
  const staticOrigin = `http://127.0.0.1:${staticServer.address().port}`;
  const sc = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const staticRequests = [];
  await sc.route("**/*", (r) => {
    if (new URL(r.request().url()).origin !== staticOrigin) {
      staticRequests.push(r.request().url());
      return r.abort();
    }
    return r.continue();
  });
  const sp = await sc.newPage();
  sp.on("pageerror", (e) => receipt.browserErrors.push(e.message));
  await sp.goto(staticOrigin + "/demo");
  await sp.locator(".message-row").first().waitFor();
  await sp
    .locator("#message")
    .fill("Paquete estático independiente · prueba sintética");
  await sp.locator("#send").click();
  await sp
    .locator(".message-row")
    .filter({ hasText: "Paquete estático independiente" })
    .waitFor();
  await sp.goto(staticOrigin + "/architecture");
  await capture(sp, "static-explorer");
  assert.deepEqual(staticRequests, []);
  await sc.close();
  pass(
    "Reproducible static package: direct routes, DEMO write/read and isolated diagram without backend",
  );
  // An explicit AWS-mode local server with no real upstream. Tests label fault injection as doubles.
  let behavior = "healthy",
    upstreamCalls = 0;
  const token = randomBytes(32).toString("hex");
  const aws = await serve({
    mode: "aws",
    token,
    now: () => Date.parse("2026-11-07T01:00:00Z"),
    fetcher: async (url) => {
      upstreamCalls++;
      if (behavior === "http")
        return new Response("{}", {
          status: 503,
          headers: { "content-type": "application/json" },
        });
      if (behavior === "network") throw new Error("Injected connection loss");
      if (behavior === "timeout")
        throw new DOMException("Injected upstream deadline", "TimeoutError");
      return new Response(
        JSON.stringify(
          url.includes("/text") ? [] : { status: "Healthy", checks: [] },
        ),
        { headers: { "content-type": "application/json" } },
      );
    },
  });
  const ac = await browser.newContext({
    viewport: { width: 1440, height: 950 },
    colorScheme: "dark",
  });
  await ac.route("**/*", (r) =>
    new URL(r.request().url()).origin === aws ? r.continue() : r.abort(),
  );
  const a = await ac.newPage();
  await a.goto(aws + "/demo#session=" + token);
  assert(!a.url().includes(token));
  assert.equal(upstreamCalls, 0);
  for (const b of ["http", "network", "timeout"]) {
    behavior = b;
    await a.locator("#refresh").click();
    await a.locator("#list-status .error").waitFor();
    assert.equal(await a.locator(".message-row").count(), 0);
    assert.match(await a.locator("#global-mode").innerText(), /AWS/);
  }
  await capture(a, "aws-offline-double");
  behavior = "healthy";
  await a.getByRole("button", { name: "Comprobar conexión" }).click();
  await a.locator("#health-result").filter({ hasText: "SQL + KMS" }).waitFor();
  await ac.setOffline(true);
  await a.locator("#refresh").click();
  await a.locator("#list-status .error").waitFor();
  assert.equal(await a.locator(".message-row").count(), 0);
  await ac.setOffline(false);
  await a.reload();
  await a.locator("#refresh").click();
  await a
    .locator("#list-status .error")
    .filter({ hasText: "bloqueada" })
    .waitFor();
  pass(
    "HTTP 503 / timeout / lost connection / expired in-memory capability: no synthetic fallback",
  );
  assert.deepEqual(receipt.browserErrors, []);
  receipt.status = "PASS";
} catch (e) {
  receipt.status = "FAIL";
  receipt.error = e.stack;
  process.exitCode = 1;
} finally {
  await browser?.close();
  for (const s of servers) await new Promise((r) => s.close(r));
  await writeFile(
    path.join(destination, "BROWSER-QA.json"),
    JSON.stringify(receipt, null, 2),
  );
  console.log(
    JSON.stringify({
      status: receipt.status,
      error: receipt.error,
      checks: receipt.checks,
      captures: receipt.captures.length,
      external: receipt.externalRequests,
      errors: receipt.browserErrors,
    }),
  );
}
