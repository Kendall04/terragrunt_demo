// Explicit public DEMO verification. GET/HEAD only; no AWS credentials or runtime API.
import assert from "node:assert/strict";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { catalog } from "./diagrams.mjs";
import { CSP_DEMO } from "./server.mjs";
import { diagramPolicy } from "../archify.mjs";

const [origin, packageDirectory, destination] = process.argv.slice(2);
assert(/^https:\/\/[a-z0-9]+\.cloudfront\.net$/.test(origin || ""));
assert(
  packageDirectory &&
    destination &&
    process.env.PLAYWRIGHT_MODULE &&
    process.env.CHROME_EXECUTABLE,
);
await mkdir(destination, { recursive: true });
assert.equal(
  (await readdir(destination)).length,
  0,
  "Preserve previous receipts",
);
const expected = JSON.parse(
  await readFile(path.join(packageDirectory, "MANIFEST.json"), "utf8"),
);
assert.equal(expected.edition, "demo");
assert.equal(expected.awsCredentials, false);
assert.equal(expected.awsProxy, false);
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const receipt = {
  schema: "ECS_PUBLIC_DEMO_HTTPS_V1",
  at: new Date().toISOString(),
  origin,
  contentSHA256: expected.contentSHA256,
  result: "INCOMPLETE",
  checks: [],
  assets: [],
  requests: [],
  captures: [],
  externalRequests: [],
  apiRequests: [],
  browserErrors: [],
};
const { chromium, request } = await import(
  pathToFileURL(process.env.PLAYWRIGHT_MODULE)
);
const http = await request.newContext({
  baseURL: origin,
  timeout: 30000,
  maxRedirects: 0,
});
let browser;
const pass = (check) => receipt.checks.push(check);
async function get(uri, status = 200) {
  const response = await http.get(uri);
  assert.equal(response.status(), status, uri);
  assert.equal(response.url(), origin + uri, "No redirects to another origin");
  const headers = response.headers();
  receipt.requests.push({
    uri,
    status: response.status(),
    mime: headers["content-type"],
    csp: headers["content-security-policy"],
    cache: headers["x-cache"],
  });
  assert.equal(headers["x-content-type-options"], "nosniff");
  assert.equal(headers["referrer-policy"], "no-referrer");
  assert.equal(headers["strict-transport-security"], "max-age=31536000");
  const isDiagram = uri.startsWith("/diagrams/") || uri.startsWith("/reading/");
  assert.equal(
    headers["content-security-policy"],
    isDiagram
      ? diagramPolicy + "; frame-ancestors 'self'; sandbox allow-scripts"
      : CSP_DEMO,
  );
  return response;
}
async function capture(page, name) {
  await page.evaluate(() => document.fonts.ready);
  if (await page.locator("#diagram-frame").count()) {
    await page.locator("#diagram-frame").scrollIntoViewIfNeeded();
    const frame = await (await page.locator("#diagram-frame").elementHandle()).contentFrame();
    await frame.evaluate(() => document.fonts.ready);
    await frame.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  }
  const bytes = await page.screenshot({
    path: path.join(destination, name + ".png"),
    fullPage: true,
  });
  receipt.captures.push({ file: name + ".png", sha256: sha(bytes) });
}
try {
  const manifestResponse = await get("/MANIFEST.json");
  assert.deepEqual(await manifestResponse.json(), expected);
  for (const entry of expected.files) {
    const r = await get("/" + entry.path);
    const bytes = await r.body();
    assert.equal(bytes.length, entry.bytes, entry.path);
    assert.equal(sha(bytes), entry.sha256, entry.path);
    const extension = path.extname(entry.path);
    const mime = {
      ".html": "text/html",
      ".mjs": "text/javascript",
      ".css": "text/css",
      ".ttf": "font/ttf",
      ".txt": "text/plain",
      ".json": "application/json",
    }[extension];
    assert(r.headers()["content-type"].startsWith(mime), entry.path);
    receipt.assets.push({
      path: entry.path,
      sha256: entry.sha256,
      bytes: bytes.length,
    });
  }
  pass("Every public byte matches sealed DEMO package, MIME and distinct CSP");
  for (const uri of [
    "/not-a-route",
    "/_api/text",
    "/server.mjs",
    "/proxy.mjs",
    "/.aws/credentials",
    "/demo/missing",
  ]) {
    const r = await get(uri, 404);
    assert.equal(await r.text(), "Not found");
  }
  for (const uri of [
    "/",
    "/demo",
    "/demo/",
    "/architecture",
    "/architecture/",
    "/resilience",
    "/evidence",
  ])
    await get(uri);
  pass(
    "Direct routes, trailing routes and genuine 404; no proxy/private assets",
  );

  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_EXECUTABLE,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      receipt.externalRequests.push(url.href);
      return route.abort();
    }
    if (url.pathname.startsWith("/_api")) {
      receipt.apiRequests.push(url.pathname);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => receipt.browserErrors.push(e.message));
  for (const width of [320, 390, 768, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    for (const uri of [
      "/",
      "/demo",
      "/architecture",
      "/resilience",
      "/evidence",
    ]) {
      assert.equal((await page.goto(origin + uri)).status(), 200);
      await page.locator("h1").waitFor();
      assert.equal((await page.reload()).status(), 200);
      await page.locator("h1").waitFor();
      assert.equal(await page.locator("h1").count(), 1);
      assert(await page.locator("#global-mode").isVisible());
      await page.evaluate(() => document.fonts.ready);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        `${width}${uri}`,
      );
      if (width === 1440 || width === 390)
        await capture(page, `public-${width}-${uri.slice(1) || "overview"}`);
    }
  }
  pass(
    "Five public pages, direct navigation/refresh, 320/390/768/1440/1920 layout",
  );
  await page.goto(origin + "/demo");
  await page.keyboard.press("Tab");
  assert(
    await page.locator(".skip").evaluate((n) => n === document.activeElement),
  );
  await page.keyboard.press("Enter");
  assert(
    await page.locator("main").evaluate((n) => n === document.activeElement),
  );
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const uri of [
      "/architecture",
      "/resilience",
      "/evidence",
      "/demo",
      "/",
    ]) {
      const menu = page.locator("#menu-toggle");
      if (await menu.isVisible()) await menu.click();
      await page.locator(`#side-nav a[href="${uri}"]`).click();
      assert.equal(new URL(page.url()).pathname, uri);
      assert(
        await page.locator("h1").evaluate((n) => n === document.activeElement),
      );
    }
  }
  pass("Public navigation desktop/mobile and keyboard focus/skip link");
  await page.goto(origin + "/demo");
  const message = "CloudFront DEMO · synthetic local-only message";
  await page.locator("#message").fill(message);
  await page.locator("#send").click();
  await page.locator(".message-row").filter({ hasText: message }).waitFor();
  await page.locator("#reset").click();
  assert.equal(await page.locator(".message-row").count(), 2);
  pass("Public DEMO create/read/reset in memory, no backend calls");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(origin + "/architecture");
    for (const d of await catalog()) {
      await page.locator("#diagram-select").selectOption(d.id);
      assert.equal(
        await page.locator("#diagram-frame").getAttribute("sandbox"),
        "allow-scripts",
      );
      const frame = await (
        await page.locator("#diagram-frame").elementHandle()
      ).contentFrame();
      await frame.waitForURL("**/diagrams/" + d.id + ".html");
      await frame.locator("svg [data-node-id]").first().waitFor();
      assert(
        await frame.evaluate(() => {
          try {
            parent.document.body;
            return false;
          } catch {
            return true;
          }
        }),
      );
      await frame.locator(".diagram-nav [data-view=reset]").click();
      const node = frame.locator("svg [data-node-id]").first();
      const before = await node.evaluate(
        (n) => n.getBoundingClientRect().width,
      );
      await frame.locator(".diagram-nav [data-view=in]").click();
      await frame.waitForFunction(
        (w) =>
          document.querySelector("svg [data-node-id]").getBoundingClientRect()
            .width > w,
        before,
      );
      await frame.locator(".diagram-nav [data-view=reset]").click();
      if (!d.historical)
        await capture(page, `public-${width}-${d.id}`);
    }
    await page.locator("#diagram-select").selectOption("ecs-delivery");
    await page
      .getByRole("button", { name: "Hoja de lectura", exact: true })
      .click();
    const reader = await (
      await page.locator("#diagram-frame").elementHandle()
    ).contentFrame();
    await reader.waitForURL("**/reading/ecs-delivery.html");
    await reader.locator("article").first().waitFor();
    assert.equal(await reader.locator("a[href]").count(), 0);
  }
  pass("17 public diagrams desktop/mobile: zoom/fit, opaque iframe and reader");
  await page.goto(origin + "/resilience");
  for (const label of ["NAT / E13", "SQL recovery", "Backups SQL"]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await page
      .getByRole("button", { name: "Paso siguiente", exact: true })
      .click();
    assert.equal(await page.locator("progress").getAttribute("value"), "1");
    await page.getByRole("button", { name: "Reiniciar", exact: true }).click();
  }
  pass("Three public historical replays, with no AWS mutation");
  assert.deepEqual(receipt.externalRequests, []);
  assert.deepEqual(receipt.apiRequests, []);
  assert.deepEqual(receipt.browserErrors, []);
  pass("Zero external/API calls and zero JavaScript errors");
  receipt.result = "PASS";
} catch (error) {
  receipt.result = "FAIL";
  receipt.error = error.message;
  throw error;
} finally {
  await browser?.close();
  await http.dispose();
  receipt.finishedAt = new Date().toISOString();
  await writeFile(
    path.join(destination, "PUBLIC-HTTPS-QA.json"),
    JSON.stringify(receipt, null, 2) + "\n",
  );
  console.log(
    JSON.stringify({
      result: receipt.result,
      assets: receipt.assets.length,
      checks: receipt.checks,
      externalRequests: receipt.externalRequests.length,
      apiRequests: receipt.apiRequests.length,
      error: receipt.error,
    }),
  );
}
