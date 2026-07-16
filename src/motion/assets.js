import { readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(fileURLToPath(new URL("../../catalog/text-runtime/", import.meta.url)));
const mediaTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".otf", "font/otf"],
  [".png", "image/png"],
  [".ttf", "font/ttf"],
]);

export async function startMotionAssetServer() {
  const server = createServer(async (request, response) => {
    const pathname = decodeURIComponent(new URL(request.url ?? "/", "http://127.0.0.1").pathname);
    const target = path.resolve(root, `.${pathname}`);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
      response.writeHead(403).end();
      return;
    }
    const info = await stat(target).catch(() => undefined);
    if (!info?.isFile()) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "cache-control": "no-store",
      "content-length": info.size,
      "content-type": mediaTypes.get(path.extname(target).toLowerCase()) ?? "application/octet-stream",
    });
    response.end(await readFile(target));
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("canonical text asset server did not bind a TCP port");
  return {
    baseUrl: `http://127.0.0.1:${address.port}/`,
    close: () => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())),
  };
}

export async function settleCanonicalFrames(page) {
  const frames = page.locator("iframe[data-vibeedit-canonical]");
  for (let index = 0; index < await frames.count(); index += 1) {
    const element = frames.nth(index);
    const handle = await element.elementHandle();
    const frame = await handle?.contentFrame();
    if (!frame) throw new Error(`canonical text frame ${index} did not attach`);
    await frame.waitForFunction(() => Object.keys(globalThis.__timelines ?? {}).length > 0 || Boolean(document.body.dataset.error), undefined, { timeout: 15_000 });
    const error = await frame.locator("body").getAttribute("data-error");
    if (error) throw new Error(`canonical text frame ${index}: ${error}`);
    await frame.evaluate(async (time) => {
      if (document.fonts?.ready) await document.fonts.ready;
      const timeline = Object.values(globalThis.__timelines ?? {})[0];
      timeline.time(time);
      if (typeof timeline.pause === "function") timeline.pause();
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    }, Number(await element.getAttribute("data-vibeedit-time")));
  }
}
