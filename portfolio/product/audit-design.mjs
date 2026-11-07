// Bounded local browser audit; no AWS, no dependency installation.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { createProductServer } from "./server.mjs";
assert(
  process.env.PLAYWRIGHT_MODULE &&
    process.env.CHROME_EXECUTABLE &&
    process.argv[2],
);
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE));
const server = createProductServer();
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_EXECUTABLE,
});
const context = await browser.newContext({ reducedMotion: "reduce" });
const report = {
  at: new Date().toISOString(),
  scope:
    "Shell semantics, core palette contrast, focus and reduced motion; not a WCAG certification or replacement for assistive-technology testing.",
  checks: [],
  contrast: [],
};
await context.route("**/*", (r) =>
  new URL(r.request().url()).origin === origin ? r.continue() : r.abort(),
);
try {
  const p = await context.newPage();
  for (const width of [320, 390, 768, 1440, 1920]) {
    await p.setViewportSize({ width, height: 1000 });
    for (const route of [
      "/",
      "/demo",
      "/resilience",
      "/architecture",
      "/evidence",
    ]) {
      await p.goto(origin + route);
      await p.locator("h1").waitFor();
      const r = await p.evaluate(() => {
        const visible = (n) =>
          n.getBoundingClientRect().width > 0 &&
          n.getBoundingClientRect().height > 0;
        const named = (n) =>
          Boolean(n.getAttribute("aria-label") || n.textContent.trim());
        return {
          heading: document.querySelectorAll("h1").length,
          unnamedButtons: [...document.querySelectorAll("button")]
            .filter(visible)
            .filter((n) => !named(n)).length,
          unlabelledInputs: [
            ...document.querySelectorAll("input,select,textarea"),
          ]
            .filter(visible)
            .filter((n) => !n.labels?.length && !n.getAttribute("aria-label"))
            .length,
          smallButtons: [...document.querySelectorAll("button")]
            .filter(visible)
            .filter((n) => n.getBoundingClientRect().height < 43.9)
            .map((n) => n.textContent),
          overflow: document.documentElement.scrollWidth > innerWidth,
          body: parseFloat(getComputedStyle(document.body).fontSize),
          reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
          focusRule: [...document.styleSheets]
            .flatMap((s) => [...s.cssRules])
            .some((r) => r.selectorText === ":focus-visible"),
          css: Object.fromEntries(
            [
              "--text",
              "--muted",
              "--accent",
              "--mint",
              "--violet",
              "--error",
              "--ink",
              "--surface",
              "--raised",
            ].map((v) => [
              v,
              getComputedStyle(document.documentElement)
                .getPropertyValue(v)
                .trim(),
            ]),
          ),
        };
      });
      assert.equal(r.heading, 1);
      assert.equal(r.unnamedButtons, 0);
      assert.equal(r.unlabelledInputs, 0);
      assert.deepEqual(r.smallButtons, []);
      assert(!r.overflow);
      assert(r.body >= 16);
      assert(r.reduced && r.focusRule);
      report.checks.push({ width, route, result: "PASS" });
      if (!report.contrast.length) {
        const luminance = (c) => {
          const rgb = c
            .slice(1)
            .match(/../g)
            .map((v) => parseInt(v, 16) / 255)
            .map((v) =>
              v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4,
            );
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
        };
        for (const fg of [
          "--text",
          "--muted",
          "--accent",
          "--mint",
          "--violet",
          "--error",
        ])
          for (const bg of ["--ink", "--surface", "--raised"]) {
            const x = luminance(r.css[fg]),
              y = luminance(r.css[bg]),
              ratio = (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
            assert(ratio >= 4.5, fg + "/" + bg);
            report.contrast.push({
              fg,
              bg,
              ratio: Math.round(ratio * 100) / 100,
            });
          }
      }
    }
  }
  report.status = "PASS";
} catch (e) {
  report.status = "FAIL";
  report.error = e.message;
  process.exitCode = 1;
} finally {
  await browser.close();
  await new Promise((r) => server.close(r));
  await writeFile(process.argv[2], JSON.stringify(report, null, 2) + "\n", {
    flag: "wx",
  });
  console.log(JSON.stringify(report));
}
