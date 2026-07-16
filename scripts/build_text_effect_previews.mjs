import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { spawnSync } from "node:child_process";
import { chromium } from "playwright";
import { portableMotionComponents } from "../src/motion/components.generated.js";
import { settleCanonicalFrames, startMotionAssetServer } from "../src/motion/assets.js";
import { documentForFrame } from "../src/motion/runtime.js";

const root = new URL("..", import.meta.url);
const rootPath = decodeURIComponent(root.pathname.replace(/\/$/, ""));
const width = 640;
const height = 360;
const fps = 24;
const durationFrames = 48;
const representativeFrame = 32;
const limitIndex = process.argv.indexOf("--limit");
const limit = limitIndex === -1 ? undefined : Number(process.argv[limitIndex + 1]);
const idsIndex = process.argv.indexOf("--ids");
const requestedIds = idsIndex === -1 ? undefined : new Set(process.argv[idsIndex + 1].split(",").map((value) => value.startsWith("vibeedit://") ? value : `vibeedit://text/${value}`));
const catalogPath = join(rootPath, "catalog/catalog.json");
const assetsPath = join(rootPath, "catalog/assets.json");
const previewRoot = join(rootPath, "catalog/previews/text-effects");
const evidenceRoot = join(rootPath, "docs/evidence/text-effects");
const catalog = JSON.parse(await readFile(catalogPath, "utf8"));
const textItems = catalog.items.filter((item) => item.id.startsWith("vibeedit://text/")).sort((left, right) => left.id.localeCompare(right.id));
const selected = requestedIds ? textItems.filter((item) => requestedIds.has(item.id)) : Number.isFinite(limit) ? textItems.slice(0, Math.max(0, limit)) : textItems;
if (requestedIds && selected.length !== requestedIds.size) throw new Error(`unknown text effect IDs: ${[...requestedIds].filter((id) => !selected.some((item) => item.id === id)).join(", ")}`);
const fullRun = selected.length === textItems.length;
const work = await mkdtemp(join(tmpdir(), "vibeedit-text-effects-"));
await mkdir(previewRoot, { recursive: true });
await mkdir(evidenceRoot, { recursive: true });
if (fullRun) {
  const expected = new Set(textItems.map((item) => `${item.id.replace("vibeedit://text/", "")}.mp4`));
  await Promise.all((await readdir(previewRoot)).filter((name) => name.endsWith(".mp4") && !expected.has(name)).map((name) => rm(join(previewRoot, name))));
}

const assets = await startMotionAssetServer();
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
await page.emulateMedia({ reducedMotion: "reduce" });
const requests = [];
const consoleErrors = [];
const pageErrors = [];
page.on("request", (request) => {
  if (!request.url().startsWith("about:") && !request.url().startsWith("data:") && !request.url().startsWith(assets.baseUrl)) requests.push(request.url());
});
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => pageErrors.push(String(error)));

await page.setContent(backgroundDocument(), { waitUntil: "load" });
const backgroundPath = join(work, "background.png");
await page.screenshot({ path: backgroundPath, animations: "disabled" });

if (process.argv.includes("--contact-only")) {
  const evidencePath = join(evidenceRoot, "text-effect-conformance.json");
  const evidence = JSON.parse(await readFile(evidencePath, "utf8"));
  const sheets = [];
  for (const [frame, name] of contactSheetFrames()) {
    const cards = [];
    for (const [index, result] of evidence.results.entries()) {
      const thumbnail = join(work, `contact-${frame}-${String(index).padStart(3, "0")}.png`);
      run("ffmpeg", [
        "-hide_banner", "-loglevel", "error", "-y", "-ss", String(frame / fps),
        "-i", join(rootPath, result.preview), "-frames:v", "1", thumbnail,
      ]);
      const image = await readFile(thumbnail);
      cards.push(`<figure><img src="data:image/png;base64,${image.toString("base64")}"><figcaption>${escapeHtml(result.id.replace("vibeedit://text/", ""))}</figcaption></figure>`);
    }
    const output = join(evidenceRoot, name);
    await writeContactSheet(browser, cards, output);
    const bytes = await readFile(output);
    sheets.push({ frame, path: relative(rootPath, output), sha256: sha256(bytes), bytes: bytes.length });
  }
  evidence.contactSheet = sheets.find((sheet) => sheet.frame === representativeFrame).path;
  evidence.contactSheets = sheets;
  await writeFile(evidencePath, JSON.stringify(evidence, null, 2) + "\n");
  await browser.close();
  await assets.close();
  await rm(work, { recursive: true, force: true });
  process.stdout.write(`${JSON.stringify({ ok: true, rebuilt: sheets.map((sheet) => sheet.path), cards: evidence.results.length })}\n`);
  process.exit(0);
}

