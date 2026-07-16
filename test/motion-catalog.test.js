import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { portableMotionComponents, renderComponent, trackingPointAt } from "../src/index.js";


test("all portable motion components seek deterministically without network content", () => {
  assert.equal(portableMotionComponents.length, 50);
  assert.equal(new Set(portableMotionComponents.map((component) => component.id)).size, 50);
  for (const component of portableMotionComponents) {
    const context = { durationFrames: 60, width: 640, height: 360 };
    const early = renderComponent(component.id, {}, 2, context);
    const late = renderComponent(component.id, {}, 42, context);
    assert.equal(early, renderComponent(component.id, {}, 2, context), component.id);
    assert.notEqual(early, late, component.id);
    assert.match(early, /data-vibeedit-component=/);
    assert.doesNotMatch(early, /<script|https?:\/\//i);
  }
});


test("portable motion components reject CSS injection and escape text", () => {
  const html = renderComponent(
    portableMotionComponents[0].id,
    { text: "<img src=x>", foreground: "red;background:url(https://invalid.example)" },
    0,
    { durationFrames: 30, width: 640, height: 360 },
  );
  assert.doesNotMatch(html, /<img|url\(/);
  assert.match(html, /&lt;img/);
});


test("face-follow motion interpolates tracked positions", () => {
  const points = [{ frame: 0, x: 0.2, y: 0.3 }, { frame: 10, x: 0.8, y: 0.7 }];
  assert.deepEqual(trackingPointAt(points, 5), { x: 0.5, y: 0.5 });
  const html = renderComponent("vibeedit://text/negative-face-follow", { text: "TRACKED", trackingFrames: points }, 5, { durationFrames: 30, width: 640, height: 360 });
  assert.match(html, /left:50\.0000%;top:50\.0000%/);
});


test("every registered text effect has a verified hash-bound preview", () => {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const catalog = JSON.parse(fs.readFileSync(path.join(root, "catalog", "catalog.json"), "utf8"));
  const assets = JSON.parse(fs.readFileSync(path.join(root, "catalog", "assets.json"), "utf8"));
  const text = catalog.items.filter((item) => item.id.startsWith("vibeedit://text/"));
  const byPath = new Map(assets.assets.map((asset) => [asset.path, asset]));

  assert.equal(text.length, 52);
  assert.equal(new Set(text.map((item) => item.id)).size, 52);
  for (const item of text) {
    assert.equal(item.preview.status, "verified", item.id);
    assert.equal(item.preview.mediaType, "video/mp4", item.id);
    const assetPath = path.posix.join("catalog", item.preview.uri);
    const asset = byPath.get(assetPath);
    assert.ok(asset, `${item.id} is missing its asset ledger entry`);
    const bytes = fs.readFileSync(path.join(root, assetPath));
    assert.equal(bytes.length, asset.bytes, item.id);
    assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), asset.sha256, item.id);
    assert.equal(asset.redistribution, "verified", item.id);
    assert.equal(asset.decodable, true, item.id);
  }
});
