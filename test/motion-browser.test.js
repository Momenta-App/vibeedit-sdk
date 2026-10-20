import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { isLocalBrowserUrl } from "../src/motion/assets.js";
import { renderMotionFrame } from "../src/motion/browser.js";

test("browser resource boundary rejects userinfo and other origins", () => {
  const origin = "http://127.0.0.1:49123/";
  assert.equal(isLocalBrowserUrl(origin + "font.ttf", origin), true);
  assert.equal(isLocalBrowserUrl(origin + "image@2x.png", origin), true);
  assert.equal(isLocalBrowserUrl("data:image/png;base64,AAAA", origin), true);
  for (const url of ["http://127.0.0.1:49123@outside.invalid/private", "http://@127.0.0.1:49123/private", "http://127.0.0.1:49124/private", "file:///private/file"]) {
    assert.equal(isLocalBrowserUrl(url, origin), false);
  }
});

test("canonical motion PNG keeps transparent margins and fits a small canvas", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "vibeedit-node-alpha-"));
  try {
    const spec = { canvas: { width: 320, height: 180, frameRate: { numerator: 30, denominator: 1 } }, timeline: { tracks: [{ order: 0, items: [{ kind: "motion", componentId: "vibeedit://text/mogrt-fluorscent", placement: { startFrame: 0, durationFrames: 60 }, props: { text: "ALPHA READY", background: "transparent" } }] }] } };
    const output = await renderMotionFrame(spec, 30, path.join(root, "alpha.png"));
    const result = spawnSync("ffmpeg", ["-v", "error", "-i", output, "-vf", "alphaextract", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]);
    assert.equal(result.status, 0, result.stderr.toString());
    const alpha = result.stdout;
    assert.equal(alpha.length, 320 * 180);
    const visible = [...alpha].flatMap((value, index) => value > 8 ? [index] : []);
    assert.ok(visible.length > 0);
    assert.equal(Math.min(...alpha), 0);
    assert.ok(Math.min(...visible.map(index => index % 320)) > 4);
    assert.ok(Math.max(...visible.map(index => index % 320)) < 315);
    assert.ok(Math.min(...visible.map(index => Math.floor(index / 320))) > 4);
    assert.ok(Math.max(...visible.map(index => Math.floor(index / 320))) < 175);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
