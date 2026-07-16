import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import { settleCanonicalFrames, startMotionAssetServer } from "./assets.js";
import { documentForFrame } from "./runtime.js";

export async function renderMotionFrame(spec, frame, output, options = {}) {
  const { chromium } = await import("playwright").catch(() => {
    throw new Error('browser rendering requires Playwright: npm install --save-dev playwright && npx playwright install chromium');
  });
  const browser = await chromium.launch({ headless: true });
  const assets = await startMotionAssetServer();
  try {
    const page = await browser.newPage({ viewport: { width: spec.canvas.width, height: spec.canvas.height }, deviceScaleFactor: 1 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setContent(documentForFrame(spec, frame, { assetBaseUrl: assets.baseUrl }), { waitUntil: "load" });
    await settleCanonicalFrames(page);
    await mkdir(dirname(output), { recursive: true });
    await page.screenshot({ path: output, omitBackground: options.transparent ?? true, animations: "disabled" });
    return output;
  } finally {
    await assets.close();
    await browser.close();
  }
}