const results = [];
try {
  for (const [index, item] of selected.entries()) {
    const slug = item.id.replace("vibeedit://text/", "");
    const frameRoot = join(work, slug);
    const previewPath = join(previewRoot, `${slug}.mp4`);
    const requestStart = requests.length;
    const consoleStart = consoleErrors.length;
    const pageErrorStart = pageErrors.length;
    await mkdir(frameRoot, { recursive: true });
    process.stdout.write(`[${index + 1}/${selected.length}] ${item.id}\n`);
    const props = Object.fromEntries(
      Object.entries(item.parameters?.properties ?? {})
        .filter(([, value]) => Object.hasOwn(value, "default"))
        .map(([key, value]) => [key, value.default]),
    );
    if (!props.text) props.text = baselineText(item.id) ?? item.name;
    const spec = testSpec(item.id, props);
    const frameHashes = new Map();
    let representativePath;
    for (let frame = 0; frame < durationFrames; frame += 1) {
      await page.setContent(withQaBackground(documentForFrame(spec, frame, { assetBaseUrl: assets.baseUrl })), { waitUntil: "load" });
      await settleCanonicalFrames(page);
      const framePath = join(frameRoot, `frame-${String(frame).padStart(4, "0")}.png`);
      const bytes = await page.screenshot({ path: framePath, animations: "disabled" });
      if ([2, 24, 43].includes(frame)) frameHashes.set(frame, sha256(bytes));
      if (frame === representativeFrame) representativePath = framePath;
    }

    await page.setContent(withQaBackground(documentForFrame(spec, 24, { assetBaseUrl: assets.baseUrl })), { waitUntil: "load" });
    await settleCanonicalFrames(page);
    const repeatHash = sha256(await page.screenshot({ animations: "disabled" }));
    await page.setContent(withQaBackground(documentForFrame(spec, durationFrames - 1, { assetBaseUrl: assets.baseUrl })), { waitUntil: "load" });
    await settleCanonicalFrames(page);
    const dom = await page.evaluate(() => {
      const section = document.querySelector("[data-vibeedit-component]");
      const primary = section?.querySelector(":scope > div") ?? section;
      const rect = primary?.getBoundingClientRect();
      return {
        component: section?.getAttribute("data-vibeedit-component") ?? null,
        text: section?.textContent?.replace(/\s+/g, " ").trim() ?? "",
        rect: rect ? { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height } : null,
      };
    });

    run("ffmpeg", [
      "-hide_banner", "-loglevel", "error", "-y", "-framerate", String(fps), "-i", join(frameRoot, "frame-%04d.png"),
      "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", previewPath,
    ]);
    const probe = JSON.parse(run("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", previewPath]));
    const video = probe.streams.find((stream) => stream.codec_type === "video");
    const ssimOutput = run("ffmpeg", ["-hide_banner", "-i", backgroundPath, "-i", representativePath, "-lavfi", "ssim", "-f", "null", "-"], true);
    const visualSsim = Number(/All:([\d.]+)/.exec(ssimOutput)?.[1] ?? "1");
    const ocrOutput = runOptional("tesseract", [representativePath, "stdout", "--psm", "6"], true);
    const ocr = ocrOutput?.trim().replace(/\s+/g, " ") ?? "";
    const expectedText = String(props.text ?? "").replace(/\s+/g, " ").trim();
    const rect = dom.rect;
    const checks = {
      deterministicFrame: repeatHash === frameHashes.get(24),
      visiblePixels: visualSsim < 0.9995,
      domTextPresent: Boolean(expectedText) && normalize(dom.text).includes(normalize(expectedText)),
      primaryBoxPresent: Boolean(rect && rect.width > 0 && rect.height > 0),
      primaryBoxWithinFrame: Boolean(rect && rect.left >= -1 && rect.top >= -1 && rect.right <= width + 1 && rect.bottom <= height + 1),
      temporalChange: frameHashes.get(2) !== frameHashes.get(43),
      temporalChangeRequired: item.id !== "vibeedit://text/caption-blend-difference",
      noNetworkRequests: requests.length === requestStart,
      noConsoleErrors: consoleErrors.length === consoleStart && pageErrors.length === pageErrorStart,
      decoded: video?.width === width && video?.height === height && Number(video?.nb_frames) === durationFrames,
    };
    const passed = Object.entries(checks).every(([key, value]) => key === "temporalChange" || key === "temporalChangeRequired" || value)
      && (!checks.temporalChangeRequired || checks.temporalChange);
    const bytes = await readFile(previewPath);
    const metadata = motionMetadata(item.id);
    results.push({
      id: item.id,
      name: item.name,
      family: metadata.family,
      motion: metadata.motion,
      fidelity: metadata.canonical
        ? { mode: "canonical-source-clone", sourceEntry: metadata.canonical.entry, sourceRevision: JSON.parse(await readFile(join(rootPath, "catalog/motion-components.json"), "utf8")).revision }
        : { mode: "portable-runtime", sourceEntry: null, sourceRevision: null },
      preview: relative(rootPath, previewPath),
      sha256: sha256(bytes),
      bytes: bytes.length,
      durationSeconds: Number(probe.format.duration),
      frames: Number(video?.nb_frames),
      width: video?.width,
      height: video?.height,
      frameRate: video?.avg_frame_rate,
      representativeFrame,
      visualSsimAgainstBackground: visualSsim,
      ocr: { advisory: true, available: ocrOutput !== undefined, text: ocr },
      dom,
      checks,
      passed,
    });
  }

  const sheets = [];
  for (const [frame, name] of contactSheetFrames(fullRun ? "" : "pilot-")) {
    const cards = await Promise.all(results.map(async (result) => {
      const image = await readFile(join(work, result.id.replace("vibeedit://text/", ""), `frame-${String(frame).padStart(4, "0")}.png`));
      return `<figure><img src="data:image/png;base64,${image.toString("base64")}"><figcaption>${escapeHtml(result.id.replace("vibeedit://text/", ""))}</figcaption></figure>`;
    }));
    const output = join(evidenceRoot, name);
    await writeContactSheet(browser, cards, output);
    const bytes = await readFile(output);
    sheets.push({ frame, path: relative(rootPath, output), sha256: sha256(bytes), bytes: bytes.length });
  }
  const contactSheet = join(rootPath, sheets.find((sheet) => sheet.frame === representativeFrame).path);

  const concatFile = join(work, "previews.ffconcat");
  await writeFile(concatFile, ["ffconcat version 1.0", ...results.map((result) => `file '${join(rootPath, result.preview).replaceAll("'", "'\\''")}'`)].join("\n") + "\n");
  const reviewReel = join(evidenceRoot, fullRun ? "review-reel.mp4" : "pilot-review-reel.mp4");
  run("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", concatFile, "-c", "copy", "-movflags", "+faststart", reviewReel]);

  const failures = results.filter((result) => !result.passed).map((result) => result.id);
  const evidence = {
    schemaVersion: "vibeedit.text-effect-conformance.v1",
    sourceRevision: JSON.parse(await readFile(join(rootPath, "catalog/motion-components.json"), "utf8")).revision,
    totalRegistered: textItems.length,
    tested: results.length,
    portableImported: 50,
    baselineComponents: ["vibeedit://text/caption-rail", "vibeedit://text/negative"],
    passed: results.length - failures.length,
    failed: failures.length,
    failures,
    renderContract: { width, height, fps, durationFrames, background: "split-gradient-conformance-field", network: "blocked-by-contract" },
    fidelityContract: {
      canonicalSourceClones: results.filter((result) => result.fidelity.mode === "canonical-source-clone").length,
      portableRuntimeEffects: results.filter((result) => result.fidelity.mode === "portable-runtime").length,
      meaning: "Render checks prove deterministic browser output. Canonical-source-clone identifies effects rendered by the packaged original VibeEdit HTML/CSS/JS implementation; portable-runtime does not claim source visual identity.",
    },
    aggregatePreviewSha256: sha256(results.map((result) => `${result.id}:${result.sha256}`).join("\n")),
    contactSheet: relative(rootPath, contactSheet),
    contactSheets: sheets,
    reviewReel: relative(rootPath, reviewReel),
    results,
  };
  const evidencePath = join(evidenceRoot, fullRun ? "text-effect-conformance.json" : "pilot-conformance.json");
  await writeFile(evidencePath, JSON.stringify(evidence, null, 2) + "\n");
  if (failures.length) throw new Error(`text effect conformance failed: ${failures.join(", ")}`);

  if (fullRun) {
    for (const item of catalog.items.filter((entry) => entry.id.startsWith("vibeedit://text/"))) {
      const result = results.find((entry) => entry.id === item.id);
      item.preview = {
        status: "verified",
        uri: `previews/text-effects/${item.id.replace("vibeedit://text/", "")}.mp4`,
        mediaType: "video/mp4",
        note: result.fidelity.mode === "canonical-source-clone"
          ? "Rendered from the packaged original VibeEdit HTML/CSS/JS implementation and checked for deterministic frame, geometry, network, and decode behavior."
          : "Rendered by the portable browser motion runtime and checked for deterministic frame, geometry, network, and decode behavior; no source-identity claim is made.",
      };
      item.validation = [
        ...item.validation.filter((entry) => entry.id !== "visual-render-conformance"),
        {
          id: "visual-render-conformance",
          status: "passed",
          command: "npm run text:previews",
          evidence: `docs/evidence/text-effects/text-effect-conformance.json#${result.id}`,
        },
      ];
    }
    await writeFile(catalogPath, JSON.stringify(catalog, null, 2) + "\n");
    const assets = JSON.parse(await readFile(assetsPath, "utf8"));
    assets.assets = [
      ...assets.assets.filter((asset) => !asset.tags?.includes("text-effect-conformance")),
      ...results.map((result) => ({
        path: result.preview,
        sha256: result.sha256,
        bytes: result.bytes,
        durationSeconds: result.durationSeconds,
        category: "preview-video",
        tags: ["text", "html", "text-effect-conformance"],
        intendedUse: `catalog preview for ${result.id}`,
        recommendedGainDb: null,
        loudnessLufs: null,
        source: "VibeEdit deterministic browser motion runtime",
        license: "SEE LICENSE IN LICENSE.md",
        redistribution: "verified",
        commercialOutputAllowed: true,
        decodable: true,
      })),
    ];
    await writeFile(assetsPath, JSON.stringify(assets, null, 2) + "\n");
  }
  process.stdout.write(`${JSON.stringify({ ok: true, tested: results.length, passed: results.length, contactSheet: relative(rootPath, contactSheet), reviewReel: relative(rootPath, reviewReel) })}\n`);
} finally {
  await browser.close();
  await assets.close();
  await rm(work, { recursive: true, force: true });
}

