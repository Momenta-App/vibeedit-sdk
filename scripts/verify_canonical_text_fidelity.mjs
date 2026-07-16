import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { spawnSync } from "node:child_process";
import { chromium } from "playwright";
import { portableMotionComponents } from "../src/motion/components.generated.js";
import { startMotionAssetServer } from "../src/motion/assets.js";

const sourceIndex = process.argv.indexOf("--source-base-url");
if (sourceIndex === -1 || !process.argv[sourceIndex + 1]) throw new Error("usage: node scripts/verify_canonical_text_fidelity.mjs --source-base-url http://127.0.0.1:8765/text-effect-catalog/components/html-motion-mogrt/");
const sourceBaseUrl = new URL(process.argv[sourceIndex + 1]);
const onlyIndex = process.argv.indexOf("--only");
const requestedIds = onlyIndex === -1 ? undefined : new Set(process.argv[onlyIndex + 1].split(",").map((value) => value.startsWith("vibeedit://") ? value : `vibeedit://text/${value}`));
const keepWork = process.argv.includes("--keep-work");
const rootPath = decodeURIComponent(new URL("..", import.meta.url).pathname.replace(/\/$/, ""));
const work = await mkdtemp(join(tmpdir(), "vibeedit-source-fidelity-"));
const assets = await startMotionAssetServer();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 640, height: 360 }, deviceScaleFactor: 1 });
const frames = [2, 24, 43];
const results = [];
const components = portableMotionComponents.filter((entry) => entry.canonical && (!requestedIds || requestedIds.has(entry.id)));
if (requestedIds && components.length !== requestedIds.size) throw new Error("one or more --only canonical text effect IDs were not found");

await page.addInitScript(() => {
  let state = 0x5f3759df;
  Math.random = () => {
    state = (1664525 * state + 1013904223) >>> 0;
    return state / 0x100000000;
  };
});

try {
  for (const [index, component] of components.entries()) {
    process.stdout.write(`[${index + 1}/${components.length}] ${component.id}\n`);
    const comparisons = [];
    for (const frame of frames) {
      const source = await capture(new URL(component.canonical.entry, sourceBaseUrl), frame, join(work, `${index}-${frame}-source.png`));
      const packaged = await capture(new URL(component.canonical.entry, assets.baseUrl), frame, join(work, `${index}-${frame}-packaged.png`));
      const output = run("ffmpeg", ["-hide_banner", "-i", source, "-i", packaged, "-lavfi", "ssim", "-f", "null", "-"], true);
      comparisons.push({ frame, ssim: Number(/All:([\d.]+)/.exec(output)?.[1] ?? "0") });
    }
    results.push({
      id: component.id,
      sourceEntry: component.canonical.entry,
      comparisons,
      minimumSsim: Math.min(...comparisons.map((entry) => entry.ssim)),
    });
  }
} finally {
  await browser.close();
  await assets.close();
  if (!keepWork) await rm(work, { recursive: true, force: true });
}

const failures = results.filter((result) => result.minimumSsim < 0.95);
const manifest = JSON.parse(await readFile(join(rootPath, "catalog/text-runtime/manifest.json"), "utf8"));
const evidence = {
  schemaVersion: "vibeedit.canonical-text-source-fidelity.v1",
  sourceRevision: manifest.revision,
  sourceBaseUrl: sourceBaseUrl.href,
  compared: results.length,
  frames,
  minimumAcceptedSsim: 0.95,
  pixelIdentical: results.filter((result) => result.minimumSsim === 1).length,
  perceptuallyEquivalent: results.filter((result) => result.minimumSsim >= 0.95 && result.minimumSsim < 1).length,
  meaning: "SSIM is measured after deterministic seeking and compositing both the tracked VibeEdit source and packaged clone over the same matte. A score of 1 is pixel-identical; 0.95 or higher is accepted as perceptually equivalent and preserves small browser font-antialiasing differences.",
  passed: results.length - failures.length,
  failed: failures.length,
  failures: failures.map((result) => result.id),
  aggregateSha256: createHash("sha256").update(JSON.stringify(results)).digest("hex"),
  results,
};
const output = join(rootPath, "docs/evidence/text-effects/source-fidelity.json");
await writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
if (keepWork) process.stdout.write(`comparison frames: ${work}\n`);
if (failures.length) throw new Error(`canonical text source fidelity failed: ${failures.map((result) => `${result.id} (${result.minimumSsim})`).join(", ")}`);
process.stdout.write(`${JSON.stringify({ ok: true, compared: results.length, passed: results.length, evidence: relative(rootPath, output) })}\n`);

async function capture(url, frame, output) {
  url.searchParams.set("alpha", "1");
  url.searchParams.set("render", "1");
  url.searchParams.set("transparent", "1");
  await page.goto(url.href, { waitUntil: "load" });
  await page.addStyleTag({ content: "html,body{background:#18253b!important}.elegant-misc-root{background:transparent!important}" });
  await page.waitForFunction(() => Object.keys(globalThis.__timelines ?? {}).length > 0 || Boolean(document.body.dataset.error), undefined, { timeout: 15_000 });
  const error = await page.locator("body").getAttribute("data-error");
  if (error) throw new Error(`${url.pathname}: ${error}`);
  await page.evaluate(async (time) => {
    if (document.fonts?.ready) await document.fonts.ready;
    const timeline = Object.values(globalThis.__timelines ?? {})[0];
    timeline.time(time);
    if (typeof timeline.pause === "function") timeline.pause();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }, frame / 24);
  await page.screenshot({ path: output, omitBackground: false, animations: "disabled" });
  return output;
}

function run(command, args, includeStderr = false) {
  const result = spawnSync(command, args, { cwd: rootPath, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")}\n${result.stderr || result.stdout}`);
  return `${result.stdout ?? ""}${includeStderr ? result.stderr ?? "" : ""}`;
}
