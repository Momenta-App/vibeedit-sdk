import assert from "node:assert/strict";
import test from "node:test";

import { portableMotionComponents, renderComponent, trackingPointAt } from "../src/index.js";


test("all portable motion components seek deterministically without network content", () => {
  assert.equal(portableMotionComponents.length, 74);
  assert.equal(new Set(portableMotionComponents.map((component) => component.id)).size, 74);
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