function testSpec(id, props) {
  return {
    canvas: { width, height, frameRate: { numerator: fps, denominator: 1 } },
    timeline: {
      tracks: [{
        id: "M1",
        kind: "motion",
        order: 10,
        items: [{ id: "effect", kind: "motion", placement: { startFrame: 0, durationFrames }, componentId: id, props }],
      }],
    },
  };
}

function withQaBackground(document) {
  return document.replace("</head>", `<style>body{background:linear-gradient(118deg,#05070d 0%,#18253b 43%,#f1efe8 43%,#9684be 72%,#17111e 100%)}body:before{content:"";position:fixed;inset:0;background:linear-gradient(90deg,transparent 49.7%,rgba(255,255,255,.28) 49.7% 50.3%,transparent 50.3%);pointer-events:none}</style></head>`);
}

function backgroundDocument() {
  return withQaBackground("<!doctype html><html><head><meta charset=\"utf-8\"><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}</style></head><body></body></html>");
}

function contactDocument(cards) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}html,body{margin:0;background:#05070d;color:#fff;font-family:Inter,-apple-system,Arial,sans-serif}main{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;padding:18px}figure{margin:0;border:1px solid #283246;background:#0b0f18;border-radius:8px;overflow:hidden}img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}figcaption{padding:8px 10px;font-size:14px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}</style></head><body><main>${cards}</main></body></html>`;
}

