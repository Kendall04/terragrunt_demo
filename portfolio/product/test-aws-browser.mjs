// MANUAL, real AWS. Never imported by CI. No retries, no load test.
import assert from "node:assert/strict";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { randomBytes, randomUUID, createHash } from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createProductServer } from "./server.mjs";
import { AWS_ENDPOINT, LAB_END } from "./proxy.mjs";
const mode = process.argv[2];
assert(
  ["--readback", "--write-once"].includes(mode),
  "Choose --readback or an independently authorized --write-once",
);
assert.equal(
  process.env.ECS_AWS_BROWSER_TEST,
  "CONFIRMED_DEV_SYNTHETIC",
  "Confirm identity/window/budget first; see README",
);
assert(Date.now() < LAB_END - 15 * 60000, "Insufficient authorized window");
const destination = process.env.UI_EVIDENCE_DIRECTORY;
assert(
  destination && process.env.PLAYWRIGHT_MODULE && process.env.CHROME_EXECUTABLE,
);
await mkdir(destination, { recursive: true });
assert.equal(
  (await readdir(destination)).length,
  0,
  "New private evidence directory required",
);
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
let expected;
if (mode === "--readback") {
  expected = JSON.parse(
    await readFile(process.env.ECS_PRIOR_AWS_RECEIPT, "utf8"),
  ).row;
  assert(
    Number.isInteger(expected.id) && /^[a-f0-9]{64}$/.test(expected.textSHA256),
  );
}
const receipt = {
  kind: "AUTHENTIC_AWS_BROWSER",
  at: new Date().toISOString(),
  mode,
  endpoint: AWS_ENDPOINT,
  calls: [],
  postAttempts: 0,
  errors: [],
  sourceHashes: {},
};
for (const file of [
  "app.mjs",
  "api.mjs",
  "data.mjs",
  "style.css",
  "proxy.mjs",
  "server.mjs",
  "diagrams.mjs",
  "test-aws-browser.mjs",
])
  receipt.sourceHashes[file] = hash(
    await readFile(new URL(file, import.meta.url)),
  );
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const token = randomBytes(32).toString("hex");
const server = createProductServer({
  mode: "aws",
  token,
  onReceipt: (r) => receipt.calls.push(r),
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_EXECUTABLE,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
    timezoneId: "America/Costa_Rica",
  });
  // Browser sees only loopback; the bounded server contacts the fixed AWS API.
  await context.route("**/*", (r) =>
    new URL(r.request().url()).origin === origin ? r.continue() : r.abort(),
  );
  const page = await context.newPage();
  page.on("pageerror", (e) => receipt.errors.push(e.message));
  await page.goto(origin + "/demo#session=" + token);
  await page
    .getByRole("button", { name: "Comprobar conexión", exact: true })
    .click();
  await page
    .locator("#health-result")
    .filter({ hasText: "SQL + KMS" })
    .waitFor();
  if (mode === "--write-once") {
    const text = "ECS-V2-UI-" + randomUUID() + " · prueba sintética";
    await page.locator("#message").fill(text);
    const response = page.waitForResponse(
      (r) =>
        r.url() === origin + "/_api/text" && r.request().method() === "POST",
    );
    receipt.postAttempts++;
    await page.locator("#send").click();
    const posted = await response;
    assert.equal(posted.status(), 200);
    const row = await posted.json();
    assert.equal(row.text, text);
    assert(Number.isInteger(row.id));
    expected = { id: row.id, createdAt: row.createdAt, textSHA256: hash(text) };
    receipt.row = expected;
  }
  const response = page.waitForResponse(
    (r) => r.url() === origin + "/_api/text?page=1&pageSize=5",
  );
  await page.locator("#refresh").click();
  const read = await response;
  assert.equal(read.status(), 200);
  const rows = await read.json();
  const row = rows.find((x) => x.id === expected.id);
  assert(
    row,
    "Expected synthetic record not in this bounded page; no broad enumeration",
  );
  assert.equal(hash(row.text), expected.textSHA256);
  const item = page.locator(`.message-row[data-id="${row.id}"]`);
  await item.waitFor();
  assert((await item.innerText()).includes(row.text));
  // UTC presentation must be independent of the browser's Costa Rica timezone.
  assert.equal(
    await item.locator("time").innerText(),
    expected.createdAt.slice(0, 19).replace("T", " ") + " UTC",
    "UTC text must match the stored timestamp",
  );
  await page.locator(".message-row").evaluateAll((els, id) => {
    for (const e of els)
      if (e.dataset.id !== String(id))
        e.querySelector("p").textContent =
          "[registro anterior oculto en evidencia]";
  }, row.id);
  const bytes = await page.screenshot({
    path: path.join(destination, "aws-real-desktop.png"),
    fullPage: true,
  });
  receipt.captureSHA256 = hash(bytes);
  receipt.row = expected;
  receipt.persistedReadback = true;
  receipt.uiVerified = true;
  receipt.utcVerified = true;
  assert.deepEqual(receipt.errors, []);
  receipt.status = "PASS";
} catch (e) {
  receipt.status = "FAIL";
  receipt.error = e.message;
  process.exitCode = 1;
} finally {
  await browser?.close();
  await new Promise((r) => server.close(r));
  await writeFile(
    path.join(destination, "receipt.private.json"),
    JSON.stringify(receipt, null, 2) + "\n",
  );
  console.log(
    JSON.stringify({
      status: receipt.status,
      error: receipt.error,
      calls: receipt.calls,
      postAttempts: receipt.postAttempts,
      row: receipt.row,
    }),
  );
}
