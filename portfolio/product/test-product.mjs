import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { randomBytes } from "node:crypto";
import { readFile, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {
  createDemo,
  createAws,
  parseText,
  utcTimestamp,
  validText,
} from "./api.mjs";
import { createProductServer } from "./server.mjs";
import { proxyHandler, AWS_ENDPOINT, LAB_END } from "./proxy.mjs";
import { catalog, diagramAsset } from "./diagrams.mjs";
import { build, staticFiles } from "./build.mjs";
import { createPreview } from "./preview.mjs";
test("memory demo supports text/XSS literals, pagination and reset without fetch", async () => {
  const old = globalThis.fetch;
  globalThis.fetch = () => {
    throw new Error("DEMO network");
  };
  try {
    const api = createDemo();
    assert.equal((await api.list()).length, 2);
    const row = await api.create("<img src=x onerror=alert(1)>");
    assert.equal((await api.list(1, 1))[0].text, row.text);
    assert.equal((await api.list(2, 1))[0].id, 2);
    api.reset();
    assert.equal((await api.list()).length, 2);
    assert.equal((await api.health()).live, "Simulado");
  } finally {
    globalThis.fetch = old;
  }
});
test("UTF8 API limit, schema and UTC timestamp contract", () => {
  assert.throws(() => validText(" "));
  assert.throws(() => validText("🔒".repeat(1025)));
  assert.equal(validText("🔒".repeat(1024)).length, 2048);
  assert.throws(() =>
    parseText({ id: 0, text: "bad", createdAt: "2026-11-07T01:10:08" }),
  );
  assert.equal(
    parseText({ id: 6, text: "x", createdAt: "2026-11-07T01:10:08.7073381" })
      .createdAt,
    "2026-11-07T01:10:08.7073381Z",
  );
  assert.equal(utcTimestamp("2026-11-07T01:10:08Z"), "2026-11-07T01:10:08Z");
  assert.throws(() => utcTimestamp("yesterday"));
});
test("AWS client never retries writes or falls back on HTTP/timeout/malformed response", async () => {
  let count = 0;
  const fail = createAws("token", async () => {
    count++;
    return new Response("{}", { status: 503 });
  });
  await assert.rejects(fail.create("synthetic"), /HTTP 503/);
  assert.equal(count, 1);
  await assert.rejects(createAws("").list(), /bloqueada/);
  await assert.rejects(
    createAws("t", async () => new Response("{}", { status: 200 })).list(),
    /página inválida/,
  );
  const hang = createAws(
    "t",
    (_u, o) =>
      new Promise((_, reject) =>
        o.signal.addEventListener("abort", () =>
          reject(new DOMException("test", "AbortError")),
        ),
      ),
    5,
  );
  await assert.rejects(hang.list(), /espera agotado/);
});
async function withServer(options, body) {
  const s = createProductServer({
    ...options,
    now: () => Date.parse("2026-11-07T01:00:00Z"),
  });
  await new Promise((r) => s.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${s.address().port}`;
  try {
    await body(origin, s);
  } finally {
    await new Promise((r) => s.close(r));
  }
}
function request(origin, route, { method = "GET", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(origin);
    const r = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: route,
        method,
        headers,
        agent: false,
      },
      (res) => {
        const chunks = [];
        res.on("data", (x) => chunks.push(x));
        res.on("end", () =>
          resolve({
            status: res.statusCode,
            headers: res.headers,
            text: Buffer.concat(chunks).toString(),
          }),
        );
      },
    );
    r.on("error", (e) => {
      e.message = `${method} ${route}: ${e.message}`;
      reject(e);
    });
    r.end(body);
  });
}
test("DEMO server has no API/proxy, blocks traversal and sensitive files, CSP no connect", async () =>
  withServer({}, async (origin) => {
    const r = await request(origin, "/demo");
    assert.equal(r.status, 200);
    assert.match(r.headers["content-security-policy"], /connect-src 'none'/);
    assert.equal(
      (await request(origin, "/assets/config.mjs")).text,
      'export const edition="demo";',
    );
    for (const p of [
      "/_api/text?page=1&pageSize=5",
      "/.aws/credentials",
      "/server.mjs",
      "/sources/unknown.json",
      "/../.git/config",
    ])
      assert.equal((await request(origin, p)).status, 404, p);
    for (const p of [
      "//example.org/",
      "http://example.org/",
      "/%2e%2e/.git/config",
    ])
      assert.equal((await request(origin, p)).status, 400);
    assert.equal(
      (await request(origin, "/demo", { headers: { Host: "evil.example" } }))
        .status,
      400,
    );
    assert.equal(
      (await request(origin, "/demo", { method: "POST" })).status,
      405,
    );
    assert.equal((await request(origin, "/demo", { method: "HEAD" })).text, "");
  }));
test("proxy authorizes local capability, exact origin/routes/body and bounded requests", async () => {
  const token = randomBytes(32).toString("hex"),
    seen = [];
  await withServer(
    {
      mode: "aws",
      token,
      fetcher: async (url, options) => {
        seen.push({ url, options });
        return new Response(
          JSON.stringify({
            id: 1,
            text: "test",
            createdAt: "2026-11-07T00:00:00Z",
          }),
          { headers: { "Content-Type": "application/json" } },
        );
      },
    },
    async (origin) => {
      const headers = {
        "X-ECS-Session": token,
        Origin: origin,
        "Content-Type": "application/json",
      };
      assert.equal((await request(origin, "/_api/ready")).status, 403);
      assert.equal(
        (
          await request(origin, "/_api/ready", {
            headers: { ...headers, Origin: "https://evil.example" },
          })
        ).status,
        403,
      );
      assert.equal(
        (
          await request(origin, "/_api/ready", {
            headers: { ...headers, "Sec-Fetch-Site": "cross-site" },
          })
        ).status,
        403,
      );
      assert.equal(
        (await request(origin, "/_api/text?page=1&pageSize=100", { headers }))
          .status,
        400,
      );
      assert.equal(
        (
          await request(origin, "/_api/text?page=1&page=2&pageSize=5", {
            headers,
          })
        ).status,
        400,
      );
      assert.equal(
        (await request(origin, "/_api/http://example.org", { headers })).status,
        404,
      );
      assert.equal(
        (
          await request(origin, "/_api/text", {
            headers,
            method: "POST",
            body: '{"text":"test","url":"https://evil.example"}',
          })
        ).status,
        400,
      );
      assert.equal(
        (
          await request(origin, "/_api/text", {
            headers: {
              "X-ECS-Session": token,
              "Content-Type": "application/json",
            },
            method: "POST",
            body: "{}",
          })
        ).status,
        403,
      );
      for (let i = 0; i < 2; i++)
        assert.equal(
          (
            await request(origin, "/_api/text", {
              headers,
              method: "POST",
              body: '{"text":"test"}',
            })
          ).status,
          200,
        );
      assert.equal(
        (
          await request(origin, "/_api/text", {
            headers,
            method: "POST",
            body: '{"text":"test"}',
          })
        ).status,
        429,
      );
      assert.equal(seen.length, 2);
      for (const r of seen) {
        assert.equal(r.url, AWS_ENDPOINT + "/text");
        assert.equal(r.options.redirect, "error");
        assert(!("X-ECS-Session" in r.options.headers));
      }
    },
  );
});
test("expired proxy and closure fail before external dispatch", async () => {
  let calls = 0;
  const handler = proxyHandler({
    token: "a".repeat(64),
    expires: LAB_END,
    now: () => LAB_END,
    fetcher: () => calls++,
  });
  let code;
  await handler(
    { headers: { "x-ecs-session": "a".repeat(64) } },
    { writeHead: (n) => (code = n), end: () => {} },
    new URL("http://127.0.0.1/_api/ready"),
    "http://127.0.0.1",
  );
  assert.equal(code, 403);
  assert.equal(calls, 0);
});

test("concurrent POST bodies cannot exceed the session write ceiling", async () => {
  const token = randomBytes(32).toString("hex");
  let calls = 0;
  await withServer(
    {
      mode: "aws",
      token,
      fetcher: async () => {
        calls++;
        await new Promise((r) => setTimeout(r, 15));
        return new Response("{}", {
          headers: { "content-type": "application/json" },
        });
      },
    },
    async (origin) => {
      const results = await Promise.all(
        Array.from({ length: 3 }, () =>
          request(origin, "/_api/text", {
            method: "POST",
            headers: {
              "X-ECS-Session": token,
              Origin: origin,
              "Content-Type": "application/json",
            },
            body: '{"text":"synthetic"}',
          }),
        ),
      );
      assert.deepEqual(results.map((r) => r.status).sort(), [200, 200, 429]);
      assert.equal(calls, 2);
    },
  );
});
test("seven V2 / five historical diagrams, source pins and opaque isolated derivatives", async () => {
  const all = await catalog();
  assert.equal(all.filter((x) => !x.historical).length, 7);
  assert.equal(all.filter((x) => x.historical).length, 5);
  for (const d of all) {
    assert(d.nodes.length);
    assert(
      d.nodes.every((n) =>
        n.sources.every((s) =>
          s.url.startsWith(
            "https://github.com/Kendall04/terragrunt_demo/blob/",
          ),
        ),
      ),
    );
    const a = await diagramAsset("/diagrams/" + d.id + ".html");
    assert.match(a.policy, /connect-src 'none'/);
    assert.match(a.body, /data-present="true"/);
    assert.doesNotMatch(a.body, /<a[^>]*href=|<script[^>]*src=/);
    assert((await diagramAsset("/sources/" + d.id + ".json")).body.length);
    if (!d.historical)
      assert((await diagramAsset("/reading/" + d.id + ".html")).body.length);
  }
  assert.equal(await diagramAsset("/diagrams/unknown.html"), null);
});
test("static DEMO package is reproducible, separate from runtime proxy and AWS credentials", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ecs-product-test-"));
  try {
    const a = await build(path.join(dir, "a")),
      b = await build(path.join(dir, "b"));
    assert.deepEqual(a, b);
    assert.equal(a.edition, "demo");
    const files = await staticFiles();
    assert.equal(
      files.get("assets/config.mjs").toString(),
      'export const edition="demo";',
    );
    assert(
      ![...files.keys()].some((p) =>
        /server|proxy|test-|private|\.env/.test(p),
      ),
    );
    assert(
      ![...files.values()].some((b) =>
        /AKIA[0-9A-Z]{16}|BEGIN (?:RSA )?PRIVATE KEY/.test(b.toString()),
      ),
    );
    assert.match(files.get("index.html").toString(), /connect-src 'none'/);
    await assert.rejects(build(path.join(dir, "a")), /empty/);
  } finally {
    await rm(dir, { recursive: true });
  }
});
test("UI keeps mode explicit, uses textContent for user text, isolated frames and historical limitations", async () => {
  const app = await readFile(new URL("app.mjs", import.meta.url), "utf8");
  const data = await readFile(new URL("data.mjs", import.meta.url), "utf8");
  assert.doesNotMatch(app, /innerHTML|localStorage|sessionStorage/);
  assert.match(app, /sandbox:\s*["']allow-scripts["']/);
  assert.doesNotMatch(app, /allow-same-origin/);
  assert.match(app, /e.source\s*!==\s*frame.contentWindow/);
  assert.match(app, /e.origin\s*!==\s*["']null["']/);
  assert.match(data, /No hubo correo de caída/);
  assert.match(data, /no.*RPO cero/);
});

test("built package previews exact routes, refuses API and detects changed bytes", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "ecs-static-test-"));
  let server;
  try {
    await build(dir);
    server = await createPreview(dir);
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    const origin = `http://127.0.0.1:${server.address().port}`;
    for (const p of ["/", "/demo", "/demo/", "/architecture?view=v2-sentinel"])
      assert.equal((await request(origin, p)).status, 200);
    for (const p of ["/_api/ready", "/proxy.mjs", "/unknown"])
      assert.equal((await request(origin, p)).status, 404);
    assert.match(
      (await request(origin, "/diagrams/v2-sentinel.html")).headers[
        "content-security-policy"
      ],
      /connect-src 'none'/,
    );
    await writeFile(
      path.join(dir, "assets/config.mjs"),
      'export const edition="aws";',
    );
    assert.equal((await request(origin, "/assets/config.mjs")).status, 503);
  } finally {
    if (server) await new Promise((r) => server.close(r));
    await rm(dir, { recursive: true });
  }
});
