import assert from "node:assert/strict";
import test from "node:test";
import { searchCatalog } from "../src/catalog.js";

test("catalog search distinguishes workflows, templates, and mask intent", () => {
  const expected = new Map([
    ["show several transitions in one edit", "vibeedit://template/multiple-transitions"],
    ["add typography to my fan edit", "vibeedit://skill/fanedit-text"],
    ["route the complete fan edit workflow", "vibeedit://skill/vibeedit-fan-edit"],
    ["mix Python media and HTML text", "vibeedit://template/mixed-source-html"],
    ["choose and place transitions for me", "vibeedit://skill/vibeedit-transition-editor"],
    ["plan sound design for the whole edit", "vibeedit://skill/vibeedit-sound-design"],
    ["apply an effect only inside the segmentation", "vibeedit://template/mask-subject-effect"],
  ]);
  assert.deepEqual(new Map([...expected].map(([query]) => [query, searchCatalog(query, { limit: 1 })[0].id])), expected);
});
