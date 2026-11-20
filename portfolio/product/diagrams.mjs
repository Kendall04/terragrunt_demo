// Five current presentation derivatives; authentic generation pins remain unchanged.
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { adaptArchify, diagramPolicy } from "../archify.mjs";
const root = new URL("../../docs/interactive/", import.meta.url);
const current = JSON.parse(await readFile(new URL("GENERATION-CURRENT.json", root), "utf8"));
const entries = [
  ["ecs-platform", "Plataforma ECS", "Del cliente al SQL privado", "API Gateway, ALB y colores intercambiables; KMS, SQL TLS y backups. Evidencia DEV; PROD no validado."],
  ["ecs-delivery", "CD DEV automático", "Un merge despliega DEV", "Ocho etapas: CI, build, ECR por digest, ECS, salud, ALB y registro S3/GitHub. Terraform separado; PROD deshabilitado."],
  ["ecs-network", "Red y NAT / E13", "Dos zonas, recuperación independiente", "ECS elegible en ambas AZ, SQL en B. ASG/E13 repara cada NAT; no implica failover entre zonas."],
  ["ecs-sql-recovery", "Backups y recuperación SQL", "Un escritor, copias verificables", "Backups horarios y recuperación fría SAME-AZ/CROSS-AZ supervisada."],
  ["ecs-trust", "Identidades y TLS", "Confianza por ambiente", "Fronteras de acceso privado, ejecución ECS y administración/backup. CA DEV definitiva; API pública sin autenticación."],
];
const sha = (b) => createHash("sha256").update(b).digest("hex");
const cache = new Map();
async function sourceBytes(id) {
  const b = await readFile(new URL("source/" + id + ".json", root));
  const pin = current.diagrams.find((x) => x.id === id);
  if (!pin || sha(b) !== pin.sourceSha256) throw new Error("Changed diagram source");
  return b;
}
export async function catalog() {
  return Promise.all(
    entries.map(async ([id, label, title, description]) => {
      const bytes = await sourceBytes(id);
      const spec = JSON.parse(bytes);
      const v2 = current.diagrams.find((x) => x.id === id);
      return {
        id,
        label,
        title,
        description,
        historical: false,
        reading: Boolean(v2),
        sha256: v2.htmlSha256,
        nodes: (spec.components ?? spec.events).map((n) => ({
          id: n.id,
          name: n.label ?? n.title ?? n.id,
          detail: n.sublabel ?? n.description ?? "",
          status: n.tag ? [n.tag] : (n.tags ?? []),
          sources: (n.sources ?? []).map((s) => ({
            path: s.path,
            line: s.line,
            url: `https://github.com/Kendall04/terragrunt_demo/blob/${spec.meta.repository.revision}/${s.path}#L${s.line}`,
          })),
        })),
        relations: (spec.connections ?? []).map((x) => ({
          from: x.from,
          to: x.to,
          label: x.label,
        })),
      };
    }),
  );
}
export async function diagramAsset(route) {
  if (cache.has(route)) return cache.get(route);
  let asset;
  if (route === "/assets/atlas.mjs")
    asset = {
      body: "export const atlas=" + JSON.stringify(await catalog()) + ";",
      type: "text/javascript",
    };
  else {
    const id = route
      .split("/")
      .at(-1)
      .replace(/\.(html|json)$/, "");
    if (!entries.some((x) => x[0] === id)) return null;
    const v2 = current.diagrams.find((x) => x.id === id);
    if (route.startsWith("/sources/"))
      asset = { body: await sourceBytes(id), type: "application/json" };
    else if (route.startsWith("/reading/")) {
      if (!v2) return null;
      let sheet = await readFile(
        new URL("readable/" + id + ".html", root),
        "utf8",
      );
      const pin = v2;
      if (sha(sheet) !== (pin.readingSha256 ?? pin.htmlSha256))
        throw new Error("Changed accepted reading sheet");
      sheet = sheet.replace("Los doce diagramas históricos conservan sus bytes.", "");
      sheet = sheet.replace(
        /(<a\b[^>]*?)\s+href="[^"]*"/g,
        '$1 aria-disabled="true"',
      );
      asset = { body: sheet, type: "text/html", policy: diagramPolicy };
    } else {
      const raw = await readFile(new URL(id + ".html", root));
      let html = adaptArchify(
        raw,
        v2.htmlSha256,
      );
      html = html.replace(
        "</body>",
        `<script>document.documentElement.setAttribute('data-theme','dark');document.addEventListener('click',function(e){var n=e.target.closest('[data-node-id]');if(n)parent.postMessage({type:'ecs-diagram-node',id:n.getAttribute('data-node-id')},'*');});</script></body>`,
      );
      asset = { body: html, type: "text/html", policy: diagramPolicy };
    }
  }
  cache.set(route, asset);
  return asset;
}
