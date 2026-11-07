import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { functions, template } from "./template.mjs";
import { staticFiles } from "../build.mjs";
import { paygTemplate } from "./payg-template.mjs";
test("pay-as-you-go is an explicit alternative with identical origin, routes and CSP", async () => {
  const a = await template(),
    b = await paygTemplate();
  assert.equal(Object.keys(b.Resources).length, 6);
  assert(!b.Resources.WebACL && !b.Resources.FreeSubscription);
  assert.deepEqual(b.Resources.Assets, a.Resources.Assets);
  assert.deepEqual(b.Resources.BucketPolicy, a.Resources.BucketPolicy);
  assert.deepEqual(b.Resources.Routes, a.Resources.Routes);
  assert.deepEqual(b.Resources.Headers, a.Resources.Headers);
  assert.deepEqual(
    b.Resources.Distribution.Properties.DistributionConfig.Origins,
    a.Resources.Distribution.Properties.DistributionConfig.Origins,
  );
});

test("edge routes: exact public assets, real 404, no API or arbitrary origin", async () => {
  const code = (await functions()).request;
  const context = vm.createContext({});
  new vm.Script(code).runInContext(context);
  function request(uri, method = "GET") {
    return context.handler({
      request: {
        uri,
        method,
        headers: {},
        querystring: { diagram: { value: "v2-sentinel" } },
      },
    });
  }
  for (const p of [
    "/",
    "/demo",
    "/demo/",
    "/architecture",
    "/resilience",
    "/evidence",
  ])
    assert.match(request(p).uri, /index.html$/);
  for (const p of (await staticFiles()).keys())
    assert.equal(request("/" + p).uri, "/" + p);
  for (const p of [
    "/_api/text",
    "/unknown",
    "/demo/missing",
    "//example.com",
    "/assets/../proxy.mjs",
    "/%2e%2e/.aws/credentials",
    "/constructor",
    "/__proto__",
  ]) {
    const r = request(p);
    assert.equal(r.statusCode, 404, p);
    assert.match(
      r.headers["content-security-policy"].value,
      /connect-src 'none'/,
    );
  }
  assert.equal(request("/demo", "POST").statusCode, 405);
  assert.equal(request("/demo", "HEAD").uri, "/demo/index.html");
});
test("edge headers preserve distinct opaque Archify CSP without weakening app policy", async () => {
  const context = vm.createContext({});
  new vm.Script((await functions()).response).runInContext(context);
  for (const uri of [
    "/index.html",
    "/demo/index.html",
    "/diagrams/v2-sentinel.html",
    "/reading/v2-sentinel.html",
  ]) {
    const r = context.handler({
      request: { uri },
      response: { statusCode: 200, headers: {} },
    });
    const c = r.headers["content-security-policy"].value;
    assert.match(c, /connect-src 'none'/);
    assert.doesNotMatch(c, /unsafe-eval|allow-same-origin/);
    if (uri.startsWith("/diagrams") || uri.startsWith("/reading")) {
      assert.match(c, /sandbox allow-scripts/);
      assert.match(c, /frame-ancestors 'self'/);
    } else {
      assert.doesNotMatch(c, /unsafe-inline/);
      assert.match(c, /frame-ancestors 'none'/);
    }
    assert.equal(r.headers["x-content-type-options"].value, "nosniff");
  }
});
test("hosting stack is isolated, private, FREE, initially disabled, with no runtime or IAM roles", async () => {
  const t = await template(),
    r = t.Resources;
  assert.equal(Object.keys(r).length, 8);
  assert.equal(r.FreeSubscription.Properties.PlanTier, "FREE");
  assert.equal(t.Parameters.Enabled.Default, "false");
  assert.equal(r.Assets.DeletionPolicy, "Retain");
  assert(
    Object.values(r.Assets.Properties.PublicAccessBlockConfiguration).every(
      (v) => v === true,
    ),
  );
  assert.equal(
    r.OriginAccess.Properties.OriginAccessControlConfig.SigningBehavior,
    "always",
  );
  const d = r.Distribution.Properties.DistributionConfig;
  assert.equal(d.Origins.length, 1);
  assert(d.Origins[0].S3OriginConfig);
  assert(!d.CustomErrorResponses);
  assert(!d.DefaultCacheBehavior.ResponseHeadersPolicyId);
  assert(
    !Object.values(r).some((x) =>
      /IAM|EC2|ECS|Lambda|SecretsManager/.test(x.Type),
    ),
  );
  const allow = r.BucketPolicy.Properties.PolicyDocument.Statement[0];
  assert.equal(allow.Action, "s3:GetObject");
  assert(allow.Condition.StringEquals["AWS:SourceArn"]);
  assert(Buffer.byteLength(JSON.stringify(t)) < 51200);
});
