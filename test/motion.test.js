import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { documentForFrame, renderComponent } from "../src/index.js";

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
