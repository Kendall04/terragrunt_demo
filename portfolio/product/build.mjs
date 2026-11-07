import { readFile, mkdir, writeFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { catalog, diagramAsset } from "./diagrams.mjs";
import { CSP_DEMO } from "./server.mjs";
const sha = (x) => createHash("sha256").update(x).digest("hex");
export async function staticFiles() {
  const files = new Map();
  for (const name of ["app.mjs", "api.mjs", "data.mjs", "style.css"])
    files.set("assets/" + name, await readFile(new URL(name, import.meta.url)));
  files.set("assets/config.mjs", Buffer.from('export const edition="demo";'));
  let html = await readFile(new URL("index.html", import.meta.url), "utf8");
  html = html.replace(
    "<head>",
    '<head><meta http-equiv="Content-Security-Policy" content="' +
      CSP_DEMO +
      '">',
  );
  files.set("index.html", Buffer.from(html));
  for (const route of ["demo", "architecture", "resilience", "evidence"])
    files.set(route + "/index.html", Buffer.from(html));
  const diagrams = await catalog();
  for (const d of diagrams) {
    for (const route of [
      "/diagrams/" + d.id + ".html",
      "/sources/" + d.id + ".json",
      ...(!d.historical ? ["/reading/" + d.id + ".html"] : []),
    ]) {
      const asset = await diagramAsset(route);
      files.set(route.slice(1), Buffer.from(asset.body));
    }
  }
  files.set(
    "assets/atlas.mjs",
    Buffer.from((await diagramAsset("/assets/atlas.mjs")).body),
  );
  // Instructions for a future host, never an automatic deployment or proxy.
  files.set(
    "HOSTING.json",
    Buffer.from(
      JSON.stringify(
        {
          edition: "demo",
          awsProxyIncluded: false,
          apiCallsAllowed: false,
          spaRoutes: ["/demo", "/architecture", "/resilience", "/evidence"],
          rewrite:
            "Only these exact paths (and trailing slash) to their index.html. Unknown paths return 404; never rewrite /_api.",
          headers: {
            appCSP: CSP_DEMO,
            referrerPolicy: "no-referrer",
            nosniff: true,
          },
          isolation:
            "Diagram frames require sandbox=allow-scripts without allow-same-origin; their embedded CSP is stricter.",
        },
        null,
        2,
      ) + "\n",
    ),
  );
  return files;
}
export async function build(destination) {
  const files = await staticFiles();
  await mkdir(destination, { recursive: true });
  if ((await readdir(destination)).length)
    throw new Error("Build destination must be empty");
  const entries = [];
  for (const [p, bytes] of [...files].sort(([a], [b]) =>
    a.localeCompare(b, "en"),
  )) {
    const out = path.join(destination, p);
    await mkdir(path.dirname(out), { recursive: true });
    await writeFile(out, bytes);
    entries.push({ path: p, bytes: bytes.length, sha256: sha(bytes) });
  }
  const manifest = {
    schema: "ECS_PORTFOLIO_STATIC_V1",
    edition: "demo",
    files: entries,
    contentSHA256: sha(JSON.stringify(entries)),
    awsCredentials: false,
    awsProxy: false,
  };
  await writeFile(
    path.join(destination, "MANIFEST.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  return manifest;
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  if (process.argv.length !== 3)
    throw new Error(
      "Usage: node portfolio/product/build.mjs <new-empty-directory>",
    );
  console.log(JSON.stringify(await build(path.resolve(process.argv[2]))));
}
