import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { documentForFrame, renderComponent } from "../src/index.js";
import { portableMotionComponents } from "../src/motion/components.generated.js";

test("negative motion seeks deterministically", () => {
  const context = { durationFrames: 30, width: 640, height: 360 };
  const first = renderComponent("vibeedit://text/negative", { text: "NO EXCUSES" }, 12, context);
  assert.equal(first, renderComponent("vibeedit://text/negative", { text: "NO EXCUSES" }, 12, context));
  assert.notEqual(first, renderComponent("vibeedit://text/negative", { text: "NO EXCUSES" }, 20, context));
  assert.match(first, /data-frame="12"/);
});

test("motion HTML escapes untrusted text", () => {
  const html = renderComponent("vibeedit://text/negative", { text: "<script>alert(1)</script>" }, 0, { durationFrames: 1, width: 640, height: 360 });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});

test("caption rail seeks deterministically and advances its active word", () => {
  const context = { durationFrames: 30, width: 640, height: 360 };
  const early = renderComponent("vibeedit://text/caption-rail", { text: "MAKE EVERY FRAME COUNT" }, 2, context);
  assert.equal(early, renderComponent("vibeedit://text/caption-rail", { text: "MAKE EVERY FRAME COUNT" }, 2, context));
  assert.notEqual(early, renderComponent("vibeedit://text/caption-rail", { text: "MAKE EVERY FRAME COUNT" }, 24, context));
  assert.match(early, /data-vibeedit-component="caption-rail"/);
});

test("mixed fixture produces one deterministic document", async () => {
  const spec = JSON.parse(await readFile(new URL("../schema/fixtures/mixed.json", import.meta.url), "utf8"));
  assert.equal(documentForFrame(spec, 30), documentForFrame(spec, 30));
  assert.match(documentForFrame(spec, 30), /NO/);
});

test("canonical seeking uses the CompositionSpec canvas frame rate", () => {
  const component = portableMotionComponents.find((entry) => entry.id === "vibeedit://text/mogrt-bubble");
  const spec = {
    canvas: { width: 640, height: 360, frameRate: { numerator: 24, denominator: 1 } },
    timeline: { tracks: [{ order: 0, items: [{ kind: "motion", placement: { startFrame: 0, durationFrames: 48 }, componentId: component.id, props: {} }] }] },
  };
  assert.match(documentForFrame(spec, 12, { assetBaseUrl: "http://127.0.0.1:1234/" }), /data-vibeedit-time="0\.500000"/);
});

test("canonical text components retain their source renderer entries", () => {
  const canonical = portableMotionComponents.filter((component) => component.canonical);
  assert.equal(canonical.length, 53);
  assert.ok(canonical.every((component) => component.canonical.entry.endsWith(".html") || component.canonical.entry.includes(".html?")));
  const component = canonical.find((entry) => entry.id === "vibeedit://text/mogrt-bubble");
  const html = renderComponent(component.id, { text: component.defaultText }, 12, {
    assetBaseUrl: "http://127.0.0.1:1234/",
    durationFrames: 48,
    fps: 24,
    width: 640,
    height: 360,
  });
  assert.match(html, /data-vibeedit-canonical="true"/);
  assert.match(html, /families\/elegant-misc\/outputs\/Bubble\.html/);
  assert.match(html, /data-vibeedit-time="0\.500000"/);
});

test("packaged canonical text runtime matches its immutable manifest", async () => {
  const root = new URL("../catalog/text-runtime/", import.meta.url);
  const manifest = JSON.parse(await readFile(new URL("manifest.json", root), "utf8"));
  assert.equal(manifest.schemaVersion, "vibeedit.canonical-text-runtime.v1");
  assert.equal(manifest.files.length, 151);
  for (const record of manifest.files) {
    const bytes = await readFile(new URL(record.path.split("/").map(encodeURIComponent).join("/"), root));
    assert.equal(bytes.length, record.bytes, record.path);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), record.sha256, record.path);
  }
});