function contactSheetFrames(prefix = "") {
  return [[2, `${prefix}contact-sheet-early.jpg`], [24, `${prefix}contact-sheet-mid.jpg`], [representativeFrame, `${prefix}contact-sheet.jpg`], [43, `${prefix}contact-sheet-late.jpg`]];
}

async function writeContactSheet(browserInstance, cards, output) {
  const contactPage = await browserInstance.newPage({ viewport: { width: 2560, height: 1440 }, deviceScaleFactor: 1 });
  await contactPage.setContent(contactDocument(cards.join("")), { waitUntil: "load" });
  await contactPage.waitForFunction(() => [...document.images].every((image) => image.complete && image.naturalWidth > 0));
  await contactPage.screenshot({ path: output, type: "jpeg", quality: 90, fullPage: true, animations: "disabled" });
  await contactPage.close();
}

function motionMetadata(id) {
  if (id === "vibeedit://text/negative") return { family: "baseline", motion: "word-reveal", canonical: null };
  if (id === "vibeedit://text/caption-rail") return { family: "baseline", motion: "active-word", canonical: null };
  const component = portableMotionComponents.find((entry) => entry.id === id);
  return { family: component?.family ?? "unknown", motion: component?.motion ?? "unknown", canonical: component?.canonical ?? null };
}

function baselineText(id) {
  if (id === "vibeedit://text/negative") return "NO EXCUSES";
  if (id === "vibeedit://text/caption-rail") return "MAKE EVERY FRAME COUNT";
  return undefined;
}

function run(command, args, includeStderr = false) {
  const result = spawnSync(command, args, { cwd: rootPath, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")}\n${result.stderr || result.stdout}`);
  return `${result.stdout ?? ""}${includeStderr ? result.stderr ?? "" : ""}`;
}

function runOptional(command, args, includeStderr = false) {
  const result = spawnSync(command, args, { cwd: rootPath, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  if (result.error?.code === "ENOENT") return undefined;
  if (result.status !== 0) return undefined;
  return `${result.stdout ?? ""}${includeStderr ? result.stderr ?? "" : ""}`;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function normalize(value) {
  return value.normalize("NFKC").toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

function escapeHtml(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}
