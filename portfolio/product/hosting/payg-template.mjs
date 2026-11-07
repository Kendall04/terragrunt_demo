// Explicit alternative only. Never used automatically when Free is rejected.
import { template } from "./template.mjs";
import { writeFile, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
export async function paygTemplate() {
  const t = await template();
  t.Description =
    "ECS portfolio DEMO only. Explicit pay-as-you-go alternative; no WAF or paid plan subscription.";
  delete t.Resources.WebACL;
  delete t.Resources.FreeSubscription;
  delete t.Resources.Distribution.Properties.DistributionConfig.WebACLId;
  delete t.Outputs.Subscription;
  t.Parameters.Enabled.Description =
    "Enable only after package checksums and private origin verification";
  return t;
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  if (process.argv.length !== 3)
    throw new Error("Usage: payg-template.mjs <new-output-directory>");
  await mkdir(process.argv[2], { recursive: true });
  const raw = JSON.stringify(await paygTemplate(), null, 2) + "\n";
  await writeFile(path.join(process.argv[2], "template.json"), raw, {
    flag: "wx",
  });
  console.log(
    JSON.stringify({
      sha256: createHash("sha256").update(raw).digest("hex"),
      bytes: Buffer.byteLength(raw),
    }),
  );
}
